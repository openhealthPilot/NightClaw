from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from .errors import InvalidDateRangeError

DEFAULT_RANGE_DAYS = 7
NIGHTSCOUT_DATE_FORMAT = "%Y-%m-%dT%H:%M"
FIVE_MINUTES = timedelta(minutes=5)
BINS_PER_DAY = 288
UTC = ZoneInfo("UTC")
DEFAULT_LOCAL_TZ = "Europe/Warsaw"


def parse_iso(value: str, default_tz: str | None = None) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(default_tz) if default_tz else UTC)
    return dt


def parse_nightscout_datetime(value: str, default_tz: str | None = None) -> datetime:
    return parse_iso(value, default_tz).astimezone(ZoneInfo(default_tz or DEFAULT_LOCAL_TZ))


def parse_date_range(
    date_start: str | None = None,
    date_end: str | None = None,
    default_days: int = DEFAULT_RANGE_DAYS,
    default_tz: str | None = None,
) -> tuple[datetime, datetime]:
    end = parse_iso(date_end, default_tz) if date_end else datetime.now(timezone.utc)
    start = parse_iso(date_start, default_tz) if date_start else end - timedelta(days=default_days)
    if start >= end:
        raise InvalidDateRangeError("date_start must be earlier than date_end")
    return start, end


def ensure_tz(dt: datetime, tz_name: str) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=ZoneInfo(tz_name))
    return dt.astimezone(ZoneInfo(tz_name))


def in_half_open_window(dt: datetime, start: datetime, end: datetime, tz_name: str | None = None) -> bool:
    if tz_name:
        dt = ensure_tz(dt, tz_name)
        start = ensure_tz(start, tz_name)
        end = ensure_tz(end, tz_name)
    return start <= dt < end


def day_start(day: date | datetime, tz_name: str) -> datetime:
    if isinstance(day, datetime):
        day = day.date()
    return datetime.combine(day, time.min, tzinfo=ZoneInfo(tz_name))


def day_end(day: date | datetime, tz_name: str) -> datetime:
    return day_start(day, tz_name) + timedelta(days=1)


def date_range_days(start: datetime, end: datetime, tz_name: str) -> list[date]:
    current = day_start(start, tz_name).date()
    stop = day_start(end - timedelta(microseconds=1), tz_name).date()
    days: list[date] = []
    while current <= stop:
        days.append(current)
        current += timedelta(days=1)
    return days


def parse_clock(clock_value: str) -> tuple[int, int]:
    hours, minutes = clock_value.split(":")
    return int(hours), int(minutes)


def nightscout_range_params(field: str, start: datetime, end: datetime, count: int = 0) -> dict[str, str]:
    return {
        "count": str(count),
        f"find[{field}][$gte]": start.strftime(NIGHTSCOUT_DATE_FORMAT),
        f"find[{field}][$lt]": end.strftime(NIGHTSCOUT_DATE_FORMAT),
    }
