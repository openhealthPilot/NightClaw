---
name: query-nightscout-context
description: Fetch explicit structured Nightscout context for an AI agent. Use when the agent already knows the ISO date range and whether it needs glucose, treatments, loop series, or joined context.
---

# Query Nightscout Context

Use this skill as the preferred AI-agent entrypoint for NightClaw data retrieval. The caller must choose the mode and ISO-8601 time window before invoking it. This skill does not infer intent, route by keywords, or parse natural-language dates.

## Quick start

Run from the installed `nightscout_skills` skill directory. The CLI automatically loads Nightscout credentials from `.env`, so no explicit `source` or absolute `PYTHONPATH` is needed.

```bash
uv run query_nightscout_context/cli.py \
  --mode glucose|treatments|loop|context \
  --date-start <iso datetime> \
  --date-end <iso datetime> \
  --question "<optional user question>" \
  --detail brief|standard|full
```

`--mode`, `--date-start`, and `--date-end` are required. `--detail` defaults to `standard`.

## Modes

- `glucose`: glucose values and glucose summaries for the selected window.
- `treatments`: therapy events only: carbs, bolus/SMB insulin, temp basal, and temporary targets. Notes, exercise, site changes, and annotation-only events are excluded.
- `loop`: 5-minute Loopalyzer-derived SGV, IOB, COB, basal, temp basal delta, and prediction series.
- `context`: joined glucose summaries, therapy events, and loop series for temporal reasoning.

## Output

The CLI emits `nightclaw.agent_query.v1` JSON with request metadata, normalized window, data used, briefing, daily summaries, canonical events, series slices, data quality, evidence refs, and safety metadata.

All outputs are observational only and are not for dosing, treatment, or medical-decision guidance.
