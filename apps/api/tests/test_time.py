from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app.core.time import (
    get_current_utc_instant,
    convert_utc_to_company_tz,
    parse_company_date_only,
    TIMEZONE_TAIPEI,
    TIMEZONE_TOKYO,
)


def test_utc_instant_generation():
    """驗證 UTC instant 為嚴格 UTC 時區"""
    now = get_current_utc_instant()
    assert now.tzinfo == timezone.utc


def test_utc_to_taipei_and_tokyo_conversion():
    """驗證同一 UTC 時間在台北 (+8) 與東京 (+9) 的正確換算"""
    # 2026-10-23 01:30:00 UTC
    dt_utc = datetime(2026, 10, 23, 1, 30, 0, tzinfo=timezone.utc)

    taipei_dt = convert_utc_to_company_tz(dt_utc, TIMEZONE_TAIPEI)
    assert taipei_dt.hour == 9
    assert taipei_dt.minute == 30

    tokyo_dt = convert_utc_to_company_tz(dt_utc, TIMEZONE_TOKYO)
    assert tokyo_dt.hour == 10
    assert tokyo_dt.minute == 30


def test_company_date_only_parsing():
    """驗證純業務日期解析為 date 物件且無時區偏移"""
    d = parse_company_date_only("2026-10-23")
    assert d.year == 2026
    assert d.month == 10
    assert d.day == 23
