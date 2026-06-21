from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, TypeVar

import requests
from dotenv import load_dotenv
from pydantic import ValidationError

from .errors import NightscoutConfigError, NightscoutRequestError, NightscoutResponseError
from .models import RawDeviceStatus, RawGlucoseEntry, RawProfileEntry, RawTreatment
from .time import nightscout_range_params

ModelT = TypeVar("ModelT", RawDeviceStatus, RawGlucoseEntry, RawProfileEntry, RawTreatment)


class NightscoutClient:
    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: int = 20,
        session: requests.Session | None = None,
    ) -> None:
        if not base_url.strip():
            raise NightscoutConfigError("NIGHTSCOUT_BASE_URL must not be empty")
        if not token.strip():
            raise NightscoutConfigError("NIGHTSCOUT_API_KEY must not be empty")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.timeout = timeout
        self.session = session or requests.Session()

    @classmethod
    def from_env(cls, timeout: int = 20) -> "NightscoutClient":
        load_dotenv()
        load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
        load_dotenv(Path(__file__).resolve().parents[3] / ".env", override=False)
        base_url = os.getenv("NIGHTSCOUT_BASE_URL")
        token = os.getenv("NIGHTSCOUT_API_KEY")
        if not base_url or not token:
            raise NightscoutConfigError("NIGHTSCOUT_BASE_URL and NIGHTSCOUT_API_KEY must be set")
        return cls(base_url=base_url, token=token, timeout=timeout)

    def get_json(self, path: str, params: dict[str, str] | None = None) -> Any:
        query = {"token": self.token}
        if params:
            query.update(params)
        try:
            response = self.session.get(f"{self.base_url}{path}", params=query, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            raise NightscoutRequestError(f"Nightscout request failed for {path}: {exc}") from exc
        except ValueError as exc:
            raise NightscoutResponseError(f"Nightscout returned invalid JSON for {path}") from exc

    def _get_model_list(self, path: str, model: type[ModelT], params: dict[str, str] | None = None) -> list[ModelT]:
        payload = self.get_json(path, params)
        if not isinstance(payload, list):
            raise NightscoutResponseError(f"Nightscout response for {path} must be a list")
        try:
            return [model.model_validate(item) for item in payload]
        except ValidationError as exc:
            raise NightscoutResponseError(f"Nightscout response for {path} did not match expected shape") from exc

    def fetch_treatments(self, start: datetime, end: datetime, count: int = 0) -> list[RawTreatment]:
        return self._get_model_list(
            "/api/v1/treatments.json",
            RawTreatment,
            nightscout_range_params("created_at", start, end, count),
        )

    def fetch_profiles(self) -> list[RawProfileEntry]:
        return self._get_model_list("/api/v1/profile.json", RawProfileEntry)

    def fetch_devicestatus(self, start: datetime, end: datetime, count: int = 0) -> list[RawDeviceStatus]:
        return self._get_model_list(
            "/api/v1/devicestatus.json",
            RawDeviceStatus,
            nightscout_range_params("created_at", start, end, count),
        )

    def fetch_sgvs(self, start: datetime, end: datetime, count: int = 0) -> list[RawGlucoseEntry]:
        return self._get_model_list(
            "/api/v1/entries/sgv.json",
            RawGlucoseEntry,
            nightscout_range_params("dateString", start, end, count),
        )
