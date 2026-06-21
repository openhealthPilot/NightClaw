# /// script
# dependencies = ["pydantic>=2.7", "python-dotenv>=1.0", "requests>=2.31"]
# ///
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from nightscout_skills.build_loop_context.pipeline import build_loopalyzer_dataset
from nightscout_skills.utils.client import NightscoutClient
from nightscout_skills.utils.models import LoopalyzerOptions
from nightscout_skills.utils.serialization import to_jsonable
from nightscout_skills.utils.time import parse_iso


def main() -> None:
    parser = argparse.ArgumentParser(description="Build Loop-derived context data from Nightscout APIs.")
    parser.add_argument("--date-start", required=True, help="Inclusive ISO-8601 start timestamp")
    parser.add_argument("--date-end", required=True, help="Exclusive ISO-8601 end timestamp")
    parser.add_argument("--no-predictions", action="store_true", help="Skip prediction extraction")
    parser.add_argument("--time-shift", action="store_true", help="Enable meal-based time shifting for multi-day ranges")
    parser.add_argument("--meal-min-carbs", type=float, default=0.0)
    parser.add_argument("--meal-window-start", default="06:00")
    parser.add_argument("--meal-window-end", default="23:30")
    parser.add_argument("--output", help="Optional path to write the JSON dataset")
    args = parser.parse_args()

    dataset = build_loopalyzer_dataset(
        client=NightscoutClient.from_env(),
        date_start=parse_iso(args.date_start),
        date_end=parse_iso(args.date_end),
        options=LoopalyzerOptions(
            include_predictions=not args.no_predictions,
            enable_time_shift=args.time_shift,
            meal_min_carbs=args.meal_min_carbs,
            meal_window_start=args.meal_window_start,
            meal_window_end=args.meal_window_end,
        ),
    )
    rendered = json.dumps(to_jsonable(dataset), indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
