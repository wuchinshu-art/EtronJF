from datetime import datetime, date, time, timedelta, timezone
from zoneinfo import ZoneInfo
from decimal import Decimal, ROUND_HALF_UP
from typing import Tuple, Optional
from sqlalchemy.orm import Session

from app.core.time import convert_utc_to_company_tz, TIMEZONE_TAIPEI
from app.core.errors import AppException
from app.models.hr import Company, Employee, Shift, CalendarDay
from app.models.leave import LeaveRequest


def calculate_leave_minutes_and_days(
    db: Session,
    employee: Employee,
    start_time_utc: datetime,
    end_time_utc: datetime,
) -> Tuple[int, Decimal]:
    """
    精確折算請假工作分鐘數與等效天數。
    規則：
    1. 依照員工所屬班別 (Shift) 之工作時段與每日標準工時 (work_minutes_per_day)。
    2. 排除公司工作日曆 (CalendarDay) 之非工作日 (例假日、國定假日)。
    3. 扣除班別規定之休息時間 (rest_minutes，預設午休 12:00~13:00)。
    4. 換算天數 = 總工作分鐘數 / 班別標準日工時 (四捨五入至小數點後兩位)。
    """
    if start_time_utc >= end_time_utc:
        raise AppException(
            code="INVALID_LEAVE_TIME_RANGE",
            message="Leave start time must be before end time",
            status_code=400,
        )

    # 取得員工所屬公司與時區
    company = db.query(Company).filter(Company.id == employee.company_id).first()
    company_tz_str = company.default_timezone if company and company.default_timezone else "Asia/Taipei"
    company_tz = ZoneInfo(company_tz_str)

    # 取得員工公司啟用班別 (預設常日班 09:00-18:00, 480分, 休息60分)
    shift = db.query(Shift).filter(Shift.company_id == employee.company_id).first()

    def parse_time_str(t_str: Optional[str], default_t: time) -> time:
        if not t_str:
            return default_t
        try:
            parts = t_str.split(":")
            return time(int(parts[0]), int(parts[1]))
        except Exception:
            return default_t

    shift_start_time = parse_time_str(shift.work_start_time if shift else None, time(9, 0))
    shift_end_time = parse_time_str(shift.work_end_time if shift else None, time(18, 0))
    rest_minutes = shift.break_minutes if shift else 60
    work_minutes_per_day = shift.daily_standard_minutes if shift and shift.daily_standard_minutes > 0 else 480
    is_overnight = shift.is_overnight if shift else False

    # 轉為公司當地時區時間
    local_start = convert_utc_to_company_tz(start_time_utc, company_tz)
    local_end = convert_utc_to_company_tz(end_time_utc, company_tz)

    curr_date = local_start.date()
    end_date = local_end.date()

    total_work_minutes = 0

    while curr_date <= end_date:
        # 查詢公司工作日曆
        cal_day = (
            db.query(CalendarDay)
            .filter(
                CalendarDay.company_id == employee.company_id,
                CalendarDay.calendar_date == curr_date,
            )
            .first()
        )

        is_work_day = cal_day.is_working_day if cal_day else (curr_date.weekday() < 5)

        if is_work_day:
            # 建立該日排班之起訖時間
            day_shift_start = datetime.combine(curr_date, shift_start_time).replace(tzinfo=company_tz)
            if is_overnight:
                day_shift_end = datetime.combine(curr_date + timedelta(days=1), shift_end_time).replace(tzinfo=company_tz)
            else:
                day_shift_end = datetime.combine(curr_date, shift_end_time).replace(tzinfo=company_tz)

            # 請假時段與排班時段求交集
            effective_start = max(local_start, day_shift_start)
            effective_end = min(local_end, day_shift_end)

            if effective_start < effective_end:
                gross_minutes = int((effective_end - effective_start).total_seconds() // 60)

                # 計算休息時間扣除 (標準午休為 12:00 ~ 12:00 + rest_minutes)
                rest_start = datetime.combine(curr_date, time(12, 0)).replace(tzinfo=company_tz)
                rest_end = rest_start + timedelta(minutes=rest_minutes)

                overlap_rest_start = max(effective_start, rest_start)
                overlap_rest_end = min(effective_end, rest_end)

                rest_deduction = 0
                if overlap_rest_start < overlap_rest_end:
                    rest_deduction = int((overlap_rest_end - overlap_rest_start).total_seconds() // 60)

                net_minutes = max(0, gross_minutes - rest_deduction)
                # 單日不超過該班別標準每日工時
                net_minutes = min(net_minutes, work_minutes_per_day)

                total_work_minutes += net_minutes

        curr_date += timedelta(days=1)

    calculated_days = (
        Decimal(total_work_minutes) / Decimal(work_minutes_per_day)
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return total_work_minutes, calculated_days


def check_leave_overlap(
    db: Session,
    employee_id: str,
    start_time_utc: datetime,
    end_time_utc: datetime,
    exclude_request_id: Optional[str] = None,
) -> None:
    """
    檢查請假時段是否與該員工現有之審核中或已核准假單重疊。
    """
    query = db.query(LeaveRequest).filter(
        LeaveRequest.employee_id == employee_id,
        LeaveRequest.status.in_(["SUBMITTED", "IN_REVIEW", "APPROVED"]),
        LeaveRequest.start_time < end_time_utc,
        LeaveRequest.end_time > start_time_utc,
    )

    if exclude_request_id:
        query = query.filter(LeaveRequest.id != exclude_request_id)

    overlap = query.first()
    if overlap:
        raise AppException(
            code="LEAVE_REQUEST_OVERLAP",
            message=f"Leave request overlaps with existing request {overlap.request_number} ({overlap.status})",
            status_code=400,
        )
