import json

import pytest

from app.generator import _prompt, generate_pack
from app.validator import PackRequest


class FakeProvider:
    def __init__(self, responses: list[str]) -> None:
        self.responses = iter(responses)
        self.calls = 0
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.calls += 1
        self.prompts.append(prompt)
        return next(self.responses)


def safe_response() -> str:
    return json.dumps(
        {
            "missions": [
                {
                    "id": index,
                    "type": activity_type,
                    "text": text,
                    "est_minutes": 3,
                }
                for index, (activity_type, text) in enumerate(
                    [
                        ("find_shapes", "Notice three shapes."),
                        ("listen_for_sounds", "Listen for two sounds."),
                        ("find_colors", "Find three colors."),
                    ],
                    start=1,
                )
            ]
        }
    )


def request() -> PackRequest:
    return PackRequest(
        setting="park",
        time_limit_min=10,
        age_band="10-13",
        season="autumn",
    )


def test_retries_rejected_output_and_accepts_safe_pack() -> None:
    provider = FakeProvider(
        [
            '{"missions":[]}',
            safe_response(),
        ]
    )
    result = generate_pack(request(), provider)
    assert provider.calls == 2
    assert result.attempts_used == 2
    assert result.first_attempt_safe is False
    assert result.pack.generation_note is None
    assert "previous draft was rejected" in provider.prompts[1]
    assert "correct this issue" in provider.prompts[1]


def test_rejects_non_positive_attempt_limits() -> None:
    with pytest.raises(ValueError, match="greater than zero"):
        generate_pack(request(), FakeProvider([safe_response()]), max_attempts=0)


def test_returns_disclosed_backup_after_failed_attempts() -> None:
    provider = FakeProvider(["not json", "not json", "not json"])
    result = generate_pack(request(), provider)
    assert provider.calls == 3
    assert result.pack.generation_note is not None
    assert len(result.pack.missions) == 3
    assert sum(mission.est_minutes for mission in result.pack.missions) <= 10


def test_prompt_changes_with_setting_age_and_time_budget() -> None:
    garden_request = request().model_copy(update={"setting": "garden"})
    neighborhood_request = garden_request.model_copy(
        update={"setting": "neighborhood", "age_band": "14-17", "time_limit_min": 30}
    )
    garden_prompt = _prompt(garden_request)
    neighborhood_prompt = _prompt(neighborhood_request)
    assert "garden" in garden_prompt
    assert "leaf outlines" in garden_prompt
    assert "neighborhood" in neighborhood_prompt
    assert "14-17" in neighborhood_prompt
    assert "pose a quick question" in neighborhood_prompt
    assert "never tell anyone to close or shut their eyes" in neighborhood_prompt
    assert "exactly 5 missions" in neighborhood_prompt


@pytest.mark.parametrize(
    ("age_band", "age_specific_guidance"),
    [
        ("10-13", "state a simple observation"),
        ("14-17", "reach a brief conclusion"),
        ("18-20", "distinguish direct observations from inferences"),
    ],
)
def test_prompt_guidance_matches_selected_age_group(
    age_band: str,
    age_specific_guidance: str,
) -> None:
    prompt = _prompt(request().model_copy(update={"age_band": age_band}))
    assert age_specific_guidance in prompt
    assert "at most 10 minutes total" in prompt
    assert "exactly 3 missions" in prompt


def test_backup_pack_varies_by_setting_and_time_budget() -> None:
    provider = FakeProvider(["not json"] * 6)
    garden_result = generate_pack(request(), provider)
    neighborhood_result = generate_pack(
        request().model_copy(update={"setting": "neighborhood", "time_limit_min": 30}),
        provider,
    )
    assert len(garden_result.pack.missions) == 3
    assert len(neighborhood_result.pack.missions) == 5
    assert garden_result.pack.missions[0].text != neighborhood_result.pack.missions[0].text


def test_backup_pack_adapts_mission_challenge_to_age_group() -> None:
    provider = FakeProvider(["not json"] * 6)
    younger_pack = generate_pack(request(), provider).pack
    older_pack = generate_pack(
        request().model_copy(update={"age_band": "18-20"}),
        provider,
    ).pack
    assert "describe one detail" in younger_pack.missions[0].text
    assert "separate observation from inference" in older_pack.missions[0].text
    assert "public areas" in older_pack.missions[0].safety_note
