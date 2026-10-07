import json
import logging
import uuid
from dataclasses import dataclass

from app.providers.base import ModelProvider
from app.providers.ollama import ProviderError
from app.validator import (
    AgeBand,
    ActivityType,
    ADULT_SAFETY_NOTE,
    DEFAULT_SAFETY_NOTE,
    Mission,
    MissionPack,
    MissionValidationError,
    PackRequest,
    validate_missions,
)
from app.weather import format_weather_note

logger = logging.getLogger(__name__)

@dataclass
class GenerationResult:
    pack: MissionPack
    first_attempt_valid_json: bool
    first_attempt_safe: bool
    attempts_used: int


def _prompt(request: PackRequest) -> str:
    weather = request.weather_note.strip() or "not provided"
    setting_guidance = {
        "park": "Notice open sky, leaf patterns, shadows, and sounds from a comfortable spot.",
        "neighborhood": "Notice colors, shapes, visible letters or numbers, and nearby sounds from a safe spot.",
        "garden": "Notice leaf outlines, flower colors, plant patterns, and garden sounds without picking anything.",
    }[request.setting]
    age_guidance: dict[AgeBand, str] = {
        "10-13": (
            "Create short mini-investigations: compare or classify things, notice a pattern, "
            "and state a simple observation."
        ),
        "14-17": (
            "Create multi-step field challenges: pose a quick question, compare observations, "
            "and reach a brief conclusion supported by what was seen or heard."
        ),
        "18-20": (
            "Create rigorous, independent observation challenges: use a systematic comparison "
            "or count, then distinguish direct observations from inferences."
        ),
    }[request.age_band]
    mission_count = {10: 3, 20: 4, 30: 5}[request.time_limit_min]
    return f"""Create an age-appropriate outdoor observation safari.
Return JSON only, with exactly this shape:
{{"missions":[{{"id":1,"type":"find_shapes","text":"...","est_minutes":3}}]}}

Choose 3 to 5 missions only from these activity types:
find_shapes, find_colors, count_things, listen_for_sounds, texture_hunt,
look_up_sky, find_numbers_or_letters, nature_pattern_hunt, gentle_movement.
Do not invent new activity types. Make every mission suitable for age group {request.age_band}.
Setting: {request.setting}. Time budget: at most {request.time_limit_min} minutes total.
Season: {request.season}. Adult-entered weather note: {weather}.
Choose exactly {mission_count} missions. {setting_guidance} {age_guidance}
Make the missions and wording specific to the setting, age group, season, and weather.
Use a varied mix of activity types; do not repeat a type in this pack. Do not reuse
generic mission wording. Keep each mission text to one short sentence of no more
than 160 characters. Keep eyes open. Do not feel, touch, pick, collect, or move
objects; for texture_hunt, describe textures by sight only. Eyes must remain open
throughout every mission; never tell anyone to close or shut their eyes. Only use
looking, listening, counting, or gentle movement.
Never mention roads, streets, traffic, water, climbing, strangers, private property,
touching animals, eating plants, screens, phones, GPS, maps, or cameras. Do not ask
anyone to collect, touch, or taste anything. IDs must be sequential from 1. Minutes
must be positive integers totaling no more than {request.time_limit_min}. Do not
output a safety note; the app adds age-appropriate safety guidance."""


def _make_pack(
    request: PackRequest,
    missions: list[Mission],
    generation_note: str | None = None,
) -> MissionPack:
    return MissionPack(
        pack_id=str(uuid.uuid4()),
        setting=request.setting,
        time_limit_min=request.time_limit_min,
        age_band=request.age_band,
        weather_note=format_weather_note(request.weather_note, request.season),
        missions=missions,
        closing="Great work! Now put the phone away and keep exploring.",
        generation_note=generation_note,
    )


