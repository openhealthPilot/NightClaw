from __future__ import annotations

from datetime import date, datetime, timedelta
from statistics import mean
from typing import Any

from nightscout_skills.build_loop_context.pipeline import build_loopalyzer_dataset
from nightscout_skills.build_glucose_context.processor import preprocess_entries
from nightscout_skills.utils.client import NightscoutClient
from nightscout_skills.utils.errors import InvalidDateRangeError
from nightscout_skills.utils.insulin import treatment_timestamp
from nightscout_skills.utils.models import (
    AgentDailySummary,
    AgentDataQuality,
    AgentEvidenceRef,
    AgentQueryDetail,
    AgentQueryMode,
    AgentQueryRequest,
    AgentQueryResponse,
    AgentQueryWindow,
    AgentSeriesPoint,
    AgentSeriesSlice,
    AgentTherapyEvent,
    LoopalyzerDataset,
    LoopalyzerOptions,
    RawDeviceStatus,
    RawGlucoseEntry,
    RawProfileEntry,
    RawTreatment,
)
from nightscout_skills.utils.profiles import default_timezone
from nightscout_skills.utils.time import (
    FIVE_MINUTES,
    UTC,
    date_range_days,
    day_start,
    ensure_tz,
    in_half_open_window,
    parse_date_range,
    parse_iso,
)

GLUCOSE_UNIT = "mg/dL"
INSULIN_UNIT = "U"
CARB_UNIT = "g"
BASAL_RATE_UNIT = "U/hr"

THERAPY_EVENT_SOURCE = "nightscout_treatments"
GLUCOSE_SOURCE = "nightscout_sgvs"
LOOP_SOURCE = "loopalyzer"

EXCLUDED_TREATMENT_TYPES = {"note", "exercise", "site change"}
LOOP_CHANNELS = {
    "sgv_bins": ("sgv", GLUCOSE_UNIT),
    "basal_bins": ("basal", BASAL_RATE_UNIT),
    "temp_basal_delta_bins": ("temp_basal_delta", BASAL_RATE_UNIT),
    "iob_bins": ("iob", INSULIN_UNIT),
    "cob_bins": ("cob", CARB_UNIT),
    "prediction_bins": ("prediction", GLUCOSE_UNIT),
}


