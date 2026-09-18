from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

LOCAL_TZ = ZoneInfo("America/Los_Angeles")
UTC = timezone.utc


def _parse_utc_datetime(value: str | None):
    if not value:
        return None

    normalized = value.strip()
    if not normalized:
        return None

    if " " in normalized and "T" not in normalized:
        normalized = normalized.replace(" ", "T", 1)

    has_offset = normalized.endswith("Z") or "+" in normalized[10:] or "-" in normalized[10:]
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    elif not has_offset:
        normalized = normalized + "+00:00"

    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)

    return dt.astimezone(LOCAL_TZ)


def utc_to_local_exif(value: str | None) -> str:
    dt = _parse_utc_datetime(value)
    return dt.strftime("%Y:%m:%d %H:%M:%S") if dt else ""


def utc_to_local_date(value: str | None) -> str:
    dt = _parse_utc_datetime(value)
    return dt.strftime("%Y-%m-%d") if dt else ""


def utc_to_local_time(value: str | None) -> str:
    dt = _parse_utc_datetime(value)
    return dt.strftime("%H:%M") if dt else ""


def filename_utc_to_local_exif(filename_fragment: str | None) -> str:
    if not filename_fragment:
        return ""

    dt = datetime.strptime(filename_fragment, "%Y-%m-%d_%H-%M-%S").replace(tzinfo=UTC)
    return dt.astimezone(LOCAL_TZ).strftime("%Y:%m:%d %H:%M:%S")
