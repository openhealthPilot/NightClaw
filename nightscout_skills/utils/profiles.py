from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import ProfileSnapshot, RawProfileEntry
from .time import parse_clock, parse_iso


def default_timezone(raw_profiles: list[RawProfileEntry], fallback_tz: str = "Europe/Warsaw") -> str:
    if not raw_profiles:
        return fallback_tz
    first_profile = raw_profiles[0]
    default_name = first_profile.default_profile
    default_store = first_profile.store.get(default_name or "", {})
    return str(default_store.get("timezone") or first_profile.timezone or fallback_tz)


def normalize_profiles(raw_profiles: list[RawProfileEntry], fallback_tz: str) -> list[ProfileSnapshot]:
    snapshots: list[ProfileSnapshot] = []
    for entry in raw_profiles:
        default_name = entry.default_profile
        if not entry.start_date:
            continue
        for profile_name, profile_data in entry.store.items():
            if profile_name != default_name:
                continue
            snapshots.append(
                ProfileSnapshot(
                    start_date=parse_iso(entry.start_date, fallback_tz),
                    profile_name=profile_name,
                    timezone=profile_data.get("timezone") or entry.timezone or fallback_tz,
                    dia=profile_data.get("dia"),
                    basal=list(profile_data.get("basal") or []),
                    carbratio=list(profile_data.get("carbratio") or []),
                    sens=list(profile_data.get("sens") or []),
                )
            )
    snapshots.sort(key=lambda item: item.start_date)
    return snapshots


def active_profile(profiles: list[ProfileSnapshot], when: datetime) -> ProfileSnapshot:
    if not profiles:
        raise ValueError("at least one profile snapshot is required")
    current = profiles[0]
    for profile in profiles:
        if profile.start_date <= when:
            current = profile
        else:
            break
    return current


def basal_entry_minutes(entry: dict[str, Any]) -> int:
    if entry.get("timeAsSeconds") is not None:
        return int(entry["timeAsSeconds"]) // 60
    if entry.get("time"):
        hours, minutes = parse_clock(str(entry["time"]))
        return hours * 60 + minutes
    return 0


def basal_rate_at(snapshot: ProfileSnapshot, when: datetime) -> float:
    minutes = when.hour * 60 + when.minute
    rate = float(snapshot.basal[-1]["value"]) if snapshot.basal else 0.0
    for entry in snapshot.basal:
        if minutes >= basal_entry_minutes(entry):
            rate = float(entry["value"])
        else:
            break
    return rate