def build_agent_query(
    *,
    mode: AgentQueryMode,
    date_start: str,
    date_end: str,
    question: str | None = None,
    detail: AgentQueryDetail = "standard",
    client: NightscoutClient | None = None,
) -> AgentQueryResponse:
    client = client or NightscoutClient.from_env()
    raw_profiles = client.fetch_profiles()
    tz_name = default_timezone(raw_profiles)
    start, end = _parse_required_window(date_start, date_end, tz_name)

    raw_sgvs: list[RawGlucoseEntry] = []
    raw_treatments: list[RawTreatment] = []
    raw_devicestatus: list[RawDeviceStatus] = []
    loop_dataset: LoopalyzerDataset | None = None

    if mode in {"glucose", "context"}:
        raw_sgvs = _filter_raw_sgvs(client.fetch_sgvs(start, end), start, end, tz_name)
    if mode in {"treatments", "context"}:
        raw_treatments = _filter_raw_treatments(client.fetch_treatments(start, end), start, end, tz_name)
    if mode == "context":
        raw_devicestatus = _filter_raw_devicestatus(client.fetch_devicestatus(start, end), start, end, tz_name)
    if mode in {"loop", "context"}:
        loop_dataset = build_loopalyzer_dataset(
            client=client,
            date_start=start,
            date_end=end,
            options=LoopalyzerOptions(include_predictions=True),
            raw_profiles=raw_profiles,
            raw_treatments=raw_treatments if mode == "context" else None,
            raw_devicestatus=raw_devicestatus if mode == "context" else None,
            raw_sgvs=raw_sgvs if mode == "context" else None,
        )
        tz_name = loop_dataset.timezone
        start = ensure_tz(start, tz_name)
        end = ensure_tz(end, tz_name)

    glucose_points = _glucose_series_points(raw_sgvs, tz_name) if raw_sgvs else []
    therapy_events = _canonical_therapy_events(raw_treatments, tz_name) if raw_treatments else []
    loop_slices = _loop_series_slices(loop_dataset, start, end, tz_name) if loop_dataset else []

    series_slices: list[AgentSeriesSlice] = []
    if mode == "glucose" and detail != "brief":
        series_slices.append(_glucose_series_slice(glucose_points))
    if mode in {"loop", "context"} and detail != "brief":
        series_slices.extend(loop_slices)
    if mode == "context" and detail == "full":
        series_slices.append(_glucose_series_slice(glucose_points))

    daily_summaries = _daily_summaries(
        start=start,
        end=end,
        tz_name=tz_name,
        glucose_points=glucose_points,
        therapy_events=therapy_events,
        series_slices=series_slices,
    )
    data_quality = _data_quality(
        mode=mode,
        start=start,
        end=end,
        raw_profiles=raw_profiles,
        raw_sgvs=raw_sgvs,
        raw_treatments=raw_treatments,
        loop_dataset=loop_dataset,
        series_slices=series_slices,
    )
    evidence_refs = _evidence_refs(mode, therapy_events, series_slices)
    briefing = _briefing(
        mode=mode,
        start=start,
        end=end,
        glucose_points=glucose_points,
        therapy_events=therapy_events,
        series_slices=series_slices,
    )

    return AgentQueryResponse(
        request=AgentQueryRequest(question=question, mode=mode, detail=detail),
        window=AgentQueryWindow(date_start=start.isoformat(), date_end=end.isoformat(), timezone=tz_name),
        data_used=_data_used(mode),
        briefing=briefing,
        daily_summaries=daily_summaries,
        events=therapy_events if mode in {"treatments", "context"} else [],
        series_slices=series_slices,
        data_quality=data_quality,
        evidence_refs=evidence_refs,
    )


def _parse_required_window(date_start: str, date_end: str, tz_name: str) -> tuple[datetime, datetime]:
    try:
        start, end = parse_date_range(date_start, date_end, default_tz=tz_name)
    except ValueError as exc:
        raise InvalidDateRangeError(f"Invalid ISO date range: {exc}") from exc
    if start >= end:
        raise InvalidDateRangeError("date_start must be earlier than date_end")
    return ensure_tz(start, tz_name), ensure_tz(end, tz_name)


def _data_used(mode: AgentQueryMode) -> list[str]:
    if mode == "glucose":
        return ["glucose"]
    if mode == "treatments":
        return ["treatments"]
    if mode == "loop":
        return ["loop_series"]
    return ["glucose", "treatments", "loop_series"]


def _filter_raw_sgvs(
    entries: list[RawGlucoseEntry],
    start: datetime,
    end: datetime,
    tz_name: str,
) -> list[RawGlucoseEntry]:
    return [
        entry
        for entry in entries
        if (timestamp := entry.date_string or entry.sys_time)
        and in_half_open_window(parse_iso(timestamp, tz_name), start, end, tz_name)
    ]


def _filter_raw_treatments(
    entries: list[RawTreatment],
    start: datetime,
    end: datetime,
    tz_name: str,
) -> list[RawTreatment]:
    return [
        entry
        for entry in entries
        if (timestamp := treatment_timestamp(entry))
        and in_half_open_window(parse_iso(timestamp, tz_name), start, end, tz_name)
    ]


def _filter_raw_devicestatus(
    entries: list[RawDeviceStatus],
    start: datetime,
    end: datetime,
    tz_name: str,
) -> list[RawDeviceStatus]:
    filtered = []
    for entry in entries:
        timestamp = entry.created_at or entry.timestamp
        if timestamp and in_half_open_window(parse_iso(timestamp, tz_name), start, end, tz_name):
            filtered.append(entry)
            continue
        if entry.mills is not None:
            when = datetime.fromtimestamp(entry.mills / 1000, tz=UTC)
            if in_half_open_window(when, start, end, tz_name):
                filtered.append(entry)
    return filtered


