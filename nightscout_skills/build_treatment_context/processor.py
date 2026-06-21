from __future__ import annotations

from nightscout_skills.utils.client import NightscoutClient
from nightscout_skills.utils.insulin import (
    generate_insulin_overview,
    normalize_profiles_for_insulin,
    treatment_timestamp,
    treatment_details,
)
from nightscout_skills.utils.models import InsulinOverview, RawProfileEntry, RawTreatmentWindow, TreatmentDetails
from nightscout_skills.utils.profiles import default_timezone
from nightscout_skills.utils.time import in_half_open_window, parse_date_range, parse_iso


def get_profile(client: NightscoutClient | None = None) -> list[RawProfileEntry]:
    client = client or NightscoutClient.from_env(timeout=10)
    return client.fetch_profiles()


def get_treatments(
    date_start: str | None = None,
    date_end: str | None = None,
    count: int = 0,
    client: NightscoutClient | None = None,
) -> RawTreatmentWindow:
    start, end = parse_date_range(date_start, date_end)
    client = client or NightscoutClient.from_env(timeout=10)
    treatments = [
        treatment
        for treatment in client.fetch_treatments(start, end, count=count)
        if (timestamp := treatment_timestamp(treatment))
        and in_half_open_window(parse_iso(timestamp), start, end)
    ]
    return RawTreatmentWindow(raw_treatments=treatments, date_start=start, date_end=end)


def preprocess_treatments(
    raw_treatments: RawTreatmentWindow,
    raw_profiles: list[RawProfileEntry],
    detailed: bool = False,
) -> TreatmentDetails | InsulinOverview:
    if detailed:
        return treatment_details(raw_treatments.raw_treatments)
    tz_name = default_timezone(raw_profiles)
    profiles = normalize_profiles_for_insulin(raw_profiles, tz_name)
    return generate_insulin_overview(raw_treatments, profiles)


def gather_treatments(
    date_start: str | None = None,
    date_end: str | None = None,
    detailed: bool = False,
    client: NightscoutClient | None = None,
) -> TreatmentDetails | InsulinOverview:
    client = client or NightscoutClient.from_env(timeout=10)
    raw_treatments = get_treatments(date_start=date_start, date_end=date_end, client=client)
    return preprocess_treatments(raw_treatments, get_profile(client), detailed=detailed)
