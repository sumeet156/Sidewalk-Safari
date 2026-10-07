import argparse
import json
import re
import time
from difflib import SequenceMatcher

from app.generator import generate_pack
from app.providers.ollama import create_provider
from app.validator import MissionPack, PackRequest


def normalized_pack(pack: MissionPack) -> str:
    missions = [
        f"{mission.type} {mission.text.casefold()}"
        for mission in pack.missions
    ]
    return re.sub(r"[^a-z0-9 ]", " ", " ".join(missions)).strip()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure local safari-pack JSON validity, safety, variety, and latency."
    )
    parser.add_argument("--count", type=int, default=50)
    parser.add_argument("--setting", choices=["park", "neighborhood", "garden"], default="park")
    parser.add_argument("--time-limit", type=int, choices=[10, 20, 30], default=20)
    parser.add_argument("--age-band", choices=["10-13", "14-17", "18-20"], default="10-13")
    parser.add_argument("--season", choices=["spring", "summer", "autumn", "winter"], default="autumn")
    parser.add_argument("--weather-note", default="")
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count must be at least 1")

    request = PackRequest(
        setting=args.setting,
        time_limit_min=args.time_limit,
        age_band=args.age_band,
        season=args.season,
        weather_note=args.weather_note,
    )
    provider = create_provider()
    valid_json_count = 0
    first_try_safe_count = 0
    fallback_count = 0
    durations = []
    pack_texts = []

    for index in range(args.count):
        started = time.perf_counter()
        result = generate_pack(request, provider)
        durations.append(time.perf_counter() - started)
        valid_json_count += result.first_attempt_valid_json
        first_try_safe_count += result.first_attempt_safe
        fallback_count += result.pack.generation_note is not None
        pack_texts.append(normalized_pack(result.pack))
        print(f"Completed pack {index + 1}/{args.count}")

    distinct_count = 0
    for index, current in enumerate(pack_texts):
        near_duplicate = any(
            SequenceMatcher(None, current, previous).ratio() >= 0.85
            for previous in pack_texts[:index]
        )
        distinct_count += not near_duplicate

    report = {
        "packs": args.count,
        "valid_json_first_attempt_pct": round(100 * valid_json_count / args.count, 1),
        "safety_pass_first_attempt_pct": round(100 * first_try_safe_count / args.count, 1),
        "distinct_pack_pct": round(100 * distinct_count / args.count, 1),
        "near_duplicate_similarity_threshold": 0.85,
        "average_generation_seconds": round(sum(durations) / len(durations), 2),
        "model": getattr(provider, "model", "configured provider"),
        "fallback_packs": fallback_count,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
