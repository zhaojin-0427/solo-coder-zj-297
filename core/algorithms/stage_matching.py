from typing import Dict, Optional
from constants import STAGE_INFO
from core.validators import validate_stage, validate_month_age


def match_stage_by_month(month_age: int) -> Dict:
    is_valid, error, error_result = validate_month_age(month_age)
    if not is_valid:
        return error_result

    for stage_num in sorted(STAGE_INFO.keys()):
        info = STAGE_INFO[stage_num]
        if info["min_month"] <= month_age < info["max_month"]:
            return {
                "recommended_stage": stage_num,
                "stage_name": info["name"],
                "month_range": [info["min_month"], info["max_month"]],
                "description": info["description"],
                "daily_intake_range": [info["daily_intake_min"], info["daily_intake_max"]],
                "match_score": 1.0,
            }

    if month_age >= STAGE_INFO[4]["max_month"]:
        info = STAGE_INFO[4]
        return {
            "recommended_stage": 4,
            "stage_name": info["name"],
            "month_range": [info["min_month"], info["max_month"]],
            "description": info["description"],
            "daily_intake_range": [info["daily_intake_min"], info["daily_intake_max"]],
            "match_score": 1.0,
            "note": "已超过配方奶最大推荐月龄，建议以主食为主",
        }

    info = STAGE_INFO[1]
    return {
        "recommended_stage": 1,
        "stage_name": info["name"],
        "month_range": [info["min_month"], info["max_month"]],
        "description": info["description"],
        "daily_intake_range": [info["daily_intake_min"], info["daily_intake_max"]],
        "match_score": 1.0,
    }


def calculate_stage_suitability(month_age: int, current_stage: int) -> Dict:
    stage_validation = validate_stage(current_stage)
    if stage_validation:
        return stage_validation

    is_valid, error, error_result = validate_month_age(month_age)
    if not is_valid:
        return {
            "current_stage": current_stage,
            "current_stage_name": STAGE_INFO[current_stage]["name"],
            "recommended_stage": None,
            "recommended_stage_name": None,
            "suitability": "invalid",
            "suitability_score": 0.0,
            "suggestion": error or "无效月龄",
            "recommended": error_result,
        }

    recommended = match_stage_by_month(month_age)
    recommended_stage = recommended["recommended_stage"]

    if current_stage == recommended_stage:
        suitability = "perfect"
        score = 1.0
        suggestion = "当前段位与月龄完全匹配，继续保持"
    elif abs(current_stage - recommended_stage) == 1:
        suitability = "acceptable"
        if current_stage < recommended_stage:
            score = 0.7
            suggestion = f"月龄已达到{recommended['stage_name']}范围，建议准备转段"
        else:
            score = 0.5
            suggestion = f"当前段位偏高，建议观察宝宝消化情况"
    else:
        suitability = "mismatch"
        if current_stage < recommended_stage:
            score = 0.3
            suggestion = f"严重滞后，建议尽快转至{recommended['stage_name']}"
        else:
            score = 0.2
            suggestion = f"段位过高，宝宝肠胃可能难以适应，建议降段"

    return {
        "current_stage": current_stage,
        "current_stage_name": STAGE_INFO[current_stage]["name"],
        "recommended_stage": recommended_stage,
        "recommended_stage_name": recommended["stage_name"],
        "suitability": suitability,
        "suitability_score": round(score, 3),
        "suggestion": suggestion,
        "recommended": recommended,
    }
