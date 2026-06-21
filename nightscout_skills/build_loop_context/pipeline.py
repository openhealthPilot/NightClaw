from __future__ import annotations

from datetime import date, datetime, timedelta
from math import floor
from statistics import mean
from typing import Any
from zoneinfo import ZoneInfo

from nightscout_skills.utils.client import NightscoutClient
from nightscout_skills.utils.errors import NightscoutResponseError
from nightscout_skills.utils.insulin import build_temp_basal_events, extract_treatment_events, temp_basal_at
from nightscout_skills.utils.models import (
    AveragePoint,
    LoopalyzerDataset,
    LoopalyzerOptions,
    Prediction,
    RawDeviceStatus,
    RawGlucoseEntry,
    RawProfileEntry,
    RawTreatment,
    SeriesPoint,
    TimeShiftSummary,
    TreatmentEvent,
)
from nightscout_skills.utils.profiles import active_profile, basal_rate_at, default_timezone, normalize_profiles
from nightscout_skills.utils.serialization import is_nan
from nightscout_skills.utils.time import (
    BINS_PER_DAY,
    FIVE_MINUTES,
    date_range_days,
    day_end,
    day_start,
    ensure_tz,
    in_half_open_window,
    parse_clock,
    parse_iso,
)

RISING_INTERPOLATION_GAP = 6
FALLING_INTERPOLATION_GAP = 24
INTERPOLATION_RATIO = 1.25


def get_empty_bins(reference_day: date, tz_name: str) -> list[list[Any]]:
    bins: list[list[Any]] = []
    dt = day_start(reference_day, tz_name)
    for _ in range(BINS_PER_DAY):
        bins.append([dt, []])
        dt += FIVE_MINUTES
    return bins


def get_nan_bins_for_days(days_to_show: list[date], tz_name: str) -> list[list[Any]]:
    bins = get_empty_bins(days_to_show[0], tz_name)
    for _ in days_to_show:
        add_array_to_bins(bins, [float("nan")] * BINS_PER_DAY)
    return bins


def add_array_to_bins(bins: list[list[Any]], values: list[float]) -> None:
    if len(bins) != BINS_PER_DAY or len(values) != BINS_PER_DAY:
        raise ValueError("bins and values must both contain 288 items")
    for index, value in enumerate(values):
        bins[index][1].append(value)


def can_interpolate(array: list[float], start: int, stop: int) -> bool:
    if array[stop] <= array[start] * INTERPOLATION_RATIO:
        return stop - start < FALLING_INTERPOLATION_GAP
    return stop - start < RISING_INTERPOLATION_GAP and array[start] != 0


def fill_nan_with_treatments(array: list[float], treatments: list[TreatmentEvent], tz_name: str) -> None:
    for treatment in treatments:
        local_dt = ensure_tz(treatment.date, tz_name)
        start_of_day = day_start(local_dt, tz_name)
        index = floor((local_dt - start_of_day).total_seconds() / 300)
        if index < 0 or index >= len(array) or not is_nan(array[index]):
            continue
        start = index
        stop = index
        while start >= 0 and is_nan(array[start]):
            start -= 1
        while stop < len(array) and is_nan(array[stop]):
            stop += 1
        interpolate = True if start < 0 or stop >= len(array) else can_interpolate(array, start, stop)
        if not interpolate:
            array[index] = treatment.amount


def interpolate_series(values: list[float], clamp_non_negative: bool = False) -> None:
    start = 0
    while start < len(values) and is_nan(values[start]):
        start += 1
    if start >= len(values):
        return
    stop = start + 1
    while stop < len(values):
        while stop < len(values) and is_nan(values[stop]):
            stop += 1
        if stop >= len(values):
            break
        if can_interpolate(values, start, stop):
            slope = (values[stop] - values[start]) / (stop - start)
            base = values[start]
            for x in range(stop - start):
                interpolated = slope * x + base
                values[start + x] = max(0.0, interpolated) if clamp_non_negative else interpolated
        start = stop
        stop += 1


def avg_bins(bins: list[list[Any]], exact_js_truthiness: bool = True) -> list[list[Any]]:
    output: list[list[Any]] = []
    for timestamp, values in bins:
        total = 0.0
        count = 0
        for value in values:
            if is_nan(value):
                continue
            if exact_js_truthiness and not value:
                continue
            total += value
            count += 1
        output.append([timestamp, total / count if count else float("nan")])
    return output