def _timestamp_fields(when: datetime, tz_name: str) -> dict[str, Any]:
    local = ensure_tz(when, tz_name)
    return {
        "timestamp_utc": local.astimezone(UTC).isoformat(),
        "timestamp_local": local.isoformat(),
        "day": local.date().isoformat(),
        "minutes_since_midnight": local.hour * 60 + local.minute,
    }


def _coerce_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _raw_treatment_payload(treatment: RawTreatment) -> dict[str, Any]:
    return treatment.model_dump(mode="python", by_alias=True)


def _canonical_therapy_events(raw_treatments: list[RawTreatment], tz_name: str) -> list[AgentTherapyEvent]:
    pending: list[AgentTherapyEvent] = []
    for index, treatment in enumerate(raw_treatments):
        raw_event_type = treatment.event_type
        normalized_type = (raw_event_type or "").strip().lower()
        if normalized_type in EXCLUDED_TREATMENT_TYPES:
            continue
        timestamp = treatment_timestamp(treatment)
        if not timestamp:
            continue
        when = ensure_tz(parse_iso(timestamp, tz_name), tz_name)
        payload = _raw_treatment_payload(treatment)

        if normalized_type == "temp basal" and treatment.rate is not None and treatment.duration is not None:
            pending.append(
                _therapy_event(
                    raw_index=index,
                    event_type="temp_basal",
                    raw_event_type=raw_event_type,
                    when=when,
                    tz_name=tz_name,
                    rate=float(treatment.rate),
                    rate_unit=BASAL_RATE_UNIT,
                    duration_minutes=float(treatment.duration),
                )
            )

        if "temporary target" in normalized_type or "temp target" in normalized_type:
            target_bottom = _coerce_float(
                payload.get("targetBottom") or payload.get("target_bottom") or payload.get("targetMin")
            )
            target_top = _coerce_float(payload.get("targetTop") or payload.get("target_top") or payload.get("targetMax"))
            target = _coerce_float(payload.get("target") or payload.get("glucose"))
            amount = target
            if amount is None and target_bottom is not None and target_top is not None:
                amount = (target_bottom + target_top) / 2
            pending.append(
                _therapy_event(
                    raw_index=index,
                    event_type="temporary_target",
                    raw_event_type=raw_event_type,
                    when=when,
                    tz_name=tz_name,
                    amount=amount,
                    unit=GLUCOSE_UNIT if amount is not None else None,
                    duration_minutes=_coerce_float(payload.get("duration")),
                    metadata={
                        key: value
                        for key, value in {
                            "target_bottom": target_bottom,
                            "target_top": target_top,
                            "reason": payload.get("reason"),
                        }.items()
                        if value is not None
                    },
                )
            )

        if treatment.carbs:
            pending.append(
                _therapy_event(
                    raw_index=index,
                    event_type="carbs",
                    raw_event_type=raw_event_type,
                    when=when,
                    tz_name=tz_name,
                    amount=float(treatment.carbs),
                    unit=CARB_UNIT,
                )
            )

        if treatment.insulin:
            pending.append(
                _therapy_event(
                    raw_index=index,
                    event_type="smb" if "smb" in normalized_type else "bolus",
                    raw_event_type=raw_event_type,
                    when=when,
                    tz_name=tz_name,
                    amount=float(treatment.insulin),
                    unit=INSULIN_UNIT,
                )
            )

    pending.sort(key=lambda event: (event.timestamp_local, event.event_type, event.raw_event_type or ""))
    return [
        event.model_copy(update={"id": f"event-{index + 1:04d}", "evidence_ref": f"event-{index + 1:04d}"})
        for index, event in enumerate(pending)
    ]


def _therapy_event(
    *,
    raw_index: int,
    event_type: str,
    raw_event_type: str | None,
    when: datetime,
    tz_name: str,
    amount: float | None = None,
    unit: str | None = None,
    rate: float | None = None,
    rate_unit: str | None = None,
    duration_minutes: float | None = None,
    metadata: dict[str, Any] | None = None,
) -> AgentTherapyEvent:
    return AgentTherapyEvent(
        id=f"pending-{raw_index}",
        event_type=event_type,
        raw_event_type=raw_event_type,
        amount=amount,
        unit=unit,
        rate=rate,
        rate_unit=rate_unit,
        duration_minutes=duration_minutes,
        source=THERAPY_EVENT_SOURCE,
        evidence_ref=f"pending-{raw_index}",
        metadata=metadata or {},
        **_timestamp_fields(when, tz_name),
    )


