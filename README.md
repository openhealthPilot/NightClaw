# NightClaw

NightClaw is an experimental toolkit for retrieving personal Nightscout data, shaping it into structured context, and making that context usable by AI agents.

It includes domain-specific data builders for glucose, treatments, and Loop-derived time series, plus an agent-facing query skill that lets an agent request the exact data mode and time window it needs.

This project is independent and is not affiliated with, endorsed by, or connected to the original Nightscout project.

NightClaw is not approved medical software and must not be used to make medical decisions, treatment decisions, dosing decisions, or other health-related decisions. The Nightscout integration and AI-agent workflow are experimental features only.

## Configuration

Create a local `.env` file from the example configuration:

```sh
cp .env.example .env
```

Then update the values for your Nightscout instance:

- `NIGHTSCOUT_BASE_URL`: the base URL for your personal Nightscout site.
- `NIGHTSCOUT_API_KEY`: an API key for accessing your Nightscout data.

Keep `.env` private. It may contain sensitive credentials and should not be committed.

## Project Layout

```text
nightscout_skills/
  build_glucose_context/
  build_treatment_context/
  build_loop_context/
  query_nightscout_context/
  utils/
tests/
cron_jobs/
  daily_nightclaw_review.md
  weekly_nightclaw_review.md
```

The `build-*` skills produce domain-specific datasets. The `query-nightscout-context` skill is the preferred AI-agent entrypoint when the agent already knows the time window and data mode.

## Skills

### `build-glucose-context`

Builds glucose context from Nightscout SGV data.

```sh
uv run nightscout_skills/build_glucose_context/cli.py \
  --date-start "2026-06-19T00:00:00+02:00" \
  --date-end "2026-06-20T00:00:00+02:00" \
  --output glucose_context.json
```

### `build-treatment-context`

Builds treatment context from Nightscout therapy events. Default output is an insulin overview; add `--detailed` for treatment-by-treatment rows.

```sh
uv run nightscout_skills/build_treatment_context/cli.py \
  --date-start "2026-06-19T00:00:00+02:00" \
  --date-end "2026-06-20T00:00:00+02:00" \
  --output treatment_context.json
```

```sh
uv run nightscout_skills/build_treatment_context/cli.py \
  --date-start "2026-06-19T00:00:00+02:00" \
  --date-end "2026-06-20T00:00:00+02:00" \
  --detailed \
  --output treatment_details.json
```

### `build-loop-context`

Builds Loop-derived context from Nightscout treatments, SGVs, profiles, and device status. It emits 5-minute SGV, basal, temp basal delta, IOB, COB, and prediction series.

```sh
uv run nightscout_skills/build_loop_context/cli.py \
  --date-start "2026-06-19T00:00:00+02:00" \
  --date-end "2026-06-20T00:00:00+02:00" \
  --output loop_context.json
```

### `query-nightscout-context`

Fetches explicit structured Nightscout context for an AI agent. The caller must provide the mode and ISO date range. This skill does not infer intent, route by keywords, or parse natural-language dates.

Supported modes:

- `glucose`: glucose values and glucose summaries.
- `treatments`: therapy events only: carbs, bolus/SMB insulin, temp basal, and temporary targets.
- `loop`: Loop-derived 5-minute SGV, IOB, COB, basal, temp basal delta, and prediction series.
- `context`: joined glucose, treatment, and loop-series data for temporal reasoning.

```sh
uv run nightscout_skills/query_nightscout_context/cli.py \
  --mode context \
  --date-start "2026-06-19T00:00:00+02:00" \
  --date-end "2026-06-20T00:00:00+02:00" \
  --question "What happened after lunch yesterday?" \
  --detail standard \
  --output agent_context.json
```

## Agent Cron Jobs

NightClaw includes prompt files for scheduled AI-agent reviews:

- `cron_jobs/daily_nightclaw_review.md`: reviews the previous full local day.
- `cron_jobs/weekly_nightclaw_review.md`: reviews the last 7 complete local days.

These files are intended to be used as OpenClaw or similar scheduled-agent prompts. The agent should read the prompt, compute the date window, run the listed NightClaw commands, and write reports under:

```text
reports/daily/<report_date>/
reports/weekly/<week_end_date>/
```

Suggested schedules:

```cron
15 6 * * *   # daily review
30 7 * * 0   # weekly review
```

If your agent platform supports file-backed prompts, configure the jobs to read:

```text
<NIGHTCLAW_REPOSITORY_ROOT>/cron_jobs/daily_nightclaw_review.md
<NIGHTCLAW_REPOSITORY_ROOT>/cron_jobs/weekly_nightclaw_review.md
```

If it requires pasted prompts, paste the contents of the corresponding file into the scheduled job.

## Testing

Run the full test suite:

```sh
uv run pytest
```

The pytest configuration in `pyproject.toml` points tests at `tests` and adds the repository root to `pythonpath`.

## Notes For Agent Use

- Agents should prefer `query-nightscout-context` for user questions.
- Agents must choose `mode`, `date_start`, and `date_end` before calling the query skill.
- Use `build-*` skills for direct domain-specific exports or lower-level debugging.
- All generated insights should be treated as observational pattern-finding, not medical advice or dosing guidance.