def time_shift_bins(bins: list[list[Any]], time_shifts: list[int]) -> None:
    for day_index, minutes in enumerate(time_shifts):
        if minutes == 0:
            continue
        shift = floor(minutes / 5)
        shifted = [float("nan")] * len(bins)
        if shift > 0:
            for index in range(BINS_PER_DAY - shift):
                shifted[index + shift] = bins[index][1][day_index]
        elif shift < 0:
            for index in range(BINS_PER_DAY + shift):
                shifted[index] = bins[index - shift][1][day_index]
        for index in range(BINS_PER_DAY):
            bins[index][1][day_index] = shifted[index]


def time_shift_single_bin(events: list[TreatmentEvent], time_shift_by_day: dict[date, int], tz_name: str) -> None:
    for event in events:
        local_dt = ensure_tz(event.date, tz_name)
        event.date = local_dt + timedelta(minutes=time_shift_by_day.get(local_dt.date(), 0))


def get_sgvs(entries: list[RawGlucoseEntry], days_to_show: list[date], tz_name: str) -> list[list[Any]]:
    bins = get_empty_bins(days_to_show[0], tz_name)
    normalized = []
    for record in entries:
        record_time = record.date_string or record.sys_time
        value = record.sgv if record.sgv is not None else record.glucose
        if record_time is None or value is None:
            continue
        normalized.append({"display_time": ensure_tz(parse_iso(record_time, tz_name), tz_name), "sgv": float(value)})
    normalized.sort(key=lambda item: item["display_time"])
    for day in days_to_show:
        values = [float("nan")] * BINS_PER_DAY
        from_dt = day_start(day, tz_name)
        to_dt = from_dt + FIVE_MINUTES
        for index in range(BINS_PER_DAY):
            found = next((item for item in normalized if from_dt <= item["display_time"] < to_dt), None)
            if found:
                values[index] = found["sgv"]
            from_dt += FIVE_MINUTES
            to_dt += FIVE_MINUTES
        add_array_to_bins(bins, values)
    return bins


def get_basals(days_to_show, profiles, temp_events, tz_name: str) -> list[list[Any]]:
    bins = get_empty_bins(days_to_show[0], tz_name)
    for day in days_to_show:
        values = [float("nan")] * BINS_PER_DAY
        dt = day_start(day, tz_name)
        for index in range(BINS_PER_DAY):
            basal = basal_rate_at(active_profile(profiles, dt), dt)
            temp = temp_basal_at(temp_events, dt)
            values[index] = basal if temp is None else temp
            dt += FIVE_MINUTES
        add_array_to_bins(bins, values)
    return bins


def get_temp_basal_deltas(days_to_show, profiles, temp_events, tz_name: str) -> list[list[Any]]:
    bins = get_empty_bins(days_to_show[0], tz_name)
    for day in days_to_show:
        values = [float("nan")] * BINS_PER_DAY
        dt = day_start(day, tz_name)
        for index in range(BINS_PER_DAY):
            basal = basal_rate_at(active_profile(profiles, dt), dt)
            temp = temp_basal_at(temp_events, dt)
            values[index] = 0.0 if temp is None else temp - basal
            dt += FIVE_MINUTES
        add_array_to_bins(bins, values)
    return bins


def _devicestatus_timestamp(entry: RawDeviceStatus, tz_name: str) -> datetime | None:
    timestamp = entry.created_at or entry.timestamp
    if timestamp:
        return ensure_tz(parse_iso(timestamp, tz_name), tz_name)
    if entry.mills is not None:
        return datetime.fromtimestamp(entry.mills / 1000, tz=ZoneInfo(tz_name))
    return None


def _glucose_timestamp(entry: RawGlucoseEntry, tz_name: str) -> datetime | None:
    timestamp = entry.date_string or entry.sys_time
    return ensure_tz(parse_iso(timestamp, tz_name), tz_name) if timestamp else None


def _treatment_timestamp(entry: RawTreatment, tz_name: str) -> datetime | None:
    timestamp = entry.created_at or entry.timestamp
    return ensure_tz(parse_iso(timestamp, tz_name), tz_name) if timestamp else None


def _filter_by_timestamp(entries, start: datetime, end: datetime, tz_name: str, timestamp_fn):
    return [
        entry
        for entry in entries
        if (timestamp := timestamp_fn(entry, tz_name)) and in_half_open_window(timestamp, start, end, tz_name)
    ]


def _extract_number(value: Any, keys: tuple[str, ...] = ()) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float | str):
        try:
            return float(value)
        except ValueError:
            return None
    if isinstance(value, dict):
        for key in keys:
            if key in value:
                extracted = _extract_number(value[key], keys)
                if extracted is not None:
                    return extracted
    return None


