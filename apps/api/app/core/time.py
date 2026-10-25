"""
後端時間與雙時區核心服務 (Backend Time and Timezone Core Service)
遵守規約：
1. 事件時間以 UTC ISO-8601 儲存與回傳。
2. 業務日期、工作日曆保留公司時區 (Asia/Taipei 或 Asia/Tokyo)。
3. date-only 純日期禁止強制附加時區偏差。
"""

from datetime import datetime, date, timezone
from zoneinfo import ZoneInfo
from typing import Union, Optional

TIMEZONE_TAIPEI = ZoneInfo("Asia/Taipei")
TIMEZONE_TOKYO = ZoneInfo("Asia/Tokyo")


def get_current_utc_instant() -> datetime:
    """取得當前 UTC 時間戳記 (帶 UTC 時區資訊)"""
    return datetime.now(timezone.utc)


def format_utc_iso(dt: datetime) -> str:
    """轉換為標準 UTC ISO-8601 字串"""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat()


def convert_utc_to_company_tz(
    dt: datetime,
    company_tz: Union[str, ZoneInfo] = TIMEZONE_TAIPEI
) -> datetime:
    """將 UTC 時間轉換為指定公司時區時間"""
    if isinstance(company_tz, str):
        company_tz = ZoneInfo(company_tz)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(company_tz)


def parse_company_date_only(date_str: str) -> date:
    """解析公司業務純日期 (YYYY-MM-DD)，不附加時區污染"""
    return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
