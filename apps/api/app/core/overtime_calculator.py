from datetime import datetime, date, time, timedelta, timezone
from zoneinfo import ZoneInfo
from typing import Tuple, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.core.time import convert_utc_to_company_tz, TIMEZONE_TAIPEI
from app.core.errors import AppException
from app.models.hr import Company, Employee, CalendarDay
from app.models.overtime import OvertimeRequest


def calculate_overtime_minutes(
    db: Session,
    employee: Employee,
    start_time_utc: datetime,
    end_time_utc: datetime,
    rest_minutes: int = 0,
    compensation_type: str = "COMPENSATORY_LEAVE",
) -> Dict[str, Any]:
    """
    計算加班分鐘數與級距明細：
    1. 扣除休息時間 (rest_minutes) 得出淨加班分鐘數 (net_minutes)
    2. 比對日曆判定日別類型：
       - REGULAR: 平日延長工時 (前2小時, 第3-4小時)
       - REST_DAY: 休息日加班
       - REGULAR_HOLIDAY / NATIONAL_HOLIDAY: 例假日 / 國定假日加班
    3. 計算轉補休假額分鐘數 (comp_leave_minutes)
    """
    if start_time_utc >= end_time_utc:
        raise AppException(
            code="INVALID_OVERTIME_TIME_RANGE",
            message="Overtime start time must be before end time",
            status_code=400,
        )

    # 取得公司與時區
    company = db.query(Company).filter(Company.id == employee.company_id).first()
    company_tz_str = company.default_timezone if company and company.default_timezone else "Asia/Taipei"
    company_tz = ZoneInfo(company_tz_str)

    # 轉為公司當地時間以決定歸屬日期
    local_start = convert_utc_to_company_tz(start_time_utc, company_tz)
    local_end = convert_utc_to_company_tz(end_time_utc, company_tz)
    ot_date = local_start.date()

    # 查詢公司工作日曆
    cal_day = (
        db.query(CalendarDay)
        .filter(
            CalendarDay.company_id == employee.company_id,
            CalendarDay.calendar_date == ot_date,
        )
        .first()
    )

    if cal_day:
        day_type = cal_day.day_type
    else:
        # 預設：週六為 REST_DAY，週日為 REGULAR_HOLIDAY，平日為 REGULAR
        if ot_date.weekday() == 5:
            day_type = "REST_DAY"
        elif ot_date.weekday() == 6:
            day_type = "REGULAR_HOLIDAY"
        else:
            day_type = "REGULAR"

    # 計算總毛時間與扣除休息時間後的淨加班分鐘數
    gross_minutes = int((end_time_utc - start_time_utc).total_seconds() // 60)
    net_minutes = max(0, gross_minutes - rest_minutes)

    if net_minutes <= 0:
        raise AppException(
            code="ZERO_OVERTIME_MINUTES",
            message="扣除休息時間後之有效加班時間必須大於 0 分鐘",
            status_code=400,
        )

    # 計算級距分段
    tier1_minutes = 0
    tier2_minutes = 0
    tier3_minutes = 0

    if day_type == "REGULAR":
        tier1_minutes = min(net_minutes, 120)  # 前 2 小時
        tier2_minutes = max(0, net_minutes - 120)  # 超過 2 小時
    elif day_type == "REST_DAY":
        tier1_minutes = min(net_minutes, 120)  # 前 2 小時
        tier2_minutes = min(max(0, net_minutes - 120), 360)  # 第 3~8 小時
        tier3_minutes = max(0, net_minutes - 480)  # 超過 8 小時
    else:  # 例假日 / 國定假日
        tier1_minutes = min(net_minutes, 480)  # 8 小時內
        tier2_minutes = max(0, net_minutes - 480)  # 超過 8 小時

    # 轉補休假額分鐘數 (標準依淨工時 1:1 換算)
    comp_leave_minutes = net_minutes if compensation_type == "COMPENSATORY_LEAVE" else 0

    return {
        "gross_minutes": gross_minutes,
        "rest_minutes": rest_minutes,
        "net_minutes": net_minutes,
        "day_type": day_type,
        "tier1_minutes": tier1_minutes,
        "tier2_minutes": tier2_minutes,
        "tier3_minutes": tier3_minutes,
        "comp_leave_minutes": comp_leave_minutes,
        "compensation_type": compensation_type,
    }


def check_overtime_overlap(
    db: Session,
    employee_id: str,
    start_time_utc: datetime,
    end_time_utc: datetime,
    exclude_request_id: Optional[str] = None,
) -> None:
    """
    檢查加班時段是否與該員工現有之審核中或已核准加班單重疊。
    """
    query = db.query(OvertimeRequest).filter(
        OvertimeRequest.employee_id == employee_id,
        OvertimeRequest.status.in_(["SUBMITTED", "IN_REVIEW", "APPROVED"]),
        OvertimeRequest.start_time < end_time_utc,
        OvertimeRequest.end_time > start_time_utc,
    )

    if exclude_request_id:
        query = query.filter(OvertimeRequest.id != exclude_request_id)

    overlap = query.first()
    if overlap:
        raise AppException(
            code="OVERTIME_REQUEST_OVERLAP",
            message=f"Overtime request overlaps with existing request {overlap.request_number} ({overlap.status})",
            status_code=400,
        )