def _glucose_series_points(raw_sgvs: list[RawGlucoseEntry], tz_name: str) -> list[AgentSeriesPoint]:
    summary = preprocess_entries(raw_sgvs)
    points: list[AgentSeriesPoint] = []
    for item in summary.glucose_values:
        when = ensure_tz(parse_iso(item.timestamp, tz_name), tz_name)
        points.append(AgentSeriesPoint(value=float(item.glucose), **_timestamp_fields(when, tz_name)))
    points.sort(key=lambda point: point.timestamp_local)
    return points


def _glucose_series_slice(points: list[AgentSeriesPoint]) -> AgentSeriesSlice:
    return AgentSeriesSlice(
        channel="glucose",
        unit=GLUCOSE_UNIT,
        resolution_minutes=5,
        points=points,
        summary=_point_summary(points),
    )


def _loop_series_slices(
    dataset: LoopalyzerDataset,
    start: datetime,
    end: datetime,
    tz_name: str,
) -> list[AgentSeriesSlice]:
    slices: list[AgentSeriesSlice] = []
    days = [date.fromisoformat(day) for day in dataset.days]
    for source_channel, rows in dataset.series.items():
        channel, unit = LOOP_CHANNELS.get(source_channel, (source_channel, None))
        points: list[AgentSeriesPoint] = []
        for day_index, day in enumerate(days):
            local_day_start = day_start(day, tz_name)
            for bin_index, row in enumerate(rows):
                when = local_day_start + timedelta(minutes=bin_index * 5)
                if not (start <= when < end):
                    continue
                value = row.values[day_index] if day_index < len(row.values) else None
                points.append(AgentSeriesPoint(value=value, **_timestamp_fields(when, tz_name)))
        slices.append(
            AgentSeriesSlice(
                channel=channel,
                unit=unit,
                resolution_minutes=5,
                points=points,
                summary=_point_summary(points),
            )
        )
    return slices


def _numeric_values(points: list[AgentSeriesPoint]) -> list[float]:
    return [float(point.value) for point in points if point.value is not None]


def _point_summary(points: list[AgentSeriesPoint]) -> dict[str, Any]:
    values = _numeric_values(points)
    return {
        "point_count": len(points),
        "value_count": len(values),
        "null_count": len(points) - len(values),
        "average": mean(values) if values else None,
        "min": min(values) if values else None,
        "max": max(values) if values else None,
    }


def _daily_summaries(
    *,
    start: datetime,
    end: datetime,
    tz_name: str,
    glucose_points: list[AgentSeriesPoint],
    therapy_events: list[AgentTherapyEvent],
    series_slices: list[AgentSeriesSlice],
) -> list[AgentDailySummary]:
    summaries: list[AgentDailySummary] = []
    for day in date_range_days(start, end, tz_name):
        day_text = day.isoformat()
        day_glucose = [point for point in glucose_points if point.day == day_text]
        day_events = [event for event in therapy_events if event.day == day_text]
        series = {
            item.channel: _point_summary([point for point in item.points if point.day == day_text])
            for item in series_slices
            if item.channel != "glucose"
        }
        summaries.append(
            AgentDailySummary(
                day=day_text,
                glucose=_point_summary(day_glucose) if day_glucose else {},
                therapy=_therapy_summary(day_events) if day_events else {},
                series=series,
            )
        )
    return summaries


