from typing import Optional, Tuple
from datetime import date, datetime, timedelta
from constants import STAGE_INFO

MAX_PAST_DAYS = 30


def validate_date_not_future(d: date) -> Tuple[bool, Optional[str]]:
    if d > date.today():
        return False, "日期不能是未来日期"
    return True, None


def validate_datetime_not_future(dt: datetime) -> Tuple[bool, Optional[str]]:
    if dt > datetime.now():
        return False, "时间不能是未来时间"
    return True, None


def validate_birth_date(d: date) -> Tuple[bool, Optional[str]]:
    if d > date.today():
        return False, "出生日期不能是未来日期"
    return True, None


def validate_date_range(start: date, end: date) -> Tuple[bool, Optional[str]]:
    if end < start:
        return False, "结束日期不能早于开始日期"
    return True, None


def validate_start_date(d: date, max_past_days: int = MAX_PAST_DAYS) -> Tuple[bool, Optional[str]]:
    valid, msg = validate_date_not_future(d)
    if not valid:
        return False, msg
    earliest = date.today() - timedelta(days=max_past_days)
    if d < earliest:
        return False, f"开始日期不能早于{max_past_days}天前"
    return True, None


def validate_expiry_date(expiry: date, opening: date) -> Tuple[bool, Optional[str]]:
    if expiry <= opening:
        return False, "保质期必须晚于开封日期"
    if expiry < date.today():
        return False, "保质期不能早于今天"
    return True, None
