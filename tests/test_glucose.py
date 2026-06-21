from nightscout_skills.build_glucose_context.processor import preprocess_entries
from nightscout_skills.utils.models import RawGlucoseEntry


def test_preprocess_entries_filters_sorts_and_averages():
    summary = preprocess_entries(
        [
            RawGlucoseEntry(type="mbg", sgv=999, dateString="2026-02-08T00:00:00+00:00"),
            RawGlucoseEntry(type="sgv", sgv=120, dateString="2026-02-08T00:05:00+00:00"),
            RawGlucoseEntry(type="sgv", sgv=None, dateString="2026-02-08T00:10:00+00:00"),
            RawGlucoseEntry(type="sgv", sgv=100, dateString="2026-02-08T00:00:00+00:00"),
            RawGlucoseEntry(type="sgv", sgv=140),
        ]
    )

    assert summary.average_glucose == 110
    assert [value.glucose for value in summary.glucose_values] == [100, 120]
