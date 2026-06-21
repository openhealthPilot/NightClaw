from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class NightscoutModel(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class RawGlucoseEntry(NightscoutModel):
    id: str | None = Field(default=None, alias="_id")
    date: float | None = None
    date_string: str | None = Field(default=None, alias="dateString")
    device: str | None = None
    type: str | None = None
    sgv: int | None = None
    glucose: int | None = None
    is_calibration: bool | None = Field(default=None, alias="isCalibration")
    utc_offset: int | None = Field(default=None, alias="utcOffset")
    sys_time: str | None = Field(default=None, alias="sysTime")


class RawTreatment(NightscoutModel):
    id: str | None = Field(default=None, alias="_id")
    entered_by: str | None = Field(default=None, alias="enteredBy")
    absolute: float | None = None
    insulin_type: str | None = Field(default=None, alias="insulinType")
    event_type: str | None = Field(default=None, alias="eventType")
    sync_identifier: str | None = Field(default=None, alias="syncIdentifier")
    timestamp: str | None = None
    temp: str | None = None
    automatic: bool | None = None
    amount: float | None = None
    rate: float | None = None
    duration: float | None = None
    created_at: str | None = None
    utc_offset: int | None = Field(default=None, alias="utcOffset")
    carbs: float | None = None
    insulin: float | None = None


class RawProfileEntry(NightscoutModel):
    default_profile: str | None = Field(default=None, alias="defaultProfile")
    start_date: str | None = Field(default=None, alias="startDate")
    store: dict[str, dict[str, Any]] = Field(default_factory=dict)
    timezone: str | None = None


class RawDeviceStatus(NightscoutModel):
    created_at: str | None = None
    timestamp: str | None = None
    mills: int | None = None
    openaps: dict[str, Any] = Field(default_factory=dict)
    loop: dict[str, Any] = Field(default_factory=dict)


class GlucoseValue(BaseModel):
    timestamp: str
    glucose: int


class GlucoseSummary(BaseModel):
    average_glucose: float | None
    glucose_values: list[GlucoseValue]


class TreatmentDetail(BaseModel):
    timestamp: str
    event_type: str | None
    amount: float | None
    rate: float | None
    duration: float | None
    carbs: float | None
    insulin: float | None


class TreatmentDetails(BaseModel):
    treatments: list[TreatmentDetail]


class RawTreatmentWindow(BaseModel):
    raw_treatments: list[RawTreatment]
    date_start: datetime
    date_end: datetime


class BolusEvent(BaseModel):
    timestamp: str
    insulin_amount: float


class InsulinOverview(BaseModel):
    insulin_type: str | None
    total_insulin: float
    bolus_insulin: float
    basal_insulin: float
    boluses: list[BolusEvent]


class ProfileSnapshot(BaseModel):
    start_date: datetime
    profile_name: str
    timezone: str | None
    dia: float | None
    basal: list[dict[str, Any]]
    carbratio: list[dict[str, Any]]
    sens: list[dict[str, Any]]


class TempBasalEvent(BaseModel):
    start: datetime
    end: datetime
    rate: float


class TreatmentEvent(BaseModel):
    date: datetime
    amount: float


class Prediction(BaseModel):
    start_date: datetime
    values: list[float]


class SeriesPoint(BaseModel):
    timestamp: str
    values: list[float | None]


class AveragePoint(BaseModel):
    timestamp: str
    value: float | None


class TimeShiftSummary(BaseModel):
    enabled: bool
    time_shifts: list[int]
    window_start: datetime | None = None
    window_stop: datetime | None = None


class LoopalyzerDataset(BaseModel):
    timezone: str
    date_start: datetime
    date_end: datetime
    days: list[str]
    profiles: list[ProfileSnapshot]
    carb_treatments: list[TreatmentEvent]
    insulin_treatments: list[TreatmentEvent]
    temp_basal_events: list[TempBasalEvent]
    series: dict[str, list[SeriesPoint]]
    averages: dict[str, list[AveragePoint]]
    time_shift: TimeShiftSummary
    raw_counts: dict[str, int]


class LoopalyzerOptions(BaseModel):
    include_predictions: bool = True
    enable_time_shift: bool = False
    meal_min_carbs: float = 0.0
    meal_window_start: str = "06:00"
    meal_window_end: str = "23:30"


AgentQueryMode = Literal["glucose", "treatments", "loop", "context"]
AgentQueryDetail = Literal["brief", "standard", "full"]


class AgentQueryRequest(BaseModel):
    question: str | None = None
    mode: AgentQueryMode
    detail: AgentQueryDetail = "standard"


class AgentQueryWindow(BaseModel):
    date_start: str
    date_end: str
    timezone: str


class AgentSafety(BaseModel):
    observational_only: bool = True
    not_for_medical_or_dosing_decisions: bool = True


class AgentEvidenceRef(BaseModel):
    id: str
    source: str
    kind: str
    reference: str | None = None


class AgentDataQuality(BaseModel):
    source_counts: dict[str, int] = Field(default_factory=dict)
    coverage: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


class AgentDailySummary(BaseModel):
    day: str
    glucose: dict[str, Any] = Field(default_factory=dict)
    therapy: dict[str, Any] = Field(default_factory=dict)
    series: dict[str, Any] = Field(default_factory=dict)


class AgentTherapyEvent(BaseModel):
    id: str
    event_type: str
    raw_event_type: str | None
    timestamp_utc: str
    timestamp_local: str
    day: str
    minutes_since_midnight: int
    amount: float | None = None
    unit: str | None = None
    rate: float | None = None
    rate_unit: str | None = None
    duration_minutes: float | None = None
    source: str
    evidence_ref: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentSeriesPoint(BaseModel):
    timestamp_utc: str
    timestamp_local: str
    day: str
    minutes_since_midnight: int
    value: float | None


class AgentSeriesSlice(BaseModel):
    channel: str
    unit: str | None = None
    resolution_minutes: int | None = None
    points: list[AgentSeriesPoint]
    summary: dict[str, Any] = Field(default_factory=dict)


class AgentQueryResponse(BaseModel):
    schema_version: str = "nightclaw.agent_query.v1"
    request: AgentQueryRequest
    window: AgentQueryWindow
    data_used: list[str]
    briefing: dict[str, Any] = Field(default_factory=dict)
    daily_summaries: list[AgentDailySummary] = Field(default_factory=list)
    events: list[AgentTherapyEvent] = Field(default_factory=list)
    series_slices: list[AgentSeriesSlice] = Field(default_factory=list)
    data_quality: AgentDataQuality = Field(default_factory=AgentDataQuality)
    evidence_refs: list[AgentEvidenceRef] = Field(default_factory=list)
    safety: AgentSafety = Field(default_factory=AgentSafety)