def _status_iob(entry: RawDeviceStatus) -> float | None:
    return _extract_number(entry.openaps.get("iob"), ("iob", "value", "amount"))


def _status_cob(entry: RawDeviceStatus) -> float | None:
    suggested = entry.openaps.get("suggested", {})
    cob = _extract_number(suggested.get("COB"), ("COB", "cob", "mealCOB", "value", "amount"))
    if cob is not None:
        return cob
    meal_cob = _extract_number(suggested.get("mealCOB"), ("mealCOB", "COB", "cob", "value", "amount"))
    if meal_cob is not None:
        return meal_cob
    loop_cob = _extract_number(entry.loop.get("cob"), ("cob", "COB", "mealCOB", "value", "amount"))
    if loop_cob is not None:
        return loop_cob
    return None


def _device_status_in_range(devicestatus: list[RawDeviceStatus], start: datetime, end: datetime, tz_name: str):
    result = []
    for entry in devicestatus:
        timestamp = _devicestatus_timestamp(entry, tz_name)
        if timestamp and start <= timestamp < end:
            result.append((timestamp, entry))
    return sorted(result, key=lambda item: item[0])


def get_iobs(devicestatus, days_to_show, insulin_treatments, tz_name: str) -> list[list[Any]]:
    bins = get_empty_bins(days_to_show[0], tz_name)
    for day in days_to_show:
        values = [float("nan")] * BINS_PER_DAY
        start = day_start(day, tz_name)
        for timestamp, entry in _device_status_in_range(devicestatus, start, day_end(day, tz_name), tz_name):
            iob = _status_iob(entry)
            if iob is not None:
                values[floor((timestamp - start).total_seconds() / 300)] = float(iob)
        if len(days_to_show) == 1:
            fill_nan_with_treatments(values, insulin_treatments, tz_name)
        interpolate_series(values)
        add_array_to_bins(bins, values)
    return bins


def get_cobs(devicestatus, days_to_show, carb_treatments, tz_name: str) -> list[list[Any]]:
    bins = get_empty_bins(days_to_show[0], tz_name)
    for day in days_to_show:
        values = [float("nan")] * BINS_PER_DAY
        start = day_start(day, tz_name)
        for timestamp, entry in _device_status_in_range(devicestatus, start, day_end(day, tz_name), tz_name):
            cob = _status_cob(entry)
            if cob is not None:
                values[floor((timestamp - start).total_seconds() / 300)] = float(cob)
        if len(days_to_show) == 1:
            fill_nan_with_treatments(values, carb_treatments, tz_name)
        interpolate_series(values, clamp_non_negative=True)
        add_array_to_bins(bins, values)
    return bins


def get_all_treatment_timestamps_for_day(carb_treatments, insulin_treatments, day: date, tz_name: str) -> list[datetime]:
    timestamps = [
        treatment.date
        for treatment in carb_treatments + insulin_treatments
        if ensure_tz(treatment.date, tz_name).date() == day
    ]
    timestamps.sort()
    timestamps.insert(0, day_start(day, tz_name))
    return timestamps


def get_all_predictions_for_day(devicestatus: list[RawDeviceStatus], day: date, tz_name: str) -> list[Prediction]:
    predictions: list[Prediction] = []
    for entry in reversed(devicestatus):
        loop_predicted = entry.loop.get("predicted")
        if loop_predicted and loop_predicted.get("startDate"):
            start_date = ensure_tz(parse_iso(loop_predicted["startDate"], tz_name), tz_name)
            if start_date.date() == day:
                predictions.append(Prediction(start_date=start_date, values=[float(v) for v in loop_predicted.get("values", [])]))
            continue
        suggested = entry.openaps.get("suggested", {})
        pred_bgs = suggested.get("predBGs", {})
        timestamp = suggested.get("timestamp") or entry.created_at
        if not pred_bgs or not timestamp:
            continue
        start_date = ensure_tz(parse_iso(timestamp, tz_name), tz_name)
        if start_date.date() == day:
            values = pred_bgs.get("COB") or pred_bgs.get("UAM") or pred_bgs.get("IOB") or []
            predictions.append(Prediction(start_date=start_date, values=[float(v) for v in values]))
    deduped: list[Prediction] = []
    for prediction in predictions:
        if not deduped or prediction.start_date != deduped[-1].start_date:
            deduped.append(prediction)
    return deduped


