---
name: build-loop-context
description: Build Loop-derived context datasets from Nightscout treatments, SGVs, profiles, and device status. Use when asked for glucose/IOB/COB/basal/prediction series, Loopalyzer-style exports, or meal-aligned multi-day Nightscout context.
---

# Build Loop Context

## Quick start

Run from the installed `nightscout_skills` skill directory. The CLI automatically loads Nightscout credentials from `.env`, so no explicit `source` or absolute `PYTHONPATH` is needed.

```bash
uv run build_loop_context/cli.py --date-start <date_start> --date-end <date_end>
```

Examples:

```bash
uv run build_loop_context/cli.py --date-start 2026-02-08T00:00:00+00:00 --date-end 2026-02-09T00:00:00+00:00
uv run build_loop_context/cli.py --date-start 2026-02-08T00:00:00+00:00 --date-end 2026-02-15T00:00:00+00:00 --time-shift --meal-min-carbs 10 --output loopalyzer.json
```

Temp basal series use active temp basal values when present; `temp_basal_delta_bins` records the delta against scheduled basal.