def _therapy_summary(events: list[AgentTherapyEvent]) -> dict[str, Any]:
    insulin_units = sum(event.amount or 0 for event in events if event.unit == INSULIN_UNIT)
    carbs_grams = sum(event.amount or 0 for event in events if event.event_type == "carbs")
    temp_basal_minutes = sum(event.duration_minutes or 0 for event in events if event.event_type == "temp_basal")
    by_type: dict[str, int] = {}
    for event in events:
        by_type[event.event_type] = by_type.get(event.event_type, 0) + 1
    return {
        "event_count": len(events),
        "events_by_type": by_type,
        "insulin_units": insulin_units,
        "carbs_grams": carbs_grams,
        "temp_basal_minutes": temp_basal_minutes,
    }


def _data_quality(
    *,
    mode: AgentQueryMode,
    start: datetime,
    end: datetime,
    raw_profiles: list[RawProfileEntry],
    raw_sgvs: list[RawGlucoseEntry],
    raw_treatments: list[RawTreatment],
    loop_dataset: LoopalyzerDataset | None,
    series_slices: list[AgentSeriesSlice],
) -> AgentDataQuality:
    source_counts = {"profiles": len(raw_profiles)}
    if mode in {"glucose", "context"}:
        source_counts["sgvs"] = len(raw_sgvs)
    if mode in {"treatments", "context"}:
        source_counts["treatments"] = len(raw_treatments)
    if loop_dataset is not None:
        source_counts.update({f"loop_{key}": value for key, value in loop_dataset.raw_counts.items()})

    expected_bins = max(1, int((end - start).total_seconds() // FIVE_MINUTES.total_seconds()))
    coverage: dict[str, Any] = {
        "expected_5_min_bins": expected_bins,
        "series": {item.channel: item.summary for item in series_slices},
    }
    if raw_sgvs:
        coverage["glucose_reading_ratio"] = len(raw_sgvs) / expected_bins

    warnings: list[str] = []
    if not raw_profiles:
        warnings.append("No profile records were returned; timezone may be a fallback.")
    if mode in {"glucose", "context"} and not raw_sgvs:
        warnings.append("No glucose records were returned for the selected window.")
    if mode in {"treatments", "context"} and not raw_treatments:
        warnings.append("No treatment records were returned for the selected window.")

    return AgentDataQuality(source_counts=source_counts, coverage=coverage, warnings=warnings)


def _evidence_refs(
    mode: AgentQueryMode,
    therapy_events: list[AgentTherapyEvent],
    series_slices: list[AgentSeriesSlice],
) -> list[AgentEvidenceRef]:
    refs: list[AgentEvidenceRef] = []
    if mode in {"glucose", "context"}:
        refs.append(AgentEvidenceRef(id="glucose-source", source=GLUCOSE_SOURCE, kind="source"))
    if mode in {"treatments", "context"}:
        refs.append(AgentEvidenceRef(id="treatments-source", source=THERAPY_EVENT_SOURCE, kind="source"))
        refs.extend(
            AgentEvidenceRef(
                id=event.evidence_ref,
                source=THERAPY_EVENT_SOURCE,
                kind="event",
                reference=event.timestamp_local,
            )
            for event in therapy_events
        )
    if mode in {"loop", "context"}:
        refs.append(AgentEvidenceRef(id="loop-source", source=LOOP_SOURCE, kind="source"))
        refs.extend(
            AgentEvidenceRef(
                id=f"series-{item.channel}",
                source=LOOP_SOURCE,
                kind="series",
                reference=item.channel,
            )
            for item in series_slices
            if item.channel != "glucose"
        )
    return refs


def _briefing(
    *,
    mode: AgentQueryMode,
    start: datetime,
    end: datetime,
    glucose_points: list[AgentSeriesPoint],
    therapy_events: list[AgentTherapyEvent],
    series_slices: list[AgentSeriesSlice],
) -> dict[str, Any]:
    briefing: dict[str, Any] = {
        "mode": mode,
        "window_hours": (end - start).total_seconds() / 3600,
    }
    if glucose_points:
        briefing["glucose"] = _point_summary(glucose_points)
    if therapy_events:
        briefing["therapy"] = _therapy_summary(therapy_events)
    if series_slices:
        briefing["series"] = {
            "channels": [item.channel for item in series_slices],
            "points_by_channel": {item.channel: len(item.points) for item in series_slices},
        }
    return briefing
