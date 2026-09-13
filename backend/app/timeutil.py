from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo


def now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def parse_utc_ms(value: str | int | float) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return int(parsed.astimezone(timezone.utc).timestamp() * 1000)


def iso_utc(value: int | None) -> str | None:
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def local_day_start_ms(value: int, timezone_name: str) -> int:
    local = datetime.fromtimestamp(value / 1000, tz=timezone.utc).astimezone(ZoneInfo(timezone_name))
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(start.astimezone(timezone.utc).timestamp() * 1000)


def local_month_bounds(year: int, month: int, timezone_name: str) -> tuple[int, int]:
    if month < 1 or month > 12:
        raise ValueError("month must be between 1 and 12")
    zone = ZoneInfo(timezone_name)
    start = datetime(year, month, 1, tzinfo=zone)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=zone)
    else:
        end = datetime(year, month + 1, 1, tzinfo=zone)
    return (
        int(start.astimezone(timezone.utc).timestamp() * 1000),
        int(end.astimezone(timezone.utc).timestamp() * 1000),
    )


def local_date_key(value: int, timezone_name: str) -> str:
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc).astimezone(ZoneInfo(timezone_name)).date().isoformat()
