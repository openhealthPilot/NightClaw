from __future__ import annotations

from dataclasses import asdict, is_dataclass
from datetime import datetime
from math import isnan
from typing import Any

from pydantic import BaseModel


def is_nan(value: Any) -> bool:
    return isinstance(value, float) and isnan(value)


def to_jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return to_jsonable(value.model_dump(mode="json", by_alias=False))
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, list):
        return [to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: to_jsonable(item) for key, item in value.items()}
    if is_dataclass(value):
        return to_jsonable(asdict(value))
    if is_nan(value):
        return None
    return value
