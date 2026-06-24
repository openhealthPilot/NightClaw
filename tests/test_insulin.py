from nightscout_skills.build_treatment_context.processor import preprocess_treatments
from nightscout_skills.utils.insulin import build_temp_basal_events, calculate_basal, extract_treatment_events, temp_basal_at
from nightscout_skills.utils.models import ProfileSnapshot, RawProfileEntry, RawTreatment, RawTreatmentWindow
from nightscout_skills.utils.time import parse_iso


def profile(rate=1.0):
    return [
        RawProfileEntry(
            defaultProfile="default",
            startDate="2026-02-01T00:00:00+00:00",
            store={
                "default": {
                    "timezone": "UTC",
                    "dia": 6,
                    "basal": [{"time": "00:00", "value": rate}],
                    "carbratio": [],
                    "sens": [],
                }
            },
        )
    ]


def test_insulin_overview_includes_bolus_basal_and_temp_basal():
    raw_window = RawTreatmentWindow(
        date_start=parse_iso("2026-02-08T00:00:00+00:00"),
        date_end=parse_iso("2026-02-08T01:00:00+00:00"),
        raw_treatments=[
            RawTreatment(eventType="Temp Basal", timestamp="2026-02-08T00:00:00+00:00", rate=2.0, duration=60),
            RawTreatment(eventType="Correction Bolus", created_at="2026-02-08T00:15:00+00:00", insulin=2.0, insulinType="Lyumjev"),
        ],
    )

    overview = preprocess_treatments(raw_window, profile(), detailed=False)

    assert overview.insulin_type == "Lyumjev"
    assert overview.basal_insulin == 2.0
    assert overview.bolus_insulin == 2.0
    assert overview.total_insulin == 4.0
    assert overview.boluses[0].insulin_amount == 2.0


def test_detailed_treatments_are_sorted():
    raw_window = RawTreatmentWindow(
        date_start=parse_iso("2026-02-08T00:00:00+00:00"),
        date_end=parse_iso("2026-02-08T01:00:00+00:00"),
        raw_treatments=[
            RawTreatment(eventType="Meal Bolus", created_at="2026-02-08T00:30:00+00:00", insulin=1.0),
            RawTreatment(eventType="Carb Correction", created_at="2026-02-08T00:10:00+00:00", carbs=15.0),
        ],
    )

    details = preprocess_treatments(raw_window, profile(), detailed=True)

    assert [item.event_type for item in details.treatments] == ["Carb Correction", "Meal Bolus"]


def test_basal_calculation_prorates_partial_5_minute_windows():
    total = calculate_basal(
        parse_iso("2026-02-08T00:00:00+00:00"),
        parse_iso("2026-02-08T00:01:00+00:00"),
        [
            ProfileSnapshot(
                start_date=parse_iso("2026-02-01T00:00:00+00:00"),
                profile_name="default",
                timezone="UTC",
                dia=6,
                basal=[{"time": "00:00", "value": 1.0}],
                carbratio=[],
                sens=[],
            )
        ],
        [],
    )

    assert round(total, 4) == 0.0167


def test_extract_treatment_events_uses_inclusive_start_exclusive_end():
    events = extract_treatment_events(
        [
            RawTreatment(eventType="Carb Correction", created_at="2026-02-08T00:00:00+00:00", carbs=10),
            RawTreatment(eventType="Carb Correction", created_at="2026-02-08T00:30:00+00:00", carbs=15),
            RawTreatment(eventType="Carb Correction", created_at="2026-02-08T01:00:00+00:00", carbs=20),
        ],
        parse_iso("2026-02-08T00:00:00+00:00"),
        parse_iso("2026-02-08T01:00:00+00:00"),
        "carbs",
        "UTC",
    )

    assert [event.amount for event in events] == [10, 15]


def test_temp_basal_at_uses_most_recent_overlapping_temp_basal():
    events = build_temp_basal_events(
        [
            RawTreatment(eventType="Temp Basal", timestamp="2026-02-08T00:00:00+00:00", rate=0.0, duration=120),
            RawTreatment(eventType="Temp Basal", timestamp="2026-02-08T00:30:00+00:00", rate=2.0, duration=30),
        ]
    )

    assert temp_basal_at(events, parse_iso("2026-02-08T00:45:00+00:00")) == 2.0


def test_basal_calculation_treats_overlapping_temp_basals_as_replacements():
    temp_events = build_temp_basal_events(
        [
            RawTreatment(eventType="Temp Basal", timestamp="2026-02-08T20:30:00+00:00", rate=1.5, duration=60),
            RawTreatment(eventType="Temp Basal", timestamp="2026-02-08T21:00:00+00:00", rate=1.0, duration=30),
        ]
    )

    total = calculate_basal(
        parse_iso("2026-02-08T20:30:00+00:00"),
        parse_iso("2026-02-08T21:30:00+00:00"),
        [
            ProfileSnapshot(
                start_date=parse_iso("2026-02-01T00:00:00+00:00"),
                profile_name="default",
                timezone="UTC",
                dia=6,
                basal=[{"time": "00:00", "value": 0.0}],
                carbratio=[],
                sens=[],
            )
        ],
        temp_events,
    )

    assert round(total, 2) == 1.25