def _backup_pack(request: PackRequest, reason: str) -> MissionPack:
    fallback_activities: dict[str, list[tuple[ActivityType, str]]] = {
        "park": [
            ("nature_pattern_hunt", "From where you are, spot a repeating pattern in nature."),
            ("listen_for_sounds", "Pause and notice two different sounds nearby."),
            ("look_up_sky", "Look up and find a shape in the clouds or sky."),
            ("find_colors", "Notice three colors around you."),
            ("count_things", "Count five things you can see without moving away."),
        ],
        "neighborhood": [
            ("find_colors", "Notice three different colors from your safe spot."),
            ("find_numbers_or_letters", "Spot a number or letter without going closer."),
            ("listen_for_sounds", "Pause and notice two different sounds nearby."),
            ("find_shapes", "Find three different shapes from where you are."),
            ("count_things", "Count five things you can see without moving away."),
        ],
        "garden": [
            ("find_shapes", "Look from where you are at three leaf or flower shapes."),
            ("nature_pattern_hunt", "Notice a repeating pattern among the plants."),
            ("find_colors", "Find three colors in the garden without removing any plants."),
            ("listen_for_sounds", "Pause and notice two different sounds nearby."),
            ("count_things", "Count five things you can see without moving away."),
        ],
    }
    durations = {
        10: [3, 3, 3],
        20: [4, 5, 5, 4],
        30: [5, 6, 6, 6, 5],
    }[request.time_limit_min]
    age_guidance = {
        "10-13": " Compare two examples and describe one detail.",
        "14-17": " Compare examples and support one pattern with evidence.",
        "18-20": " Compare systematically and separate observation from inference.",
    }[request.age_band]
    safety_note = (
        ADULT_SAFETY_NOTE if request.age_band == "18-20" else DEFAULT_SAFETY_NOTE
    )
    fallback_activities = fallback_activities[request.setting]
    missions = [
        Mission(
            id=index,
            type=activity_type,
            text=f"{text}{age_guidance}",
            est_minutes=durations[index - 1],
            safety_note=safety_note,
        )
        for index, (activity_type, text) in enumerate(fallback_activities[: len(durations)], start=1)
    ]
    logger.warning("Using a hand-written backup pack: %s", reason)
    return _make_pack(
        request,
        missions,
        generation_note=(
            "Gemma did not return a usable pack this time. Showing a safe backup instead."
        ),
    )


def generate_pack(
    request: PackRequest,
    provider: ModelProvider,
    max_attempts: int = 3,
) -> GenerationResult:
    if max_attempts <= 0:
        raise ValueError("max_attempts must be greater than zero.")

    prompt = _prompt(request)
    first_attempt_valid_json = False
    first_attempt_safe = False
    last_error = "No response was generated."
    attempts_used = 0

    for attempt in range(1, max_attempts + 1):
        attempts_used = attempt
        try:
            raw_response = provider.generate(prompt)
        except ProviderError as exc:
            last_error = str(exc)
            logger.error("Local model request failed: %s", exc)
            break

        if attempt == 1:
            try:
                json.loads(raw_response)
                first_attempt_valid_json = True
            except json.JSONDecodeError:
                first_attempt_valid_json = False

        try:
            missions = validate_missions(
                raw_response,
                request.time_limit_min,
                request.age_band,
            )
        except MissionValidationError as exc:
            last_error = str(exc)
            logger.warning("Rejected model output on attempt %d: %s", attempt, exc)
            prompt = (
                f"{prompt}\n\n"
                f"Your previous draft was rejected: {last_error} "
                "Regenerate the entire pack and correct this issue in every mission. "
                "Follow all safety restrictions exactly."
            )
            continue

        if attempt == 1:
            first_attempt_safe = True
        return GenerationResult(
            pack=_make_pack(request, missions),
            first_attempt_valid_json=first_attempt_valid_json,
            first_attempt_safe=first_attempt_safe,
            attempts_used=attempt,
        )

    return GenerationResult(
        pack=_backup_pack(request, last_error),
        first_attempt_valid_json=first_attempt_valid_json,
        first_attempt_safe=first_attempt_safe,
        attempts_used=attempts_used,
    )
