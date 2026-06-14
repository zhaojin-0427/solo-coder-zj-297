from typing import Optional, Dict, Tuple
from constants import STAGE_INFO

VALID_STAGES = set(STAGE_INFO.keys())
MIN_MONTH_AGE = 0
MAX_MONTH_AGE = 72


def is_valid_stage(stage: int) -> bool:
    return stage in VALID_STAGES


def validate_stage(current_stage: int) -> Optional[Dict]:
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


def validate_month_age(month_age: int) -> Tuple[bool, Optional[str], Optional[Dict]]:
    if month_age < MIN_MONTH_AGE:
        error = f"无效的月龄: {month_age}，月龄不能为负数"
        result = {
            "recommended_stage": None,
            "stage_name": None,
            "month_range": None,
            "description": None,
            "daily_intake_range": None,
            "match_score": 0.0,
            "error": error,
        }
        return False, error, result
    if month_age > MAX_MONTH_AGE:
        error = f"无效的月龄: {month_age}，月龄最大为 {MAX_MONTH_AGE} 个月"
        result = {
            "recommended_stage": None,
            "stage_name": None,
            "month_range": None,
            "description": None,
            "daily_intake_range": None,
            "match_score": 0.0,
            "error": error,
        }
        return False, error, result
    return True, None, None
