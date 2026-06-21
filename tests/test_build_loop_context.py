from nightscout_skills.build_loop_context.pipeline import build_loopalyzer_dataset, compute_time_shifts, get_cobs, get_sgvs
from nightscout_skills.utils.models import LoopalyzerOptions, RawDeviceStatus, RawGlucoseEntry, RawProfileEntry, RawTreatment, TreatmentEvent
from nightscout_skills.utils.time import parse_iso


class FakeLoopClient:
    def fetch_profiles(self):
        return [
            RawProfileEntry(
                defaultProfile="default",
                startDate="2026-02-01T00:00:00+00:00",
                store={
                    "default": {
                        "timezone": "UTC",
                        "dia": 6,
                        "basal": [{"timeAsSeconds": 0, "value": 1.0}],
                        "carbratio": [],
                        "sens": [],
                    }
                },
            )
        ]

    def fetch_treatments(self, start, end, count=0):
        return [
            RawTreatment(eventType="Temp Basal", created_at="2026-02-08T00:00:00+00:00", rate=2.0, duration=60),
            RawTreatment(eventType="Carb Correction", created_at="2026-02-08T00:10:00+00:00", carbs=20.0),
            RawTreatment(eventType="Correction Bolus", created_at="2026-02-08T00:15:00+00:00", insulin=1.0),
        ]

    def fetch_devicestatus(self, start, end, count=0):
        return [
            RawDeviceStatus(
                created_at="2026-02-08T00:20:00+00:00",
                openaps={"iob": {"iob": 0.8}, "suggested": {"COB": 12, "predBGs": {"COB": [110, 111]}}},
            )
        ]

    def fetch_sgvs(self, start, end, count=0):
        return [RawGlucoseEntry(type="sgv", sgv=100, dateString="2026-02-08T00:02:00+00:00")]


def test_build_loopalyzer_dataset_uses_shared_client_shape_and_temp_basal():
    dataset = build_loopalyzer_dataset(
        FakeLoopClient(),
        parse_iso("2026-02-08T00:00:00+00:00"),
        parse_iso("2026-02-08T01:00:00+00:00"),
        LoopalyzerOptions(),
    )

    assert dataset.timezone == "UTC"
    assert dataset.raw_counts == {"profiles": 1, "treatments": 3, "devicestatus": 1, "sgvs": 1}
    assert dataset.series["sgv_bins"][0].values[0] == 100.0
    assert dataset.series["basal_bins"][0].values[0] == 2.0
    assert dataset.series["temp_basal_delta_bins"][0].values[0] == 1.0
    assert dataset.series["iob_bins"][4].values[0] == 0.8
    assert dataset.series["cob_bins"][4].values[0] == 12.0


def test_compute_time_shifts_aligns_first_meals():
    shifts = compute_time_shifts(
        [
            TreatmentEvent(date=parse_iso("2026-02-08T08:00:00+00:00"), amount=20),
            TreatmentEvent(date=parse_iso("2026-02-09T09:00:00+00:00"), amount=20),
        ],
        [parse_iso("2026-02-08T00:00:00+00:00").date(), parse_iso("2026-02-09T00:00:00+00:00").date()],
        6.0,
        "UTC",
        LoopalyzerOptions(enable_time_shift=True, meal_min_carbs=10),
    )

    assert shifts["enabled"] is True
    assert shifts["time_shifts"] == [30, -30]


def test_get_cobs_accepts_loop_cob_object_payloads():
    bins = get_cobs(
        [
            RawDeviceStatus(
                created_at="2026-02-08T00:20:00+00:00",
                loop={"cob": {"cob": 17}},
            )
        ],
        [parse_iso("2026-02-08T00:00:00+00:00").date()],
        [],
        "UTC",
    )

    assert bins[4][1][0] == 17.0


def test_get_sgvs_includes_readings_on_bin_start_and_excludes_next_bin():
    bins = get_sgvs(
        [
            RawGlucoseEntry(type="sgv", sgv=100, dateString="2026-02-08T00:00:00+00:00"),
            RawGlucoseEntry(type="sgv", sgv=120, dateString="2026-02-08T00:05:00+00:00"),
        ],
        [parse_iso("2026-02-08T00:00:00+00:00").date()],
        "UTC",
    )

    assert bins[0][1][0] == 100.0
    assert bins[1][1][0] == 120.0
