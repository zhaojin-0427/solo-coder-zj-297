from typing import Dict, List, Optional, Tuple
from datetime import date, datetime, timedelta

from constants import STAGE_INFO, TRANSITION_SUCCESS_BASE, DIGESTION_STATUS, get_weight_range, get_nutrient_requirement
from schemas import (
    STORAGE_METHOD_NAMES, REMAINING_HANDLING_NAMES,
    MIN_WATER_TEMPERATURE, MAX_WATER_TEMPERATURE, SCOOP_TO_WATER_RATIO, OPENING_SAFE_DAYS
)

from core.algorithms import (
    match_stage_by_month,
    calculate_stage_suitability,
    analyze_weight_growth,
    analyze_digestion,
    analyze_nutrient_gap,
    comprehensive_analysis,
    calculate_transition_success_rate,
    analyze_single_record,
    generate_phase_review,
    generate_plan_review,
    analyze_formula_batch,
    analyze_brewing_record,
    generate_brewing_daily_report,
    analyze_abnormal_event_risk,
    generate_abnormal_event_replay,
)
from core.algorithms.event_risk import SEVERITY_LEVEL_MAP, ABNORMAL_EVENT_TYPE_NAMES
from core.reports import (
    generate_feeding_report,
    calculate_overall_score,
    generate_report_summary,
    get_event_type_distribution,
)
from core.utils.date_calculator import (
    calculate_month_age,
    calculate_report_period,
    calculate_stock_days,
)
from core.validators.stage import is_valid_stage

VALID_STAGES = set(STAGE_INFO.keys())


def _validate_stage(current_stage: int) -> Optional[Dict]:
    if not is_valid_stage(current_stage):
        return {
            "current_stage": current_stage,
            "current_stage_name": "无效段位",
            "recommended_stage": None,
            "recommended_stage_name": None,
            "suitability": "invalid",
            "suitability_score": 0.0,
            "suggestion": f"无效的奶粉段位: {current_stage}，有效段位为 1-4",
            "recommended": None,
        }
    return None


def _validate_month_age(month_age: int) -> Optional[Dict]:
    if month_age < 0:
        return {
            "recommended_stage": None,
            "stage_name": None,
            "month_range": None,
            "description": None,
            "daily_intake_range": None,
            "match_score": 0.0,
            "error": f"无效的月龄: {month_age}，月龄不能为负数",
        }
    return None


def _calculate_overall_score(
    total_milk_ml: float,
    period_days: int,
    baby,
    weight_change_kg: float,
    digestion_abnormal_count: int,
    brewing_abnormal_count: int,
    batch_risk_count: int,
    transition_progress: float,
    doctor_consultation_count: int,
    abnormal_event_completion_rate: float,
    health_records_count: int,
) -> float:
    return calculate_overall_score(
        total_milk_ml=total_milk_ml,
        period_days=period_days,
        baby=baby,
        weight_change_kg=weight_change_kg,
        digestion_abnormal_count=digestion_abnormal_count,
        brewing_abnormal_count=brewing_abnormal_count,
        batch_risk_count=batch_risk_count,
        transition_progress=transition_progress,
        doctor_consultation_count=doctor_consultation_count,
        abnormal_event_completion_rate=abnormal_event_completion_rate,
        health_records_count=health_records_count,
    )


def _generate_report_summary(
    report_type: str,
    baby_name: str,
    period_start: date,
    period_end: date,
    total_milk_ml: float,
    avg_daily_milk_ml: float,
    weight_change_kg: float,
    overall_score: float,
    abnormal_event_count: int,
    digestion_abnormal_count: int,
) -> str:
    return generate_report_summary(
        report_type=report_type,
        baby_name=baby_name,
        period_start=period_start,
        period_end=period_end,
        total_milk_ml=total_milk_ml,
        avg_daily_milk_ml=avg_daily_milk_ml,
        weight_change_kg=weight_change_kg,
        overall_score=overall_score,
        abnormal_event_count=abnormal_event_count,
        digestion_abnormal_count=digestion_abnormal_count,
    )


def _get_event_type_distribution(events: List) -> List[Dict]:
    return get_event_type_distribution(events)
