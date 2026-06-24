from __future__ import annotations

from datetime import datetime, timedelta

from .models import (
    BolusEvent,
    InsulinOverview,
    ProfileSnapshot,
    RawTreatment,
    RawTreatmentWindow,
    TempBasalEvent,
    TreatmentDetail,
    TreatmentDetails,
    TreatmentEvent,
)
from .profiles import active_profile, basal_rate_at, normalize_profiles
from .time import FIVE_MINUTES, ensure_tz, in_half_open_window, parse_iso


def treatment_timestamp(treatment: RawTreatment) -> str | None:
    return treatment.timestamp or treatment.created_at


def build_temp_basal_events(raw_treatments: list[RawTreatment], tz_name: str | None = None) -> list[TempBasalEvent]:
    events: list[TempBasalEvent] = []
    for treatment in raw_treatments:
        if treatment.event_type != "Temp Basal":
            continue
        timestamp = treatment_timestamp(treatment)
        if timestamp is None or treatment.rate is None or treatment.duration is None:
            continue
        start = parse_iso(timestamp, tz_name)
        if tz_name:
            start = ensure_tz(start, tz_name)
        events.append(
            TempBasalEvent(
                start=start,
                end=start + timedelta(minutes=float(treatment.duration)),
                rate=float(treatment.rate),
            )
        )
    events.sort(key=lambda item: item.start)
    return events


def temp_basal_at(temp_events: list[TempBasalEvent], when: datetime) -> float | None:
    for event in reversed(temp_events):
        if event.start <= when < event.end:
            return event.rate
    return None


def basal_rate_with_temp(profiles: list[ProfileSnapshot], temp_events: list[TempBasalEvent], when: datetime) -> float:
    snapshot = active_profile(profiles, when)
    temp = temp_basal_at(temp_events, when)
    return basal_rate_at(snapshot, when) if temp is None else temp


def calculate_basal(
    date_start: datetime,
    date_end: datetime,
    profiles: list[ProfileSnapshot],
    temp_events: list[TempBasalEvent],
) -> float:
    total = 0.0
    current = date_start
    while current < date_end:
        next_tick = min(current + FIVE_MINUTES, date_end)
        hours = (next_tick - current).total_seconds() / 3600
        total += basal_rate_with_temp(profiles, temp_events, current) * hours
        current = next_tick
    return total


def calculate_bolus(raw_treatments: list[RawTreatment]) -> tuple[float, list[BolusEvent]]:
    total = 0.0
    boluses: list[BolusEvent] = []
    for treatment in raw_treatments:
        if not treatment.insulin:
            continue
        timestamp = treatment_timestamp(treatment)
        if not timestamp:
            continue
        boluses.append(BolusEvent(timestamp=parse_iso(timestamp).isoformat(), insulin_amount=float(treatment.insulin)))
        total += float(treatment.insulin)
    boluses.sort(key=lambda item: item.timestamp)
    return total, boluses


def treatment_details(raw_treatments: list[RawTreatment]) -> TreatmentDetails:
    cleaned: list[TreatmentDetail] = []
    for treatment in raw_treatments:
        timestamp = treatment_timestamp(treatment)
        if not timestamp:
            continue
        cleaned.append(
            TreatmentDetail(
                timestamp=parse_iso(timestamp).isoformat(),
                event_type=treatment.event_type,
                amount=treatment.amount,
                rate=treatment.rate,
                duration=treatment.duration,
                carbs=treatment.carbs,
                insulin=treatment.insulin,
            )
        )
    return TreatmentDetails(treatments=sorted(cleaned, key=lambda item: item.timestamp))


def extract_treatment_events(
    raw_treatments: list[RawTreatment],
    start: datetime,
    end: datetime,
    field: str,
    tz_name: str,
) -> list[TreatmentEvent]:
    events: list[TreatmentEvent] = []
    for treatment in raw_treatments:
        amount = getattr(treatment, field)
        timestamp = treatment_timestamp(treatment)
        if not amount or not timestamp:
            continue
        when = ensure_tz(parse_iso(timestamp, tz_name), tz_name)
        if in_half_open_window(when, start, end, tz_name):
            events.append(TreatmentEvent(date=when, amount=float(amount)))
    events.sort(key=lambda item: item.date)
    return events


def generate_insulin_overview(raw_window: RawTreatmentWindow, profiles: list[ProfileSnapshot]) -> InsulinOverview:
    temp_events = build_temp_basal_events(raw_window.raw_treatments)
    total_basal = calculate_basal(raw_window.date_start, raw_window.date_end, profiles, temp_events)
    total_bolus, boluses = calculate_bolus(raw_window.raw_treatments)
    insulin_type = next((item.insulin_type for item in raw_window.raw_treatments if item.insulin_type), "Fiasp")
    return InsulinOverview(
        insulin_type=insulin_type,
        total_insulin=round(total_basal + total_bolus, 2),
        bolus_insulin=round(total_bolus, 2),
        basal_insulin=round(total_basal, 2),
        boluses=boluses,
    )


def normalize_profiles_for_insulin(raw_profiles, fallback_tz: str) -> list[ProfileSnapshot]:
    return normalize_profiles(raw_profiles, fallback_tz)
