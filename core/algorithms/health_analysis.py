from typing import Dict, Optional, List
from constants import STAGE_INFO, DIGESTION_STATUS, get_weight_range, get_nutrient_requirement
from core.validators import validate_stage, validate_month_age, is_valid_stage
from core.algorithms.stage_matching import match_stage_by_month, calculate_stage_suitability


def analyze_weight_growth(
    month_age: int,
    weight_kg: float,
    gender: str,
    weight_history: Optional[List[Dict]] = None
) -> Dict:
    min_w, max_w = get_weight_range(month_age, gender)
    median_w = (min_w + max_w) / 2

    if weight_kg < min_w:
        level = "underweight"
        deviation = (min_w - weight_kg) / min_w
        status = "体重偏轻"
    elif weight_kg > max_w:
        level = "overweight"
        deviation = (weight_kg - max_w) / max_w
        status = "体重偏重"
    else:
        level = "normal"
        deviation = abs(weight_kg - median_w) / median_w
        status = "体重正常"

    result = {
        "current_weight": weight_kg,
        "reference_range": [round(min_w, 2), round(max_w, 2)],
        "median_weight": round(median_w, 2),
        "weight_level": level,
        "weight_status": status,
        "deviation_percent": round(deviation * 100, 2),
        "need_attention": deviation > 0.15 if level == "normal" else True,
    }

    if weight_history and len(weight_history) >= 2:
        sorted_history = sorted(weight_history, key=lambda x: x["month_age"])
        growth_rates = []
        for i in range(1, len(sorted_history)):
            prev = sorted_history[i - 1]
            curr = sorted_history[i]
            month_diff = curr["month_age"] - prev["month_age"]
            if month_diff > 0:
                rate = (curr["weight_kg"] - prev["weight_kg"]) / month_diff
                growth_rates.append(rate)
        if growth_rates:
            avg_rate = sum(growth_rates) / len(growth_rates)
            if month_age <= 3:
                expected_rate = 1.0
            elif month_age <= 6:
                expected_rate = 0.7
            elif month_age <= 12:
                expected_rate = 0.4
            else:
                expected_rate = 0.2
            rate_status = "正常" if 0.6 * expected_rate <= avg_rate <= 1.4 * expected_rate else (
                "增长过快" if avg_rate > 1.4 * expected_rate else "增长缓慢"
            )
            result.update({
                "avg_monthly_gain_kg": round(avg_rate, 3),
                "expected_monthly_gain_kg": round(expected_rate, 3),
                "growth_rate_status": rate_status,
                "growth_abnormal": rate_status != "正常",
            })

    return result


def analyze_digestion(digestion_status: str, digestion_note: Optional[str] = None) -> Dict:
    status_map = {
        "normal": {"level": "normal", "score": 100, "alert": False, "description": "消化正常"},
        "mild_discomfort": {"level": "mild", "score": 75, "alert": False, "description": "轻度不适，注意观察"},
        "constipation": {"level": "moderate", "score": 50, "alert": True, "description": "便秘，建议调整奶量或更换段位"},
        "diarrhea": {"level": "severe", "score": 30, "alert": True, "description": "腹泻，建议就医"},
        "allergy": {"level": "severe", "score": 20, "alert": True, "description": "过敏反应，立即就医并考虑特殊配方奶"},
        "vomiting": {"level": "moderate", "score": 40, "alert": True, "description": "频繁吐奶，建议就医检查"},
    }
    info = status_map.get(digestion_status, status_map["mild_discomfort"])
    return {
        "digestion_status": digestion_status,
        "status_name": DIGESTION_STATUS.get(digestion_status, "未知"),
        "level": info["level"],
        "digestion_score": info["score"],
        "alert": info["alert"],
        "description": info["description"],
        "note": digestion_note,
    }


