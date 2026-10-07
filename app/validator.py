import json
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

ActivityType = Literal[
    "find_shapes",
    "find_colors",
    "count_things",
    "listen_for_sounds",
    "texture_hunt",
    "look_up_sky",
    "find_numbers_or_letters",
    "nature_pattern_hunt",
    "gentle_movement",
]
AgeBand = Literal["10-13", "14-17", "18-20"]

ALLOWED_ACTIVITY_TYPES = {
    "find_shapes",
    "find_colors",
    "count_things",
    "listen_for_sounds",
    "texture_hunt",
    "look_up_sky",
    "find_numbers_or_letters",
    "nature_pattern_hunt",
    "gentle_movement",
}

SUPERVISION_PHRASE = "within sight of your grown-up"
DEFAULT_SAFETY_NOTE = "Stay with your grown-up and within sight of your grown-up."
ADULT_SAFETY_NOTE = "Stay in public areas and keep a safe distance from your group."
UNSAFE_TEXT_PATTERNS = (
    r"\broad(?:s)?\b",
    r"\bstreet(?:s)?\b",
    r"\bhighway(?:s)?\b",
    r"\btraffic\b",
    r"\bwater\b",
    r"\b(?:pond|river|lake|ocean|stream)(?:s)?\b",
    r"\bclimb(?:ing|s|ed)?\b",
    r"\bstranger(?:s)?\b",
    r"\bprivate property\b",
    r"\bpick(?:ing)?\b",
    r"\bcollect(?:ing)?\b",
    r"\btouch(?:ing|es|ed)?\b",
    r"\bpet(?:ting|s)?\b",
    r"\bfeed(?:ing|s)?\b",
    r"\beat(?:ing)?\b",
    r"\btast(?:e|ing|es|ed)\b",
    r"\bfeel(?:ing|s)?\b",
    r"\b(?:close|shut) your eyes\b",
    r"\b(?:screen|phone|gps|camera|map|tablet|device|app)\b",
    r"\b(?:photos?|pictures?|images?|photographs?|recording)\b",
    r"\bprivate propert(?:y|ies)\b",
)


class Mission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(ge=1)
    type: ActivityType
    text: str = Field(min_length=1, max_length=200)
    est_minutes: int = Field(ge=1, le=30)
    safety_note: str = Field(min_length=1, max_length=160)


class GeneratedMission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int = Field(ge=1, le=5)
    type: ActivityType
    text: str = Field(min_length=1, max_length=160)
    est_minutes: int = Field(ge=1, le=30)


class PackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    setting: Literal["park", "neighborhood", "garden"]
    time_limit_min: Literal[10, 20, 30]
    age_band: AgeBand
    season: Literal["spring", "summer", "autumn", "winter"]
    weather_note: str = Field(default="", max_length=100)


class MissionPack(BaseModel):
    pack_id: str
    setting: Literal["park", "neighborhood", "garden"]
    time_limit_min: Literal[10, 20, 30]
    age_band: AgeBand
    weather_note: str
    missions: list[Mission] = Field(min_length=3, max_length=5)
    closing: str
    generation_note: str | None = None


class MissionValidationError(ValueError):
    pass


def validate_missions(
    raw_response: str,
    time_limit_min: int,
    age_band: AgeBand = "10-13",
) -> list[Mission]:
    try:
        payload = json.loads(raw_response)
    except json.JSONDecodeError as exc:
        raise MissionValidationError("The model response was not valid JSON.") from exc

    if not isinstance(payload, dict) or set(payload) != {"missions"}:
        raise MissionValidationError("The response must contain only a missions array.")
    if not isinstance(payload["missions"], list) or not 3 <= len(payload["missions"]) <= 5:
        raise MissionValidationError("A pack must contain between 3 and 5 missions.")

    try:
        generated_missions = [
            GeneratedMission.model_validate(item) for item in payload["missions"]
        ]
    except ValidationError as exc:
        raise MissionValidationError(f"Mission fields are invalid: {exc}") from exc

    safety_note = ADULT_SAFETY_NOTE if age_band == "18-20" else DEFAULT_SAFETY_NOTE
    missions = [
        Mission(**mission.model_dump(), safety_note=safety_note)
        for mission in generated_missions
    ]

    if [mission.id for mission in missions] != list(range(1, len(missions) + 1)):
        raise MissionValidationError("Mission IDs must be sequential, starting at 1.")
    if len({mission.type for mission in missions}) != len(missions):
        raise MissionValidationError("Each mission must use a different activity type.")
    if any(mission.type not in ALLOWED_ACTIVITY_TYPES for mission in missions):
        raise MissionValidationError("A mission uses an activity outside the safety allowlist.")
    if sum(mission.est_minutes for mission in missions) > time_limit_min:
        raise MissionValidationError("Mission estimates exceed the selected time limit.")

    for mission in missions:
        content = mission.text.casefold()
        if any(re.search(pattern, content) for pattern in UNSAFE_TEXT_PATTERNS):
            raise MissionValidationError(
                f"Mission {mission.id} contains a prohibited safety topic."
            )
        if age_band == "18-20":
            if "public areas" not in mission.safety_note.casefold():
                raise MissionValidationError(
                    f"Mission {mission.id} is missing public-area guidance."
                )
        elif SUPERVISION_PHRASE not in mission.safety_note.casefold():
            raise MissionValidationError(f"Mission {mission.id} is missing supervision.")

    return missions