def find_predicted(predictions: list[Prediction], timestamp: datetime, offset: int = 0) -> int | None:
    target = timestamp + timedelta(minutes=offset)
    predicted_index: int | None = None
    if offset < 0:
        for index, prediction in enumerate(predictions):
            if prediction.start_date <= target:
                predicted_index = index
    else:
        for index in range(len(predictions) - 1, -1, -1):
            if predictions[index].start_date >= target:
                predicted_index = index
    return predicted_index


def get_predictions(devicestatus, carb_treatments, insulin_treatments, days_to_show, tz_name: str) -> list[list[Any]]:
    bins = get_empty_bins(days_to_show[0], tz_name)
    for day in days_to_show:
        values = [float("nan")] * BINS_PER_DAY
        treatment_timestamps = get_all_treatment_timestamps_for_day(carb_treatments, insulin_treatments, day, tz_name)
        predictions = get_all_predictions_for_day(devicestatus, day, tz_name)
        for treatment_index, timestamp in enumerate(treatment_timestamps):
            predicted_index = find_predicted(predictions, timestamp, 0)
            if predicted_index is None:
                continue
            prediction = predictions[predicted_index]
            current = prediction.start_date
            end = day_end(day, tz_name) - timedelta(microseconds=1)
            if treatment_index < len(treatment_timestamps) - 1:
                end = treatment_timestamps[treatment_index + 1]
            for predicted_value in prediction.values:
                if current > end:
                    break
                index = floor((current - day_start(day, tz_name)).total_seconds() / 300)
                if 0 <= index < BINS_PER_DAY:
                    values[index] = float(predicted_value)
                current += FIVE_MINUTES
        add_array_to_bins(bins, values)
    return bins


def compute_time_shifts(carb_treatments, days_to_show, dia_hours: float, tz_name: str, options: LoopalyzerOptions):
    h1, m1 = parse_clock(options.meal_window_start)
    h2, m2 = parse_clock(options.meal_window_end)
    if (h2, m2) <= (h1, m1):
        return {"enabled": False, "time_shifts": [0] * len(days_to_show), "time_shift_by_day": {}}
    first_carbs = [float("nan")] * len(days_to_show)
    for day_index, day in enumerate(days_to_show):
        begin = day_start(day, tz_name).replace(hour=h1, minute=m1)
        end = day_start(day, tz_name).replace(hour=h2, minute=m2)
        for treatment in carb_treatments:
            local_dt = ensure_tz(treatment.date, tz_name)
            if treatment.amount >= options.meal_min_carbs and begin <= local_dt <= end:
                first_carbs[day_index] = (local_dt - day_start(day, tz_name)).total_seconds() / 60
                break
    meal_minutes = [value for value in first_carbs if not is_nan(value)]
    if not meal_minutes:
        return {"enabled": False, "time_shifts": [0] * len(days_to_show), "time_shift_by_day": {}}
    average_minutes = round(mean(meal_minutes))
    time_shifts = [0] * len(days_to_show)
    time_shift_by_day: dict[date, int] = {}
    for day_index, day in enumerate(days_to_show):
        if is_nan(first_carbs[day_index]):
            continue
        delta = round(average_minutes - first_carbs[day_index])
        time_shifts[day_index] = delta
        time_shift_by_day[day] = delta
    return {
        "enabled": True,
        "time_shifts": time_shifts,
        "time_shift_by_day": time_shift_by_day,
        "window_start": day_start(days_to_show[0], tz_name) + timedelta(minutes=average_minutes),
        "window_stop": min(
            day_start(days_to_show[0], tz_name) + timedelta(minutes=average_minutes + dia_hours * 60),
            day_end(days_to_show[0], tz_name) - timedelta(minutes=1),
        ),
    }


def serialize_bins(bins: list[list[Any]]) -> list[SeriesPoint]:
    return [
        SeriesPoint(timestamp=timestamp.isoformat(), values=[None if is_nan(value) else value for value in values])
        for timestamp, values in bins
    ]


def serialize_avg(avg_series: list[list[Any]]) -> list[AveragePoint]:
    return [
        AveragePoint(timestamp=timestamp.isoformat(), value=None if is_nan(value) else value)
        for timestamp, value in avg_series
    ]


