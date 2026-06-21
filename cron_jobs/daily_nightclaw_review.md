# Daily NightClaw Review

Task:
Run yesterday's NightClaw diabetes data review and produce a concise, evidence-backed Markdown report.

Repository root:
`<NIGHTCLAW_REPOSITORY_ROOT>`

Timezone:
`Europe/Warsaw`

Date window:
Use the previous full local calendar day.

- `date_start` = yesterday at `00:00:00` in `Europe/Warsaw`
- `date_end` = today at `00:00:00` in `Europe/Warsaw`
- `report_date` = yesterday's local date as `YYYY-MM-DD`

Create this output directory:

```bash
reports/daily/<report_date>
```

Collect data:

```bash
cd <NIGHTCLAW_REPOSITORY_ROOT>

uv run nightscout_skills/query_nightscout_context/cli.py \
  --mode context \
  --date-start "<YESTERDAY_START_ISO>" \
  --date-end "<TODAY_START_ISO>" \
  --question "Daily review of glucose, treatments, insulin, basal, carbs, Loop context, diet and exercise-relevant patterns." \
  --detail standard \
  --output "reports/daily/<report_date>/agent_context.json"

uv run nightscout_skills/build_treatment_context/cli.py \
  --date-start "<YESTERDAY_START_ISO>" \
  --date-end "<TODAY_START_ISO>" \
  --output "reports/daily/<report_date>/insulin_overview.json"
```

If either command fails, stop and write a short failure report to:

```bash
reports/daily/<report_date>/daily_report.md
```

Use the generated JSON files as evidence. If a field is missing or sparse, say so instead of guessing.

Produce:

```bash
reports/daily/<report_date>/daily_report.md
```

Report structure:

1. Executive Summary
- 3-6 bullets with the most important patterns.
- Include data quality caveats.

2. Glucose Patterns
- Average, min, max, notable high/low periods.
- Overnight, morning, afternoon, evening patterns.
- Identify post-meal rises, late drops, rebounds, or prolonged flat/high/low periods.

3. Insulin And Treatment Review
- Total insulin, basal insulin, bolus insulin when available.
- Carbs, boluses, SMBs, temp basal activity, temporary targets.
- Explain timing relationships between insulin, carbs, IOB, COB, basal, and glucose movement.

4. Settings And Dosing-Strategy Review
Analyze yesterday's data for patterns that may indicate the user should review current diabetes settings or habits. Cover:

- basal profile by time block
- insulin sensitivity factor / correction factor
- insulin-to-carb ratio
- bolus timing / pre-bolus timing
- carb counting accuracy
- meal composition and delayed absorption
- exercise timing and delayed glucose effects
- temporary targets or temp basal usage

For each candidate issue, provide:

- observed evidence from the data
- why the pattern may matter
- which setting or behavior it relates to
- confidence level: low, medium, or high
- what additional data would confirm or weaken the hypothesis
- a concrete review question for the user

Do not output exact new basal rates, insulin doses, insulin sensitivity values, or carb-ratio values. Do not say "change X to Y." Instead, say what pattern the current data suggests reviewing and why.

Acceptable phrasing:

- "This pattern may be worth reviewing in relation to the breakfast carb ratio."
- "The overnight rise is consistent with a possible basal mismatch, but one night is not enough to conclude that."
- "The late post-meal drop may suggest reviewing bolus timing, carb absorption, or correction strength."
- "Exercise may have contributed to increased insulin sensitivity later in the day."

Avoid:

- "Increase basal from X to Y."
- "Change ISF to X."
- "Use N units next time."
- "Eat exactly N grams before exercise."

5. Diet And Exercise Insights
- Suggest practical, non-dosing experiments:
  - meal logging improvements
  - comparing similar meals
  - noting fat/protein-heavy meals
  - timing walks or exercise relative to meals
  - watching for delayed lows after activity
- Do not prescribe insulin changes.

Rules:

- Ground every major claim in the JSON data.
- Do not invent meals, exercise, symptoms, or intent.
- Distinguish observed facts from hypotheses.
