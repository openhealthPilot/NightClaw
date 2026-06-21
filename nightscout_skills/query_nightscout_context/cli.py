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

from nightscout_skills.query_nightscout_context.processor import build_agent_query
from nightscout_skills.utils.errors import InvalidDateRangeError
from nightscout_skills.utils.serialization import to_jsonable
from nightscout_skills.utils.time import parse_date_range


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch explicit NightClaw context for an AI agent.")
    parser.add_argument("--mode", required=True, choices=["glucose", "treatments", "loop", "context"])
    parser.add_argument("--date-start", required=True, help="Inclusive ISO-8601 start timestamp")
    parser.add_argument("--date-end", required=True, help="Exclusive ISO-8601 end timestamp")
    parser.add_argument("--question", help="Optional user question for response metadata")
    parser.add_argument("--detail", choices=["brief", "standard", "full"], default="standard")
    parser.add_argument("--output", help="Optional path to write JSON output")
    args = parser.parse_args()

    try:
        parse_date_range(args.date_start, args.date_end)
    except (InvalidDateRangeError, ValueError) as exc:
        parser.error(str(exc))

    response = build_agent_query(
        mode=args.mode,
        date_start=args.date_start,
        date_end=args.date_end,
        question=args.question,
        detail=args.detail,
    )
    rendered = json.dumps(to_jsonable(response), indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
