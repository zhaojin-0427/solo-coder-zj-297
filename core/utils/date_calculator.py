from typing import Optional, Tuple
from datetime import date, datetime, timedelta
from schemas import SCOOP_TO_WATER_RATIO


def to_date(value) -> date:
    if hasattr(value, "date"):
        return value.date()
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return value


def calculate_month_age(birth_date, current_date) -> int:
    birth = to_date(birth_date)
    current = to_date(current_date)
    months = (current.year - birth.year) * 12 + (current.month - birth.month)
    if current.day < birth.day:
        months -= 1
    return max(0, months)


def calculate_report_period(report_type: str, ref_date: Optional[date] = None) -> Tuple[date, date]:
    if ref_date is None:
        ref_date = date.today()

    if report_type == "weekly":
        weekday = ref_date.weekday()
        period_end = ref_date - timedelta(days=weekday + 1)
        period_start = period_end - timedelta(days=6)
        return period_start, period_end
    else:
        first_day = ref_date.replace(day=1)
        period_end = first_day - timedelta(days=1)
        period_start = period_end.replace(day=1)
        return period_start, period_end


def calculate_stock_days(
    current_remaining_grams: float,
    daily_intake_ml: float,
    scoop_weight_grams: float = 4.5
) -> float:
    if daily_intake_ml <= 0 or current_remaining_grams <= 0:
        return 0.0
    grams_per_ml = scoop_weight_grams / SCOOP_TO_WATER_RATIO
    daily_grams_needed = daily_intake_ml * grams_per_ml
    return round(current_remaining_grams / daily_grams_needed, 1)
