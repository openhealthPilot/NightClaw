from __future__ import annotations

import statistics

from nightscout_skills.utils.client import NightscoutClient
from nightscout_skills.utils.models import GlucoseSummary, GlucoseValue, RawGlucoseEntry
from nightscout_skills.utils.time import in_half_open_window, parse_date_range, parse_iso

DEFAULT_COUNT = 999999


def get_entries(
    date_start: str | None = None,
    date_end: str | None = None,
    count: int = DEFAULT_COUNT,
    client: NightscoutClient | None = None,
) -> list[RawGlucoseEntry]:
    start, end = parse_date_range(date_start, date_end)
    client = client or NightscoutClient.from_env(timeout=10)
    entries = client.fetch_sgvs(start, end, count=count)
    return [
        entry
        for entry in entries
        if (timestamp := entry.date_string or entry.sys_time)
        and in_half_open_window(parse_iso(timestamp), start, end)
    ]


def preprocess_entries(raw_entries: list[RawGlucoseEntry]) -> GlucoseSummary:
    values: list[int] = []
    cleaned: list[GlucoseValue] = []
    for entry in raw_entries:
        if entry.type != "sgv" or entry.sgv is None:
            continue
        timestamp = entry.date_string or entry.sys_time
        if not timestamp:
            continue
        values.append(entry.sgv)
        cleaned.append(GlucoseValue(timestamp=parse_iso(timestamp).isoformat(), glucose=entry.sgv))

    return GlucoseSummary(
        average_glucose=statistics.mean(values) if values else None,
        glucose_values=sorted(cleaned, key=lambda item: item.timestamp),
    )


def gather_glucose_data(
    date_start: str | None = None,
    date_end: str | None = None,
    client: NightscoutClient | None = None,
) -> GlucoseSummary:
    return preprocess_entries(get_entries(date_start=date_start, date_end=date_end, client=client))
