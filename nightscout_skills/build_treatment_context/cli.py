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

from nightscout_skills.build_treatment_context.processor import gather_treatments
from nightscout_skills.utils.serialization import to_jsonable


def main() -> None:
    parser = argparse.ArgumentParser(description="Build treatment context from Nightscout therapy events.")
    parser.add_argument("--date-start", type=str)
    parser.add_argument("--date-end", type=str)
    parser.add_argument("--detailed", action="store_true")
    parser.add_argument("--output", type=str, help="Optional path to write JSON output")
    args = parser.parse_args()

    rendered = json.dumps(
        to_jsonable(gather_treatments(args.date_start, args.date_end, args.detailed)),
        indent=2,
    )
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
