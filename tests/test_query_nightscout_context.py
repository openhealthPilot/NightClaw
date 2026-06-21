import subprocess
import sys
from pathlib import Path

from nightscout_skills.query_nightscout_context.processor import build_agent_query
from nightscout_skills.utils.models import RawDeviceStatus, RawGlucoseEntry, RawProfileEntry, RawTreatment

ROOT = Path(__file__).resolve().parents[1]


class FakeAgentClient:
    def __init__(self):
        self.calls = {"profiles": 0, "treatments": 0, "devicestatus": 0, "sgvs": 0}

    def fetch_profiles(self):
        self.calls["profiles"] += 1
        return [
            RawProfileEntry(
                defaultProfile="default",
                startDate="2026-02-08T00:00:00+00:00",
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
        self.calls["treatments"] += 1
        return [
            RawTreatment(eventType="Note", created_at="2026-02-08T00:01:00+00:00"),
            RawTreatment(eventType="Exercise", created_at="2026-02-08T00:02:00+00:00"),
            RawTreatment(eventType="Site Change", created_at="2026-02-08T00:03:00+00:00"),
            RawTreatment(eventType="Carb Correction", created_at="2026-02-08T00:10:00+00:00", carbs=20),
            RawTreatment(eventType="SMB", created_at="2026-02-08T00:15:00+00:00", insulin=0.3),
            RawTreatment(eventType="Correction Bolus", created_at="2026-02-08T00:20:00+00:00", insulin=1.2),
            RawTreatment(eventType="Temp Basal", created_at="2026-02-08T00:25:00+00:00", rate=2.0, duration=30),
            RawTreatment(
                eventType="Temporary Target",
                created_at="2026-02-08T00:30:00+00:00",
                duration=60,
                targetTop=120,
                targetBottom=100,
                reason="test",
            ),
            RawTreatment(eventType="Carb Correction", created_at="2026-02-08T01:00:00+00:00", carbs=99),
        ]

    def fetch_devicestatus(self, start, end, count=0):
        self.calls["devicestatus"] += 1
        return [
            RawDeviceStatus(
                created_at="2026-02-08T00:20:00+00:00",
                openaps={"iob": {"iob": 0.8}, "suggested": {"COB": 12, "predBGs": {"COB": [110, 111]}}},
            ),
            RawDeviceStatus(created_at="2026-02-08T01:00:00+00:00", openaps={"iob": {"iob": 9.9}}),
        ]

    def fetch_sgvs(self, start, end, count=0):
        self.calls["sgvs"] += 1
        return [
            RawGlucoseEntry(type="sgv", sgv=90, dateString="2026-02-08T00:00:00+00:00"),
            RawGlucoseEntry(type="sgv", sgv=100, dateString="2026-02-08T00:02:00+00:00"),
            RawGlucoseEntry(type="sgv", sgv=130, dateString="2026-02-08T00:07:00+00:00"),
            RawGlucoseEntry(type="mbg", sgv=999, dateString="2026-02-08T00:08:00+00:00"),
            RawGlucoseEntry(type="sgv", sgv=250, dateString="2026-02-08T01:00:00+00:00"),
        ]


def build(mode, detail="standard"):
    return build_agent_query(
        mode=mode,
        date_start="2026-02-08T00:00:00+00:00",
        date_end="2026-02-08T01:00:00+00:00",
        question="test question",
        detail=detail,
        client=FakeAgentClient(),
    )


def test_cli_requires_mode_before_fetching_data():
    result = subprocess.run(
        [
            sys.executable,
            "nightscout_skills/query_nightscout_context/cli.py",
            "--date-start",
            "2026-02-08T00:00:00+00:00",
            "--date-end",
            "2026-02-08T01:00:00+00:00",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "--mode" in result.stderr


def test_cli_requires_date_bounds_before_fetching_data():
    result = subprocess.run(
        [
            sys.executable,
            "nightscout_skills/query_nightscout_context/cli.py",
            "--mode",
            "glucose",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "--date-start" in result.stderr
    assert "--date-end" in result.stderr


def test_cli_rejects_invalid_date_range_before_fetching_data():
    result = subprocess.run(
        [
            sys.executable,
            "nightscout_skills/query_nightscout_context/cli.py",
            "--mode",
            "glucose",
            "--date-start",
            "2026-02-08T01:00:00+00:00",
            "--date-end",
            "2026-02-08T00:00:00+00:00",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "date_start must be earlier than date_end" in result.stderr


def test_glucose_mode_returns_glucose_summary_and_values():
    response = build("glucose")

    assert response.request.mode == "glucose"
    assert response.data_used == ["glucose"]
    assert response.briefing["glucose"]["average"] == 106.66666666666667
    assert response.series_slices[0].channel == "glucose"
    assert [point.value for point in response.series_slices[0].points] == [90.0, 100.0, 130.0]


def test_treatments_mode_excludes_annotation_only_events():
    response = build("treatments")

    assert [event.event_type for event in response.events] == [
        "carbs",
        "smb",
        "bolus",
        "temp_basal",
        "temporary_target",
    ]
    assert all(event.raw_event_type not in {"Note", "Exercise", "Site Change"} for event in response.events)
    assert response.events[-1].metadata == {"target_bottom": 100.0, "target_top": 120.0, "reason": "test"}


def test_loop_mode_returns_chronological_5_min_series_slices():
    response = build("loop")

    channels = [item.channel for item in response.series_slices]
    assert channels == ["sgv", "basal", "temp_basal_delta", "iob", "cob", "prediction"]
    sgv = response.series_slices[0]
    assert len(sgv.points) == 12
    assert sgv.points[0].timestamp_local == "2026-02-08T00:00:00+00:00"
    assert sgv.points[-1].timestamp_local == "2026-02-08T00:55:00+00:00"
    assert sgv.points[0].value == 90.0


def test_context_mode_joins_data_without_routing():
    response = build("context")

    assert response.request.mode == "context"
    assert response.request.question == "test question"
    assert response.data_used == ["glucose", "treatments", "loop_series"]
    assert len(response.events) == 5
    assert {item.channel for item in response.series_slices} == {
        "sgv",
        "basal",
        "temp_basal_delta",
        "iob",
        "cob",
        "prediction",
    }


def test_context_mode_fetches_each_nightscout_resource_once():
    client = FakeAgentClient()

    build_agent_query(
        mode="context",
        date_start="2026-02-08T00:00:00+00:00",
        date_end="2026-02-08T01:00:00+00:00",
        detail="standard",
        client=client,
    )

    assert client.calls == {"profiles": 1, "treatments": 1, "devicestatus": 1, "sgvs": 1}


def test_context_mode_filters_exact_end_records_from_events_and_glucose():
    response = build("context")

    assert all(event.amount != 99 for event in response.events)
    assert response.briefing["glucose"]["max"] == 130.0


def test_brief_detail_omits_dense_series_and_full_adds_glucose_series_to_context():
    brief = build("context", detail="brief")
    full = build("context", detail="full")

    assert brief.series_slices == []
    assert "glucose" in {item.channel for item in full.series_slices}
