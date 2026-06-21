# Weekly NightClaw Review

Task:
Run a 7-day NightClaw diabetes pattern review and produce an evidence-backed Markdown report focused on recurring signals, not single-day noise.

Repository root:
`<NIGHTCLAW_REPOSITORY_ROOT>`

Timezone:
`Europe/Warsaw`

Date window:
Use the last 7 complete local calendar days ending today at midnight.

- `date_start` = 7 days before today at `00:00:00` in `Europe/Warsaw`
- `date_end` = today at `00:00:00` in `Europe/Warsaw`
- `week_end_date` = yesterday's local date as `YYYY-MM-DD`

Create this output directory:

```bash
reports/weekly/<week_end_date>
```

Collect data:

```bash
cd <NIGHTCLAW_REPOSITORY_ROOT>

uv run nightscout_skills/query_nightscout_context/cli.py \
  --mode context \
  --date-start "<WEEK_START_ISO>" \
  --date-end "<TODAY_START_ISO>" \
  --question "Weekly review of recurring glucose, treatments, insulin, basal, carbs, Loop context, diet and exercise-relevant patterns." \
  --detail standard \
  --output "reports/weekly/<week_end_date>/agent_context.json"

uv run nightscout_skills/build_treatment_context/cli.py \
  --date-start "<WEEK_START_ISO>" \
  --date-end "<TODAY_START_ISO>" \
  --output "reports/weekly/<week_end_date>/insulin_overview.json"
```

If either command fails, stop and write a short failure report to:

```bash
reports/weekly/<week_end_date>/weekly_report.md
```

Use the generated JSON files as evidence. If a field is missing or sparse, say so instead of guessing.

Produce:

```bash
reports/weekly/<week_end_date>/weekly_report.md
```

Report structure:

1. Executive Summary
- 4-8 bullets focused on patterns repeated across multiple days.
- Explicitly distinguish recurring patterns from one-off anomalies.
- Include data quality caveats.

2. Week At A Glance
- Date range, data coverage, total insulin if available, basal/bolus split if available.
- Summarize glucose average, min/max, recurring high/low time blocks, and notable variability.

3. Recurring Glucose Patterns
- Overnight drift patterns.
- Morning/breakfast patterns.
- Lunch/afternoon patterns.
- Dinner/evening patterns.
- Repeated lows, rebounds, highs, or delayed drops.
- Call out how many days support each pattern.

4. Recurring Treatment And Insulin Patterns
- Repeated carb/bolus/SMB/temp basal/temporary target timing.
- Repeated relationships between IOB, COB, basal, and glucose movement.
- Repeated post-meal response patterns.
- Repeated correction over-response or under-response patterns when evidence supports it.

5. Settings And Dosing-Strategy Review Candidates
Analyze the week for patterns that may indicate the user should review current diabetes settings or habits. Cover:

- basal profile by time block
- insulin sensitivity factor / correction factor
- insulin-to-carb ratio by meal period
- bolus timing / pre-bolus timing
- carb counting accuracy
- meal composition and delayed absorption
- exercise timing and delayed glucose effects
- temporary targets or temp basal usage

For each candidate issue, provide:

- observed evidence from the data
- number of days supporting the pattern
- why the pattern may matter
- which setting or behavior it relates to
- confidence level: low, medium, or high
- what additional data would confirm or weaken the hypothesis
- a concrete review question for the user

Do not output exact new basal rates, insulin doses, insulin sensitivity values, or carb-ratio values. Do not say "change X to Y." Instead, say what recurring pattern the current data suggests reviewing and why.

Acceptable phrasing:

- "This repeated breakfast rise may be worth reviewing in relation to breakfast carb ratio, pre-bolus timing, or breakfast composition."
- "The recurring overnight rise is consistent with a possible basal mismatch in this time block, but confirm against additional weeks before making changes."
- "The repeated late post-meal drop may suggest reviewing bolus timing, carb absorption, or correction strength."
- "Repeated activity-adjacent drops may suggest reviewing exercise timing, preparation, or temporary target strategy."

Avoid:

- "Increase basal from X to Y."
- "Change ISF to X."
- "Use N units next time."
- "Eat exactly N grams before exercise."

6. Diet And Exercise Insights
- Identify meal patterns worth comparing more carefully.
- Suggest logging improvements that would make next week's review more precise.
- Identify exercise-adjacent glucose patterns if the data supports them.
- Do not prescribe insulin changes.

7. Top Follow-Up Questions
- Provide 5-8 concrete questions for the user to answer or track next week.
- Prioritize questions that would confirm or weaken the highest-confidence patterns.

Rules:

- Ground every major claim in the JSON data.
- Do not invent meals, exercise, symptoms, or intent.
- Distinguish observed facts from hypotheses.
- Do not output exact dosing changes.
- Do not tell the user to change insulin settings directly.
- Use clear, practical language.
- Prefer recurring multi-day evidence over single-day anomalies.
- End with: "This is an observational review for pattern-finding, not medical advice or dosing guidance."
