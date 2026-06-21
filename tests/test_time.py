from datetime import timezone

import pytest

from nightscout_skills.utils.errors import InvalidDateRangeError
from nightscout_skills.utils.time import parse_date_range, parse_iso


def test_parse_iso_handles_z_suffix():
    dt = parse_iso("2026-02-08T10:15:00Z")

    assert dt.tzinfo is not None
    assert dt.utcoffset().total_seconds() == 0


def test_parse_iso_adds_default_timezone_to_naive_values():
    dt = parse_iso("2026-02-08T10:15:00", "Europe/Warsaw")

    assert dt.tzinfo is not None
    assert dt.hour == 10


def test_parse_date_range_rejects_invalid_order():
    with pytest.raises(InvalidDateRangeError):
        parse_date_range("2026-02-09T00:00:00+00:00", "2026-02-08T00:00:00+00:00")


def test_parse_date_range_defaults_start_to_last_seven_days():
    start, end = parse_date_range(date_end="2026-02-08T00:00:00+00:00")

    assert end.tzinfo == timezone.utc
    assert (end - start).days == 7