def build_loopalyzer_dataset(
    client: NightscoutClient,
    date_start: datetime,
    date_end: datetime,
    options: LoopalyzerOptions | None = None,
    raw_profiles: list[RawProfileEntry] | None = None,
    raw_treatments: list[RawTreatment] | None = None,
    raw_devicestatus: list[RawDeviceStatus] | None = None,
    raw_sgvs: list[RawGlucoseEntry] | None = None,
) -> LoopalyzerDataset:
    options = options or LoopalyzerOptions()
    raw_profiles = raw_profiles if raw_profiles is not None else client.fetch_profiles()
    tz_name = default_timezone(raw_profiles)
    start = ensure_tz(date_start, tz_name)
    end = ensure_tz(date_end, tz_name)
    days_to_show = date_range_days(start, end, tz_name)
    profiles = normalize_profiles(raw_profiles, tz_name)
    if not profiles:
        raise NightscoutResponseError("Nightscout profile data did not include a usable default profile")

    raw_treatments = raw_treatments if raw_treatments is not None else client.fetch_treatments(start, end)
    raw_devicestatus = raw_devicestatus if raw_devicestatus is not None else client.fetch_devicestatus(start, end)
    raw_sgvs = raw_sgvs if raw_sgvs is not None else client.fetch_sgvs(start, end)
    raw_treatments = _filter_by_timestamp(raw_treatments, start, end, tz_name, _treatment_timestamp)
    raw_devicestatus = _filter_by_timestamp(raw_devicestatus, start, end, tz_name, _devicestatus_timestamp)
    raw_sgvs = _filter_by_timestamp(raw_sgvs, start, end, tz_name, _glucose_timestamp)
    temp_events = build_temp_basal_events(raw_treatments, tz_name)
    carb_treatments = extract_treatment_events(raw_treatments, start, end, "carbs", tz_name)
    insulin_treatments = extract_treatment_events(raw_treatments, start, end, "insulin", tz_name)

    sgv_bins = get_sgvs(raw_sgvs, days_to_show, tz_name)
    basal_bins = get_basals(days_to_show, profiles, temp_events, tz_name)
    temp_basal_delta_bins = get_temp_basal_deltas(days_to_show, profiles, temp_events, tz_name)
    iob_bins = get_iobs(raw_devicestatus, days_to_show, insulin_treatments, tz_name)
    cob_bins = get_cobs(raw_devicestatus, days_to_show, carb_treatments, tz_name)
    prediction_bins = (
        get_predictions(raw_devicestatus, carb_treatments, insulin_treatments, days_to_show, tz_name)
        if options.include_predictions
        else get_nan_bins_for_days(days_to_show, tz_name)
    )

    time_shift = {"enabled": False, "time_shifts": [0] * len(days_to_show), "time_shift_by_day": {}}
    if options.enable_time_shift and len(days_to_show) > 1:
        time_shift = compute_time_shifts(carb_treatments, days_to_show, profiles[-1].dia or 6.0, tz_name, options)
        if time_shift["enabled"]:
            for bins in [sgv_bins, basal_bins, temp_basal_delta_bins, iob_bins, cob_bins, prediction_bins]:
                time_shift_bins(bins, time_shift["time_shifts"])
            time_shift_single_bin(carb_treatments, time_shift["time_shift_by_day"], tz_name)
            time_shift_single_bin(insulin_treatments, time_shift["time_shift_by_day"], tz_name)

    return LoopalyzerDataset(
        timezone=tz_name,
        date_start=start,
        date_end=end,
        days=[day.isoformat() for day in days_to_show],
        profiles=profiles,
        carb_treatments=carb_treatments,
        insulin_treatments=insulin_treatments,
        temp_basal_events=temp_events,
        series={
            "sgv_bins": serialize_bins(sgv_bins),
            "basal_bins": serialize_bins(basal_bins),
            "temp_basal_delta_bins": serialize_bins(temp_basal_delta_bins),
            "iob_bins": serialize_bins(iob_bins),
            "cob_bins": serialize_bins(cob_bins),
            "prediction_bins": serialize_bins(prediction_bins),
        },
        averages={
            "sgv": serialize_avg(avg_bins(sgv_bins)),
            "basal": serialize_avg(avg_bins(basal_bins)),
            "temp_basal_delta": serialize_avg(avg_bins(temp_basal_delta_bins)),
            "iob": serialize_avg(avg_bins(iob_bins)),
            "cob": serialize_avg(avg_bins(cob_bins)),
            "predictions": serialize_avg(avg_bins(prediction_bins)),
        },
        time_shift=TimeShiftSummary(
            enabled=time_shift["enabled"],
            time_shifts=time_shift["time_shifts"],
            window_start=time_shift.get("window_start"),
            window_stop=time_shift.get("window_stop"),
        ),
        raw_counts={
            "profiles": len(raw_profiles),
            "treatments": len(raw_treatments),
            "devicestatus": len(raw_devicestatus),
            "sgvs": len(raw_sgvs),
        },
    )
