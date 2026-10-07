import json

import pytest

from app.validator import MissionValidationError, PackRequest, validate_missions

def make_response(texts: list[str] | None = None, minutes: list[int] | None = None) -> str:
    texts = texts or ["Notice three shapes nearby.", "Listen for two sounds.", "Find three colors."]
    minutes = minutes or [3, 3, 3]
    return json.dumps(
        {
            "missions": [
                {
                    "id": index,
                    "type": activity,
                    "text": text,
                    "est_minutes": minutes[index - 1],
                }
                for index, (activity, text) in enumerate(
                    zip(
                        ["find_shapes", "listen_for_sounds", "find_colors"],
                        texts,
                    ),
                    start=1,
                )
            ]
        }
    )


def test_accepts_safe_pack_within_time_budget() -> None:
    missions = validate_missions(make_response(), time_limit_min=10)
    assert len(missions) == 3


@pytest.mark.parametrize(
    "unsafe_text",
    [
        "Look at the road.",
        "Find a leaf to eat.",
        "Climb a tree.",
        "Use your phone to take a photo.",
        "Take a picture of a flower.",
        "Feel the snow and ice.",
        "Close your eyes and listen.",
        "Pick up a leaf.",
        "Collect five stones.",
    ],
)
def test_rejects_unsafe_mission_text(unsafe_text: str) -> None:
    with pytest.raises(MissionValidationError):
        validate_missions(make_response([unsafe_text, "Listen for two sounds.", "Find three colors."]), 10)


def test_rejects_non_allowlisted_activity() -> None:
    response = json.loads(make_response())
    response["missions"][0]["type"] = "find_mailboxes"
    with pytest.raises(MissionValidationError):
        validate_missions(json.dumps(response), 10)


def test_rejects_repeated_activity_types() -> None:
    response = json.loads(make_response())
    response["missions"][1]["type"] = response["missions"][0]["type"]
    with pytest.raises(MissionValidationError, match="different activity type"):
        validate_missions(json.dumps(response), 10)


def test_rejects_mission_text_longer_than_schema_limit() -> None:
    response = json.loads(make_response())
    response["missions"][0]["text"] = "x" * 161
    with pytest.raises(MissionValidationError, match="160 characters"):
        validate_missions(json.dumps(response), 10)


def test_rejects_time_budget_overrun() -> None:
    with pytest.raises(MissionValidationError):
        validate_missions(make_response(minutes=[4, 4, 4]), 10)


def test_adds_supervision_note_to_generated_missions() -> None:
    response = json.loads(make_response())
    missions = validate_missions(json.dumps(response), 10)
    assert all("within sight of your grown-up" in mission.safety_note for mission in missions)


@pytest.mark.parametrize("age_band", ["10-13", "14-17", "18-20"])
def test_accepts_each_supported_age_group(age_band: str) -> None:
    request = PackRequest(
        setting="park",
        time_limit_min=10,
        age_band=age_band,
        season="autumn",
    )
    missions = validate_missions(make_response(), 10, request.age_band)
    assert len(missions) == 3


def test_adult_missions_use_public_area_guidance_without_grown_up_supervision() -> None:
    missions = validate_missions(make_response(), 10, "18-20")
    assert all("public areas" in mission.safety_note for mission in missions)
    assert all("grown-up" not in mission.safety_note for mission in missions)


def test_rejects_unsupported_legacy_age_group() -> None:
    with pytest.raises(ValueError):
        PackRequest(
            setting="park",
            time_limit_min=10,
            age_band="7-9",
            season="autumn",
        )