def analyze_nutrient_gap(
    month_age: int,
    current_stage: int,
    daily_intake_ml: float,
    weight_kg: float
) -> Dict:
    if not is_valid_stage(current_stage):
        return {
            "daily_intake_ml": daily_intake_ml,
            "recommended_intake_range": None,
            "intake_status": "无效段位",
            "actual_intake_per_day": None,
            "nutrient_gaps": None,
            "overall_gap_score": 0.0,
            "overall_status": f"无效的奶粉段位: {current_stage}，有效段位为 1-4",
            "need_supplement": False,
        }

    stage_nutrients = STAGE_INFO[current_stage]["nutrients"]
    requirements = get_nutrient_requirement(month_age)
    intake_per_100ml = daily_intake_ml / 100.0

    actual_intake = {}
    gaps = {}
    total_gap_score = 0.0
    nutrient_count = 0

    for nutrient in ["protein", "fat", "carb", "calcium", "iron", "dha"]:
        actual = round(stage_nutrients[nutrient] * intake_per_100ml, 2)
        required = round(requirements[nutrient], 2)
        actual_intake[nutrient] = actual
        if required > 0:
            gap_ratio = (actual - required) / required
        else:
            gap_ratio = 0.0
        gaps[nutrient] = {
            "actual": actual,
            "required": required,
            "gap_ratio": round(gap_ratio, 3),
            "status": "充足" if gap_ratio >= 0 else "不足",
            "gap_amount": round(required - actual, 2) if gap_ratio < 0 else 0,
        }
        if gap_ratio < 0:
            total_gap_score += abs(gap_ratio)
        nutrient_count += 1

    overall_gap_score = round(total_gap_score / nutrient_count * 100, 2) if nutrient_count > 0 else 0
    overall_status = "营养充足" if overall_gap_score < 5 else ("轻度营养缺口" if overall_gap_score < 15 else "显著营养缺口")

    intake_range = [STAGE_INFO[current_stage]["daily_intake_min"], STAGE_INFO[current_stage]["daily_intake_max"]]
    if daily_intake_ml < intake_range[0]:
        intake_status = "奶量不足"
    elif daily_intake_ml > intake_range[1]:
        intake_status = "奶量偏高"
    else:
        intake_status = "奶量正常"

    return {
        "daily_intake_ml": daily_intake_ml,
        "recommended_intake_range": intake_range,
        "intake_status": intake_status,
        "actual_intake_per_day": actual_intake,
        "nutrient_gaps": gaps,
        "overall_gap_score": overall_gap_score,
        "overall_status": overall_status,
        "need_supplement": overall_gap_score >= 10,
    }


def comprehensive_analysis(
    month_age: int,
    current_stage: int,
    daily_intake_ml: float,
    digestion_status: str,
    weight_kg: float,
    gender: str,
    weight_history: Optional[List[Dict]] = None,
    digestion_note: Optional[str] = None,
) -> Dict:
    stage_validation = validate_stage(current_stage)
    if stage_validation:
        return {
            "stage_suitability": stage_validation,
            "weight_analysis": None,
            "digestion_analysis": None,
            "nutrient_analysis": None,
            "transition_analysis": None,
            "warnings": [{"type": "invalid_stage", "level": "high", "message": stage_validation["suggestion"]}],
            "need_doctor_consultation": False,
            "overall_suggestion": stage_validation["suggestion"],
        }

    is_valid, error, error_result = validate_month_age(month_age)
    if not is_valid:
        return {
            "stage_suitability": {
                "current_stage": current_stage,
                "current_stage_name": STAGE_INFO[current_stage]["name"],
                "recommended_stage": None,
                "recommended_stage_name": None,
                "suitability": "invalid",
                "suitability_score": 0.0,
                "suggestion": error or "无效月龄",
                "recommended": error_result,
            },
            "weight_analysis": None,
            "digestion_analysis": None,
            "nutrient_analysis": None,
            "transition_analysis": None,
            "warnings": [{"type": "invalid_month_age", "level": "high", "message": error or "无效月龄"}],
            "need_doctor_consultation": False,
            "overall_suggestion": error or "无效月龄",
        }

    from core.algorithms.transition import calculate_transition_success_rate

    stage_suitability = calculate_stage_suitability(month_age, current_stage)
    weight_analysis = analyze_weight_growth(month_age, weight_kg, gender, weight_history)
    digestion_analysis = analyze_digestion(digestion_status, digestion_note)
    nutrient_analysis = analyze_nutrient_gap(month_age, current_stage, daily_intake_ml, weight_kg)

    target_stage = stage_suitability["recommended_stage"]
    transition = calculate_transition_success_rate(
        month_age, current_stage, target_stage,
        digestion_status, weight_analysis["weight_level"], daily_intake_ml
    )

    warnings = []
    if stage_suitability["suitability"] == "mismatch":
        warnings.append({"type": "stage_mismatch", "level": "high", "message": stage_suitability["suggestion"]})
    elif stage_suitability["suitability"] == "acceptable":
        warnings.append({"type": "stage_warning", "level": "medium", "message": stage_suitability["suggestion"]})

    if digestion_analysis["alert"]:
        warnings.append({"type": "digestion_alert", "level": "high", "message": digestion_analysis["description"]})

    if weight_analysis["need_attention"]:
        warnings.append({"type": "growth_alert", "level": "medium", "message": f"生长曲线异常: {weight_analysis['weight_status']}"})

    if nutrient_analysis["need_supplement"]:
        warnings.append({"type": "nutrient_gap", "level": "medium", "message": nutrient_analysis["overall_status"]})

    need_doctor = any(w["level"] == "high" for w in warnings) or (
        weight_analysis.get("growth_abnormal", False)
    )

    return {
        "stage_suitability": stage_suitability,
        "weight_analysis": weight_analysis,
        "digestion_analysis": digestion_analysis,
        "nutrient_analysis": nutrient_analysis,
        "transition_analysis": transition,
        "warnings": warnings,
        "need_doctor_consultation": need_doctor,
        "overall_suggestion": "建议就医咨询" if need_doctor else (
            transition["suggestions"][0] if transition["suggestions"] else "继续保持当前喂养方案"
        ),
    }
