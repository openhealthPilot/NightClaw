---
name: build-glucose-context
description: Build glucose context from Nightscout SGV data. Use when asked for glucose values, averages, trends, or glucose metrics.
---

# Build Glucose Context

## Quick start

Run from the installed `nightscout_skills` skill directory. Date range is optional and defaults to the last 7 days. The CLI automatically loads Nightscout credentials from `.env`, so no explicit `source` or absolute `PYTHONPATH` is needed.

```bash
uv run build_glucose_context/cli.py --date-start <date_start> --date-end <date_end>
```

Examples:

```bash
uv run build_glucose_context/cli.py
uv run build_glucose_context/cli.py --date-start 2026-02-08T15:00:00+00:00 --date-end 2026-02-10T20:00:00+00:00
```
