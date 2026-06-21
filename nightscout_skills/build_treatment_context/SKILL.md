---
name: build-treatment-context
description: Build treatment context from Nightscout therapy events. Use when asked for insulin, carbs, boluses, temp basal, temporary targets, or treatment metrics.
---

# Build Treatment Context

## Quick start

Run from the installed `nightscout_skills` skill directory. Date range is optional and defaults to the last 7 days. Add `--detailed` for a treatment-by-treatment view. The CLI automatically loads Nightscout credentials from `.env`, so no explicit `source` or absolute `PYTHONPATH` is needed.

```bash
uv run build_treatment_context/cli.py --date-start <date_start> --date-end <date_end> --detailed
```

Examples:

```bash
uv run build_treatment_context/cli.py
uv run build_treatment_context/cli.py --date-start 2026-02-08T15:00:00+00:00 --date-end 2026-02-10T20:00:00+00:00
uv run build_treatment_context/cli.py --date-start 2026-02-10T15:00:00+00:00 --date-end 2026-02-10T20:00:00+00:00 --detailed
```
