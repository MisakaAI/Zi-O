"""UTC 毫秒时间戳,ISO 8601 和站点时区边界转换工具."""

from __future__ import annotations

from datetime import UTC, datetime
from zoneinfo import ZoneInfo


def now_ms() -> int:
    """返回当前 UTC Unix milliseconds,作为数据库时间字段的统一单位."""
    return int(datetime.now(UTC).timestamp() * 1000)


def parse_utc_ms(value: str | int | float) -> int:
    """把带时区的 ISO 8601 字符串或数字转换为 UTC Unix milliseconds."""
    if isinstance(value, (int, float)):
        return int(value)
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        raise ValueError("timestamp must include a timezone")
    return int(parsed.astimezone(UTC).timestamp() * 1000)


def iso_utc(value: int | None) -> str | None:
    """把数据库毫秒时间戳序列化为带毫秒的 UTC ISO 8601 字符串."""
    if value is None:
        return None
    return datetime.fromtimestamp(value / 1000, tz=UTC).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def local_day_start_ms(value: int, timezone_name: str) -> int:
    """计算给定时间在站点时区对应自然日零点的 UTC 毫秒时间戳."""
    local = datetime.fromtimestamp(value / 1000, tz=UTC).astimezone(ZoneInfo(timezone_name))
    start = local.replace(hour=0, minute=0, second=0, microsecond=0)
    return int(start.astimezone(UTC).timestamp() * 1000)


def local_month_bounds(year: int, month: int, timezone_name: str) -> tuple[int, int]:
    """返回站点时区指定月份的 UTC 半开区间起止时间戳."""
    if month < 1 or month > 12:
        raise ValueError("month must be between 1 and 12")
    zone = ZoneInfo(timezone_name)
    start = datetime(year, month, 1, tzinfo=zone)
    if month == 12:
        end = datetime(year + 1, 1, 1, tzinfo=zone)
    else:
        end = datetime(year, month + 1, 1, tzinfo=zone)
    return (
        int(start.astimezone(UTC).timestamp() * 1000),
        int(end.astimezone(UTC).timestamp() * 1000),
    )


def local_date_key(value: int, timezone_name: str) -> str:
    """把 UTC 毫秒时间戳转换为站点时区的 YYYY-MM-DD 日期键."""
    return datetime.fromtimestamp(value / 1000, tz=UTC).astimezone(ZoneInfo(timezone_name)).date().isoformat()
