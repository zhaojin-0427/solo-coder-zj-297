from typing import Dict, List, Optional, Tuple
from datetime import date, datetime, timedelta
from constants import STAGE_INFO, TRANSITION_SUCCESS_BASE, DIGESTION_STATUS, get_weight_range, get_nutrient_requirement
from schemas import (
    STORAGE_METHOD_NAMES, REMAINING_HANDLING_NAMES,
    MIN_WATER_TEMPERATURE, MAX_WATER_TEMPERATURE, SCOOP_TO_WATER_RATIO, OPENING_SAFE_DAYS
)


VALID_STAGES = set(STAGE_INFO.keys())


def _validate_stage(current_stage: int) -> Optional[Dict]:
    if current_stage not in VALID_STAGES:
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


def match_stage_by_month(month_age: int) -> Dict:
    validation = _validate_month_age(month_age)
    if validation:
        return validation
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
    validation = _validate_stage(current_stage)
    if validation:
        return validation
    month_validation = _validate_month_age(month_age)
    if month_validation:
        return {
            "current_stage": current_stage,
            "current_stage_name": STAGE_INFO[current_stage]["name"],
            "recommended_stage": None,
            "recommended_stage_name": None,
            "suitability": "invalid",
            "suitability_score": 0.0,
            "suggestion": month_validation.get("error", "无效月龄"),
            "recommended": month_validation,
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


def analyze_weight_growth(month_age: int, weight_kg: float, gender: str, weight_history: Optional[List[Dict]] = None) -> Dict:
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


def analyze_nutrient_gap(month_age: int, current_stage: int, daily_intake_ml: float, weight_kg: float) -> Dict:
    if current_stage not in VALID_STAGES:
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


def calculate_transition_success_rate(
    month_age: int,
    current_stage: int,
    target_stage: int,
    digestion_status: str,
    weight_level: str,
    daily_intake_ml: float,
) -> Dict:
    if current_stage == target_stage:
        return {
            "success_rate": 1.0,
            "transition_needed": False,
            "message": "无需转段",
            "risk_factors": [],
            "suggestions": [],
        }

    if abs(current_stage - target_stage) > 1:
        return {
            "success_rate": 0.3,
            "transition_needed": True,
            "message": "跨段转奶风险高，建议逐段过渡",
            "risk_factors": ["跨段转奶"],
            "suggestions": ["先转至相邻段位", "采用混合过渡法", "密切观察消化情况"],
        }

    key = (min(current_stage, target_stage), max(current_stage, target_stage))
    base_rate = TRANSITION_SUCCESS_BASE.get(key, 0.8)
    risk_factors = []
    suggestions = []
    final_rate = base_rate

    if digestion_status in ["diarrhea", "allergy", "vomiting"]:
        final_rate -= 0.25
        risk_factors.append(f"消化异常: {DIGESTION_STATUS.get(digestion_status)}")
        suggestions.append("先治疗消化问题再转段")
    elif digestion_status in ["constipation", "mild_discomfort"]:
        final_rate -= 0.1
        risk_factors.append(f"消化不适: {DIGESTION_STATUS.get(digestion_status)}")
        suggestions.append("调整饮食改善消化后转段")

    if weight_level == "underweight":
        final_rate -= 0.15
        risk_factors.append("体重偏轻")
        suggestions.append("加强营养，体重稳定后转段")
    elif weight_level == "overweight":
        final_rate -= 0.05
        risk_factors.append("体重偏重")

    stage_info = STAGE_INFO.get(target_stage, STAGE_INFO[1])
    if daily_intake_ml < stage_info["daily_intake_min"] * 0.7:
        final_rate -= 0.1
        risk_factors.append("奶量摄入偏低")
        suggestions.append("确保奶量充足再转段")

    if month_age < stage_info["min_month"]:
        final_rate -= 0.15
        risk_factors.append("月龄未达到转段标准")
        suggestions.append("建议达到推荐月龄后再转段")

    final_rate = max(0.1, min(final_rate, 0.99))

    if final_rate >= 0.85:
        readiness = "ready"
        message = "转段条件良好，可逐步转段"
        suggestions.append("采用 7 天混合过渡法")
    elif final_rate >= 0.65:
        readiness = "cautious"
        message = "可以转段，需密切观察"
        suggestions.append("采用 14 天延长过渡法")
    else:
        readiness = "not_ready"
        message = "转段条件不佳，建议暂缓"

    return {
        "success_rate": round(final_rate, 3),
        "transition_needed": True,
        "readiness": readiness,
        "message": message,
        "base_rate": base_rate,
        "risk_factors": risk_factors,
        "suggestions": suggestions,
        "transition_method": "7天过渡法" if final_rate >= 0.85 else "14天过渡法",
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
    stage_validation = _validate_stage(current_stage)
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
    month_validation = _validate_month_age(month_age)
    if month_validation:
        return {
            "stage_suitability": {
                "current_stage": current_stage,
                "current_stage_name": STAGE_INFO[current_stage]["name"],
                "recommended_stage": None,
                "recommended_stage_name": None,
                "suitability": "invalid",
                "suitability_score": 0.0,
                "suggestion": month_validation.get("error", "无效月龄"),
                "recommended": month_validation,
            },
            "weight_analysis": None,
            "digestion_analysis": None,
            "nutrient_analysis": None,
            "transition_analysis": None,
            "warnings": [{"type": "invalid_month_age", "level": "high", "message": month_validation.get("error", "无效月龄")}],
            "need_doctor_consultation": False,
            "overall_suggestion": month_validation.get("error", "无效月龄"),
        }
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


def calculate_month_age(birth_date, current_date):
    months = (current_date.year - birth_date.year) * 12 + (current_date.month - birth_date.month)
    if current_date.day < birth_date.day:
        months -= 1
    return max(0, months)


def analyze_single_record(
    record,
    plan,
    baby,
    month_age,
):
    digestion_analysis = analyze_digestion(record.digestion_status, record.note)

    weight_analysis = None
    if record.weight_kg:
        weight_analysis = analyze_weight_growth(month_age, record.weight_kg, baby.gender)

    current_stage = plan.target_stage if record.new_formula_ratio >= 50 else plan.original_stage
    nutrient_analysis = analyze_nutrient_gap(
        month_age, current_stage, record.milk_intake_ml, record.weight_kg or 0
    )

    stage_suitability = calculate_stage_suitability(month_age, current_stage)

    is_alert = digestion_analysis["alert"]
    weight_ok = True
    if weight_analysis:
        weight_ok = not weight_analysis["need_attention"] and not weight_analysis.get("growth_abnormal", False)

    return {
        "record_id": record.id,
        "record_date": record.record_date.date().isoformat() if hasattr(record.record_date, "date") else str(record.record_date),
        "digestion_analysis": digestion_analysis,
        "weight_analysis": weight_analysis,
        "nutrient_analysis": nutrient_analysis,
        "stage_suitability": stage_suitability,
        "is_alert_day": is_alert or not weight_ok,
    }


def generate_phase_review(plan, baby, records):
    if not records:
        return {
            "transition_progress": 0.0,
            "risk_level": "low",
            "suggest_pause": False,
            "suggest_extend": False,
            "need_doctor_consultation": False,
            "success_rate": 0.0,
            "summary": "暂无跟踪记录",
            "phase_details": None,
        }

    from datetime import date as _date
    today = _date.today()
    start_date = plan.start_date.date() if hasattr(plan.start_date, "date") else plan.start_date
    days_passed = (today - start_date).days + 1
    transition_progress = min(1.0, max(0.0, days_passed / plan.transition_days))

    import json
    try:
        schedule = json.loads(plan.daily_ratio_schedule)
    except (json.JSONDecodeError, TypeError):
        schedule = []

    latest_record = records[-1]
    birth_date = baby.birth_date.date() if hasattr(baby.birth_date, "date") else baby.birth_date
    latest_record_date = latest_record.record_date.date() if hasattr(latest_record.record_date, "date") else latest_record.record_date
    month_age = calculate_month_age(birth_date, latest_record_date)

    record_analyses = []
    alert_days = 0
    consecutive_abnormal_days = 0
    max_consecutive_abnormal = 0
    current_consecutive = 0
    weights_with_dates = []
    digestion_alerts_count = 0
    success_rates = []

    prev_date = None
    for i, rec in enumerate(records):
        rec_date = rec.record_date.date() if hasattr(rec.record_date, "date") else rec.record_date
        if prev_date and (rec_date - prev_date).days > 1:
            current_consecutive = 0
        prev_date = rec_date

        ma = calculate_month_age(birth_date, rec_date)
        analysis = analyze_single_record(rec, plan, baby, ma)
        record_analyses.append(analysis)

        if analysis["is_alert_day"]:
            alert_days += 1
            current_consecutive += 1
            max_consecutive_abnormal = max(max_consecutive_abnormal, current_consecutive)
        else:
            current_consecutive = 0

        if analysis["digestion_analysis"]["alert"]:
            digestion_alerts_count += 1

        if rec.weight_kg:
            weights_with_dates.append({"date": rec_date.isoformat(), "weight_kg": rec.weight_kg})

        digestion_level = analysis["digestion_analysis"]["level"]
        if digestion_level == "normal":
            base_sr = 0.95
        elif digestion_level == "mild":
            base_sr = 0.8
        elif digestion_level == "moderate":
            base_sr = 0.5
        else:
            base_sr = 0.2

        nutrient_gap = analysis["nutrient_analysis"]["overall_gap_score"]
        nutrient_factor = max(0.7, 1.0 - nutrient_gap / 100)
        day_sr = round(base_sr * nutrient_factor, 3)
        success_rates.append(day_sr)

    avg_success_rate = round(sum(success_rates) / len(success_rates), 3) if success_rates else 0.0

    latest_analysis = record_analyses[-1]

    if latest_analysis["digestion_analysis"]["level"] == "severe":
        risk_level = "high"
        suggest_pause = True
        need_doctor = True
    elif max_consecutive_abnormal >= 3 or alert_days >= len(records) * 0.5:
        risk_level = "high"
        suggest_pause = True
        need_doctor = alert_days >= len(records) * 0.7 or max_consecutive_abnormal >= 5
    elif alert_days >= 2 or max_consecutive_abnormal >= 2:
        risk_level = "medium"
        suggest_pause = False
        need_doctor = latest_analysis["digestion_analysis"]["level"] == "severe"
    else:
        risk_level = "low"
        suggest_pause = False
        need_doctor = False

    suggest_extend = (
        risk_level in ("medium", "high")
        and transition_progress > 0.7
        and avg_success_rate < 0.7
    )

    final_suggestions = []
    if suggest_pause:
        final_suggestions.append("建议暂停转段，待宝宝状态稳定后再继续")
    if suggest_extend:
        final_suggestions.append("建议延长过渡期，减缓新奶粉比例提升速度")
    if need_doctor:
        final_suggestions.append("建议及时咨询医生")
    if risk_level == "low" and transition_progress < 1.0:
        final_suggestions.append("转段进展顺利，继续按计划推进")
    if transition_progress >= 1.0 and risk_level == "low":
        final_suggestions.append("转段已完成，建议继续观察1-2周")

    consecutive_abnormal_days = max_consecutive_abnormal

    return {
        "transition_progress": round(transition_progress, 3),
        "risk_level": risk_level,
        "suggest_pause": suggest_pause,
        "suggest_extend": suggest_extend,
        "need_doctor_consultation": need_doctor,
        "success_rate": avg_success_rate,
        "alert_days_count": alert_days,
        "consecutive_abnormal_days": consecutive_abnormal_days,
        "digestion_alert_count": digestion_alerts_count,
        "latest_record_analysis": latest_analysis,
        "summary": "；".join(final_suggestions) if final_suggestions else "转段进行中",
        "details": {
            "records_analyzed": len(record_analyses),
            "alert_ratio": round(alert_days / len(records), 3) if records else 0,
            "success_rate_trend": {
                "first_half": round(sum(success_rates[:len(success_rates)//2]) / max(1, len(success_rates)//2), 3),
                "second_half": round(sum(success_rates[len(success_rates)//2:]) / max(1, len(success_rates) - len(success_rates)//2), 3),
            } if success_rates else None,
            "weight_trend": weights_with_dates,
        },
    }


def generate_plan_review(plan, baby, records):
    if not records:
        return {
            "plan_id": plan.id,
            "plan_name": plan.plan_name,
            "has_data": False,
            "summary": "暂无跟踪记录，无法生成复盘",
        }

    import json
    try:
        schedule = json.loads(plan.daily_ratio_schedule)
    except (json.JSONDecodeError, TypeError):
        schedule = []

    from datetime import date as _date
    birth_date = baby.birth_date.date() if hasattr(baby.birth_date, "date") else baby.birth_date

    record_analyses = []
    alert_days = 0
    max_consecutive_abnormal = 0
    current_consecutive = 0
    weights_with_dates = []
    digestion_alerts_count = 0
    daily_success_rates = []
    nutrient_gap_scores = []
    prev_date = None

    for i, rec in enumerate(sorted(records, key=lambda r: r.record_date)):
        rec_date = rec.record_date.date() if hasattr(rec.record_date, "date") else rec.record_date
        if prev_date and (rec_date - prev_date).days > 1:
            current_consecutive = 0
        prev_date = rec_date

        ma = calculate_month_age(birth_date, rec_date)
        analysis = analyze_single_record(rec, plan, baby, ma)
        record_analyses.append(analysis)

        if analysis["is_alert_day"]:
            alert_days += 1
            current_consecutive += 1
            max_consecutive_abnormal = max(max_consecutive_abnormal, current_consecutive)
        else:
            current_consecutive = 0

        if analysis["digestion_analysis"]["alert"]:
            digestion_alerts_count += 1

        if rec.weight_kg:
            weights_with_dates.append({"date": rec_date.isoformat(), "weight_kg": rec.weight_kg})

        nutrient_gap_scores.append(analysis["nutrient_analysis"]["overall_gap_score"])

        digestion_level = analysis["digestion_analysis"]["level"]
        if digestion_level == "normal":
            base_sr = 0.95
        elif digestion_level == "mild":
            base_sr = 0.8
        elif digestion_level == "moderate":
            base_sr = 0.5
        else:
            base_sr = 0.2

        nutrient_gap = analysis["nutrient_analysis"]["overall_gap_score"]
        nutrient_factor = max(0.7, 1.0 - nutrient_gap / 100)
        day_sr = round(base_sr * nutrient_factor, 3)
        daily_success_rates.append({
            "date": rec_date.isoformat(),
            "success_rate": day_sr,
        })

    overall_success_rate = round(
        sum(x["success_rate"] for x in daily_success_rates) / len(daily_success_rates), 3
    ) if daily_success_rates else 0.0

    weight_trend = "stable"
    if len(weights_with_dates) >= 2:
        first_w = weights_with_dates[0]["weight_kg"]
        last_w = weights_with_dates[-1]["weight_kg"]
        if last_w > first_w * 1.01:
            weight_trend = "gaining"
        elif last_w < first_w * 0.99:
            weight_trend = "losing"

    nutrient_gap_change = None
    if len(nutrient_gap_scores) >= 2:
        first_half = nutrient_gap_scores[:len(nutrient_gap_scores)//2]
        second_half = nutrient_gap_scores[len(nutrient_gap_scores)//2:]
        avg_first = round(sum(first_half) / len(first_half), 2)
        avg_second = round(sum(second_half) / len(second_half), 2)
        nutrient_gap_change = {
            "first_half_avg": avg_first,
            "second_half_avg": avg_second,
            "change": round(avg_second - avg_first, 2),
            "trend": "improving" if avg_second < avg_first else ("worsening" if avg_second > avg_first else "stable"),
        }

    if max_consecutive_abnormal >= 5 or digestion_alerts_count >= len(records) * 0.6:
        final_risk = "high"
    elif max_consecutive_abnormal >= 3 or alert_days >= len(records) * 0.3:
        final_risk = "medium"
    else:
        final_risk = "low"

    final_suggestions = []
    if final_risk == "high":
        final_suggestions.append("转段过程风险较高，建议就医评估宝宝适应情况")
        if plan.status != "completed":
            final_suggestions.append("建议暂停转段或考虑转回原段位")
    elif final_risk == "medium":
        final_suggestions.append("存在一定适应问题，建议延长过渡期并密切观察")
        if nutrient_gap_change and nutrient_gap_change["trend"] == "worsening":
            final_suggestions.append("营养缺口有扩大趋势，建议评估奶量和辅食搭配")
    else:
        if plan.status == "completed":
            final_suggestions.append("转段成功完成，建议继续保持当前喂养方案并观察1-2周")
        else:
            final_suggestions.append("宝宝适应良好，可按计划继续推进转段")

    if weight_trend == "losing":
        final_suggestions.append("体重呈下降趋势，建议关注营养摄入并咨询医生")

    return {
        "plan_id": plan.id,
        "plan_name": plan.plan_name,
        "baby_id": baby.id,
        "baby_name": baby.baby_name,
        "has_data": True,
        "transition_success_rate": {
            "overall": overall_success_rate,
            "daily": daily_success_rates,
        },
        "consecutive_abnormal_days": max_consecutive_abnormal,
        "total_alert_days": alert_days,
        "total_records": len(records),
        "weight_trend": weight_trend,
        "weight_records": weights_with_dates,
        "digestion_alert_count": digestion_alerts_count,
        "nutrient_gap_change": nutrient_gap_change,
        "avg_nutrient_gap_score": round(sum(nutrient_gap_scores) / len(nutrient_gap_scores), 2) if nutrient_gap_scores else 0,
        "final_risk_level": final_risk,
        "final_suggestions": final_suggestions,
        "summary": "；".join(final_suggestions),
    }


def calculate_stock_days(current_remaining_grams: float, daily_intake_ml: float, scoop_weight_grams: float = 4.5) -> float:
    if daily_intake_ml <= 0 or current_remaining_grams <= 0:
        return 0.0
    grams_per_ml = scoop_weight_grams / SCOOP_TO_WATER_RATIO
    daily_grams_needed = daily_intake_ml * grams_per_ml
    return round(current_remaining_grams / daily_grams_needed, 1)


def analyze_formula_batch(
    batch,
    baby,
    latest_health_record=None,
) -> Dict:
    today = date.today()
    risks = []
    warnings = []
    suggestions = []

    birth_date = baby.birth_date.date() if hasattr(baby.birth_date, "date") else baby.birth_date
    month_age = calculate_month_age(birth_date, today)

    days_since_opening = (today - batch.opening_date).days
    days_until_expiry = (batch.expiry_date - today).days

    is_expired = days_until_expiry <= 0
    is_opening_overdue = days_since_opening > OPENING_SAFE_DAYS

    if is_expired:
        risks.append({
            "type": "expired",
            "level": "critical",
            "message": f"批次已过期 {abs(days_until_expiry)} 天，严禁继续使用",
        })
        suggestions.append("立即停用并丢弃该批次奶粉")
    elif days_until_expiry <= 7:
        warnings.append({
            "type": "expiry_warning",
            "level": "high",
            "message": f"保质期仅剩 {days_until_expiry} 天，建议尽快用完",
        })
        suggestions.append("尽快在保质期内用完，或考虑更换新批次")
    elif days_until_expiry <= 30:
        warnings.append({
            "type": "expiry_reminder",
            "level": "medium",
            "message": f"保质期还有 {days_until_expiry} 天",
        })

    if is_opening_overdue:
        risks.append({
            "type": "opening_overdue",
            "level": "high",
            "message": f"已开封 {days_since_opening} 天，超过建议 {OPENING_SAFE_DAYS} 天安全期，存在变质风险",
        })
        suggestions.append("建议停止使用该开封批次，更换新批次")
    elif days_since_opening >= OPENING_SAFE_DAYS - 7:
        warnings.append({
            "type": "opening_reminder",
            "level": "medium",
            "message": f"已开封 {days_since_opening} 天，建议在 {OPENING_SAFE_DAYS} 天内用完",
        })

    stage_suitability = calculate_stage_suitability(month_age, batch.stage)
    if stage_suitability["suitability"] == "mismatch":
        risks.append({
            "type": "stage_mismatch",
            "level": "high",
            "message": f"当前批次段位({batch.stage}段)与宝宝月龄({month_age}个月)不匹配",
        })
        suggestions.append(stage_suitability["suggestion"])
    elif stage_suitability["suitability"] == "acceptable":
        warnings.append({
            "type": "stage_warning",
            "level": "medium",
            "message": stage_suitability["suggestion"],
        })

    stock_days = 0.0
    if latest_health_record:
        stock_days = calculate_stock_days(
            batch.current_remaining_grams,
            latest_health_record.daily_intake_ml
        )
        if stock_days <= 3:
            warnings.append({
                "type": "low_stock",
                "level": "high",
                "message": f"库存仅剩约 {stock_days} 天用量，请及时补货",
            })
            suggestions.append("库存不足，建议立即购买新批次")
        elif stock_days <= 7:
            warnings.append({
                "type": "stock_reminder",
                "level": "medium",
                "message": f"库存约可用 {stock_days} 天，建议准备补货",
            })

    if batch.current_remaining_grams <= 0:
        risks.append({
            "type": "out_of_stock",
            "level": "high",
            "message": "该批次库存已用完",
        })
        suggestions.append("该批次已用完，请更换新批次")

    if not batch.is_active:
        warnings.append({
            "type": "inactive",
            "level": "medium",
            "message": "该批次已被停用",
        })

    risk_level = "low"
    has_critical = any(r["level"] == "critical" for r in risks)
    has_high_risk = any(r["level"] == "high" for r in risks) or any(w["level"] == "high" for w in warnings)
    has_medium = any(w["level"] == "medium" for w in warnings)

    if has_critical:
        risk_level = "critical"
    elif has_high_risk:
        risk_level = "high"
    elif has_medium:
        risk_level = "medium"

    should_replace = is_expired or is_opening_overdue or batch.current_remaining_grams <= 0

    nutrient_analysis = None
    digestion_analysis = None
    if latest_health_record:
        nutrient_analysis = analyze_nutrient_gap(
            month_age, batch.stage, latest_health_record.daily_intake_ml, latest_health_record.weight_kg
        )
        digestion_analysis = analyze_digestion(
            latest_health_record.digestion_status, latest_health_record.digestion_note
        )

    return {
        "batch_id": batch.id,
        "brand_name": batch.brand_name,
        "product_name": batch.product_name,
        "stage": batch.stage,
        "batch_number": batch.batch_number,
        "month_age": month_age,
        "days_since_opening": days_since_opening,
        "days_until_expiry": days_until_expiry,
        "is_expired": is_expired,
        "is_opening_overdue": is_opening_overdue,
        "stock_remaining_grams": batch.current_remaining_grams,
        "stock_available_days": stock_days,
        "storage_method": batch.storage_method,
        "storage_method_name": STORAGE_METHOD_NAMES.get(batch.storage_method, batch.storage_method),
        "is_active": batch.is_active,
        "stage_suitability": stage_suitability,
        "nutrient_analysis": nutrient_analysis,
        "digestion_analysis": digestion_analysis,
        "risks": risks,
        "warnings": warnings,
        "suggestions": suggestions,
        "risk_level": risk_level,
        "should_replace_batch": should_replace,
    }


def analyze_brewing_record(
    record,
    batch,
    baby,
    latest_health_record=None,
) -> Dict:
    today = date.today()
    issues = []
    warnings = []
    suggestions = []

    birth_date = baby.birth_date.date() if hasattr(baby.birth_date, "date") else baby.birth_date
    month_age = calculate_month_age(birth_date, today)

    if record.water_temperature < MIN_WATER_TEMPERATURE:
        issues.append({
            "type": "water_temp_low",
            "level": "medium",
            "message": f"水温过低: {record.water_temperature}°C，建议水温在 {MIN_WATER_TEMPERATURE}-{MAX_WATER_TEMPERATURE}°C",
        })
        suggestions.append("下次冲泡时适当提高水温，过低的水温可能影响奶粉溶解和营养吸收")
    elif record.water_temperature > MAX_WATER_TEMPERATURE:
        issues.append({
            "type": "water_temp_high",
            "level": "high",
            "message": f"水温过高: {record.water_temperature}°C，可能破坏营养成分",
        })
        suggestions.append("下次冲泡时降低水温，过高的水温会破坏奶粉中的营养成分")

    expected_water = record.formula_scoops * SCOOP_TO_WATER_RATIO
    water_deviation = abs(record.water_volume_ml - expected_water) / expected_water
    if water_deviation > 0.2:
        ratio_type = "too_thick" if record.water_volume_ml < expected_water else "too_thin"
        issues.append({
            "type": f"ratio_{ratio_type}",
            "level": "high",
            "message": f"冲泡比例异常: {record.formula_scoops}勺配 {record.water_volume_ml}ml 水，建议约 {expected_water:.0f}ml (每勺{SCOOP_TO_WATER_RATIO}ml)",
        })
        if ratio_type == "too_thick":
            suggestions.append("奶粉浓度过高，可能增加宝宝肠胃负担，建议增加水量或减少奶粉量")
        else:
            suggestions.append("奶粉浓度过低，可能导致营养摄入不足，建议减少水量或增加奶粉量")

    if record.actual_consumed_ml < record.water_volume_ml * 0.5:
        warnings.append({
            "type": "low_consumption",
            "level": "medium",
            "message": f"实际饮用量偏低: {record.actual_consumed_ml}ml，仅为冲泡量的 {record.actual_consumed_ml/record.water_volume_ml*100:.0f}%",
        })
        suggestions.append("注意观察宝宝食欲，如持续饮用量偏低建议咨询医生")

    if record.has_remaining and record.remaining_handling == "stored":
        warnings.append({
            "type": "remaining_stored",
            "level": "medium",
            "message": "剩余奶水已储存，建议在1小时内食用完",
        })
        suggestions.append("剩余奶水建议丢弃，如需储存应冷藏并在1小时内用完")
    elif record.has_remaining and record.remaining_handling == "used_later":
        warnings.append({
            "type": "remaining_used_later",
            "level": "high",
            "message": "剩余奶水留待稍后使用，存在细菌滋生风险",
        })
        suggestions.append("建议丢弃剩余奶水，新鲜冲泡更安全")

    wasted_ml = record.water_volume_ml - record.actual_consumed_ml
    if wasted_ml > 0:
        warnings.append({
            "type": "milk_waste",
            "level": "low",
            "message": f"本次浪费约 {wasted_ml:.0f}ml 奶水",
        })

    batch_analysis = analyze_formula_batch(batch, baby, latest_health_record)
    if batch_analysis["risks"]:
        for risk in batch_analysis["risks"]:
            issues.append(risk)
        suggestions.extend(batch_analysis["suggestions"])

    risk_level = "low"
    has_high = any(i["level"] == "high" for i in issues)
    has_medium = any(i["level"] == "medium" for i in issues) or any(w["level"] == "medium" for w in warnings)

    if has_high:
        risk_level = "high"
    elif has_medium:
        risk_level = "medium"

    return {
        "record_id": record.id,
        "batch_id": record.batch_id,
        "baby_id": record.baby_id,
        "month_age": month_age,
        "brewing_time": record.brewing_time.isoformat() if hasattr(record.brewing_time, "isoformat") else str(record.brewing_time),
        "water_temperature": record.water_temperature,
        "formula_scoops": record.formula_scoops,
        "water_volume_ml": record.water_volume_ml,
        "expected_water_volume_ml": round(expected_water, 1),
        "ratio_deviation_percent": round(water_deviation * 100, 1),
        "actual_consumed_ml": record.actual_consumed_ml,
        "wasted_ml": round(wasted_ml, 1),
        "has_remaining": record.has_remaining,
        "remaining_handling": record.remaining_handling,
        "remaining_handling_name": REMAINING_HANDLING_NAMES.get(record.remaining_handling, record.remaining_handling) if record.remaining_handling else None,
        "issues": issues,
        "warnings": warnings,
        "suggestions": suggestions,
        "risk_level": risk_level,
        "batch_risk_level": batch_analysis["risk_level"],
    }


def generate_brewing_daily_report(
    baby,
    report_date: date,
    records: List,
    batches: List,
    latest_health_record=None,
) -> Dict:
    total_brewing_count = len(records)
    total_water_volume = sum(r.water_volume_ml for r in records)
    total_formula_scoops = sum(r.formula_scoops for r in records)
    total_actual_consumed = sum(r.actual_consumed_ml for r in records)
    total_wasted = total_water_volume - total_actual_consumed

    batch_usage = {}
    abnormal_details = []
    total_abnormal = 0
    records_with_analysis = []

    for record in records:
        batch = next((b for b in batches if b.id == record.batch_id), None)
        if not batch:
            continue

        analysis = analyze_brewing_record(record, batch, baby, latest_health_record)
        record_dict = {
            "id": record.id,
            "baby_id": record.baby_id,
            "batch_id": record.batch_id,
            "brewing_time": record.brewing_time,
            "water_temperature": record.water_temperature,
            "formula_scoops": record.formula_scoops,
            "water_volume_ml": record.water_volume_ml,
            "actual_consumed_ml": record.actual_consumed_ml,
            "has_remaining": record.has_remaining,
            "remaining_handling": record.remaining_handling,
            "abnormal_notes": record.abnormal_notes,
            "created_at": record.created_at,
            "safety_analysis": analysis,
        }
        records_with_analysis.append(record_dict)

        batch_key = f"{batch.id}-{batch.brand_name}-{batch.product_name}"
        if batch_key not in batch_usage:
            batch_usage[batch_key] = {
                "batch_id": batch.id,
                "brand_name": batch.brand_name,
                "product_name": batch.product_name,
                "stage": batch.stage,
                "batch_number": batch.batch_number,
                "usage_count": 0,
                "total_scoops": 0.0,
                "total_water_ml": 0.0,
                "total_consumed_ml": 0.0,
            }
        batch_usage[batch_key]["usage_count"] += 1
        batch_usage[batch_key]["total_scoops"] += record.formula_scoops
        batch_usage[batch_key]["total_water_ml"] += record.water_volume_ml
        batch_usage[batch_key]["total_consumed_ml"] += record.actual_consumed_ml

        record_abnormal = len(analysis["issues"])
        total_abnormal += record_abnormal
        if record_abnormal > 0:
            abnormal_details.append({
                "record_id": record.id,
                "brewing_time": record.brewing_time.isoformat() if hasattr(record.brewing_time, "isoformat") else str(record.brewing_time),
                "issues": analysis["issues"],
                "risk_level": analysis["risk_level"],
            })

    batch_usage_distribution = list(batch_usage.values())
    for item in batch_usage_distribution:
        item["usage_percent"] = round(item["usage_count"] / total_brewing_count * 100, 1) if total_brewing_count > 0 else 0

    overall_suggestions = []
    risk_level = "low"

    if total_brewing_count == 0:
        overall_suggestions.append("今日暂无冲泡记录")
        risk_level = "low"
    else:
        if total_wasted > total_water_volume * 0.3:
            overall_suggestions.append(f"今日浪费比例较高({total_wasted/total_water_volume*100:.0f}%)，建议根据宝宝食量调整冲泡量")
            risk_level = "medium"

        if total_abnormal >= 3:
            overall_suggestions.append(f"今日出现 {total_abnormal} 次异常冲泡，请注意冲泡规范")
            risk_level = "high"
        elif total_abnormal >= 1:
            overall_suggestions.append(f"今日出现 {total_abnormal} 次异常冲泡，建议关注")
            risk_level = "medium" if risk_level == "low" else risk_level

        if total_actual_consumed < 400 and latest_health_record:
            intake_range = STAGE_INFO.get(baby.current_stage, {}).get("daily_intake_range", [600, 1000])
            if total_actual_consumed < intake_range[0] * 0.5:
                overall_suggestions.append("今日总摄入量偏低，建议关注宝宝食欲和喂养频次")
                risk_level = "high"

        if not overall_suggestions:
            overall_suggestions.append("今日冲泡情况良好，继续保持")

    return {
        "baby_id": baby.id,
        "baby_name": baby.baby_name,
        "report_date": report_date.isoformat(),
        "total_brewing_count": total_brewing_count,
        "total_water_volume_ml": round(total_water_volume, 1),
        "total_formula_scoops": round(total_formula_scoops, 1),
        "total_actual_consumed_ml": round(total_actual_consumed, 1),
        "total_wasted_ml": round(total_wasted, 1),
        "batch_usage_distribution": batch_usage_distribution,
        "abnormal_count": total_abnormal,
        "abnormal_details": abnormal_details,
        "risk_level": risk_level,
        "overall_suggestions": overall_suggestions,
        "records": records_with_analysis,
    }


def analyze_abnormal_event_risk(
    event_data: Dict,
    baby,
    batch=None,
    brewing_record=None,
    latest_health_record=None,
    active_transition_plans=None,
    recent_events=None,
    db_batches=None,
) -> Dict:
    import json

    suspected_causes = []
    risk_score = 0.0
    brewing_abnormal_related = False
    batch_risk_related = False
    suggest_pause_batch = False
    suggest_stop_transition = False
    suggest_doctor_consultation = False
    observation_suggestions = []

    event_type = event_data.get("event_type", "other")
    severity = event_data.get("severity_level", "mild")
    body_temp = event_data.get("body_temperature")
    digestion_status = event_data.get("digestion_status")
    daily_intake = event_data.get("daily_milk_intake_ml")
    weight = event_data.get("weight_kg")

    severity_weight = {"mild": 20, "moderate": 40, "severe": 65, "critical": 85}
    risk_score += severity_weight.get(severity, 20)

    type_risk_map = {
        "vomiting": 15, "diarrhea": 20, "constipation": 10,
        "allergy": 25, "fever": 20, "low_appetite": 10,
        "bloating": 8, "skin_rash": 15, "other": 5,
    }
    risk_score += type_risk_map.get(event_type, 5)

    if body_temp is not None:
        if body_temp >= 38.5:
            risk_score += 25
            suspected_causes.append(f"高热 {body_temp}°C，需警惕感染")
            suggest_doctor_consultation = True
        elif body_temp >= 37.5:
            risk_score += 12
            suspected_causes.append(f"低热 {body_temp}°C，建议观察")

    if digestion_status and digestion_status != "normal":
        digestion_info = analyze_digestion(digestion_status)
        if digestion_info["alert"]:
            risk_score += 15
            suspected_causes.append(f"消化异常: {digestion_info['description']}")
        if digestion_status == "diarrhea":
            suspected_causes.append("腹泻可能与奶粉不耐受、冲泡卫生或批次有关")
            if batch:
                batch_risk_related = True
        elif digestion_status == "allergy":
            suspected_causes.append("过敏反应可能与奶粉配方或批次变更有关")
            if batch:
                batch_risk_related = True
                suggest_pause_batch = True
        elif digestion_status == "vomiting":
            suspected_causes.append("吐奶/呕吐可能与冲泡浓度、温度或进食方式有关")
            brewing_abnormal_related = True

    if daily_intake and latest_health_record:
        birth_date = baby.birth_date.date() if hasattr(baby.birth_date, "date") else baby.birth_date
        today = date.today()
        month_age = calculate_month_age(birth_date, today)
        stage_info = STAGE_INFO.get(baby.current_stage, STAGE_INFO[1])
        min_intake = stage_info["daily_intake_min"]
        max_intake = stage_info["daily_intake_max"]
        if daily_intake < min_intake * 0.5:
            risk_score += 15
            suspected_causes.append(f"奶量摄入严重不足: {daily_intake}ml，建议摄入量 {min_intake}-{max_intake}ml")
        elif daily_intake < min_intake * 0.7:
            risk_score += 8
            suspected_causes.append(f"奶量摄入偏低: {daily_intake}ml")

    if weight and baby:
        birth_date = baby.birth_date.date() if hasattr(baby.birth_date, "date") else baby.birth_date
        today = date.today()
        month_age = calculate_month_age(birth_date, today)
        weight_analysis = analyze_weight_growth(month_age, weight, baby.gender)
        if weight_analysis.get("need_attention"):
            risk_score += 10
            suspected_causes.append(f"体重指标异常: {weight_analysis['weight_status']}")
            if weight_analysis["weight_level"] == "underweight":
                suggest_doctor_consultation = True

    if brewing_record:
        brewing_analysis = analyze_brewing_record(
            brewing_record,
            batch if batch else (db_batches[brewing_record.batch_id] if db_batches and brewing_record.batch_id in db_batches else None),
            baby,
            latest_health_record,
        )
        if brewing_analysis["issues"]:
            brewing_abnormal_related = True
            risk_score += len([i for i in brewing_analysis["issues"] if i["level"] == "high"]) * 12
            risk_score += len([i for i in brewing_analysis["issues"] if i["level"] == "medium"]) * 6
            for issue in brewing_analysis["issues"][:3]:
                suspected_causes.append(f"冲泡异常: {issue['message']}")
            if brewing_record.formula_scoops * SCOOP_TO_WATER_RATIO > brewing_record.water_volume_ml * 1.2:
                suspected_causes.append("奶粉浓度过高可能加重肠胃负担")

    if batch:
        batch_analysis = analyze_formula_batch(batch, baby, latest_health_record)
        if batch_analysis["risks"]:
            batch_risk_related = True
            risk_score += len([r for r in batch_analysis["risks"] if r["level"] == "critical"]) * 30
            risk_score += len([r for r in batch_analysis["risks"] if r["level"] == "high"]) * 15
            for risk in batch_analysis["risks"][:2]:
                suspected_causes.append(f"批次风险: {risk['message']}")
            if batch_analysis.get("should_replace_batch"):
                suggest_pause_batch = True
        if batch_analysis["stage_suitability"]["suitability"] == "mismatch":
            risk_score += 10
            suspected_causes.append(f"段位不匹配: {batch_analysis['stage_suitability']['suggestion']}")

    if active_transition_plans:
        for plan in active_transition_plans:
            if plan.status == "in_progress":
                suggest_stop_transition = True
                suspected_causes.append(f"正在进行转段计划（{plan.plan_name}），建议暂停观察")
                risk_score += 10
                break

    if recent_events and len(recent_events) >= 3:
        risk_score += 15
        suspected_causes.append(f"近期已发生 {len(recent_events)} 次异常事件，复发风险较高")
        suggest_doctor_consultation = True
    elif recent_events and len(recent_events) >= 1:
        risk_score += 8
        suspected_causes.append("近期存在异常事件史，需关注是否为反复问题")

    if severity in ("severe", "critical"):
        suggest_doctor_consultation = True
    if event_type in ("allergy", "fever") and severity != "mild":
        suggest_doctor_consultation = True

    if risk_score >= 85:
        risk_level = "critical"
    elif risk_score >= 60:
        risk_level = "high"
    elif risk_score >= 35:
        risk_level = "medium"
    else:
        risk_level = "low"

    if not suspected_causes:
        if event_type in ("vomiting", "diarrhea", "bloating"):
            suspected_causes.append("暂未发现明确关联因素，可能与宝宝肠胃状态或进食习惯有关")
        elif event_type == "low_appetite":
            suspected_causes.append("食欲下降可能与情绪、环境或身体状态变化有关")
        elif event_type == "fever":
            suspected_causes.append("发热可能与感染或环境因素有关，需密切观察体温变化")
        else:
            suspected_causes.append("建议持续观察症状变化，记录相关喂养数据")

    observation_suggestions.append(f"密切关注{SEVERITY_LEVEL_MAP.get(event_type, '症状')}变化，每2-4小时观察一次")
    if event_type == "diarrhea":
        observation_suggestions.append("注意补充水分，防止脱水，记录排便次数和性状")
    elif event_type == "vomiting":
        observation_suggestions.append("喂奶后竖抱拍嗝，减少活动，少量多次喂养")
    elif event_type == "fever":
        observation_suggestions.append("定时测量体温，物理降温，体温超过38.5°C及时就医")
    elif event_type == "allergy":
        observation_suggestions.append("注意皮疹、呼吸等过敏表现，避免接触可疑过敏源")
    elif event_type == "constipation":
        observation_suggestions.append("可适当增加饮水量，腹部轻柔按摩促进蠕动")
    if batch and suggest_pause_batch:
        observation_suggestions.append(f"建议暂停使用当前批次（{batch.batch_number}），更换其他批次或品牌")
    if suggest_stop_transition:
        observation_suggestions.append("建议暂停转段计划，待宝宝状态恢复稳定后再评估")
    if suggest_doctor_consultation:
        observation_suggestions.append("建议尽快就医咨询，携带喂养记录和症状描述")
    if risk_level == "low":
        observation_suggestions.append("风险较低，按上述建议居家观察即可，如有加重及时处理")

    return {
        "risk_level": risk_level,
        "risk_score": round(risk_score, 1),
        "suspected_causes": suspected_causes,
        "brewing_abnormal_related": brewing_abnormal_related,
        "batch_risk_related": batch_risk_related,
        "suggest_pause_batch": suggest_pause_batch,
        "suggest_stop_transition": suggest_stop_transition,
        "suggest_doctor_consultation": suggest_doctor_consultation,
        "observation_suggestions": observation_suggestions,
    }


SEVERITY_LEVEL_MAP = {
    "vomiting": "呕吐", "diarrhea": "腹泻", "constipation": "便秘",
    "allergy": "过敏反应", "fever": "体温", "low_appetite": "食欲",
    "bloating": "腹胀", "skin_rash": "皮疹", "other": "症状",
}


def generate_abnormal_event_replay(
    baby,
    start_date: date,
    end_date: date,
    events: List,
    batches_map: Dict = None,
    active_transition_plans: List = None,
) -> Dict:
    import json
    from collections import Counter, defaultdict

    batches_map = batches_map or {}

    total_event_count = len(events)
    closed_event_count = sum(1 for e in events if e.status == "closed")
    handling_completion_rate = round(closed_event_count / total_event_count * 100, 1) if total_event_count > 0 else 0.0

    type_counter = Counter()
    high_risk_count = 0
    digestion_abnormal_count = 0
    transition_related_count = 0
    batch_event_counter = defaultdict(int)
    recurrence_event_types = []

    for event in events:
        type_counter[event.event_type] += 1
        if event.auto_risk_level in ("high", "critical"):
            high_risk_count += 1
        digestion_types = {"vomiting", "diarrhea", "constipation", "bloating", "allergy"}
        if event.event_type in digestion_types or (event.digestion_status and event.digestion_status != "normal"):
            digestion_abnormal_count += 1
        if event.auto_suggest_stop_transition:
            transition_related_count += 1
        if event.batch_id:
            batch_info = batches_map.get(event.batch_id, {})
            label = f"批次#{event.batch_id}"
            if batch_info:
                label = f"{batch_info.get('brand_name','')}-{batch_info.get('batch_number', '')}(#{event.batch_id})"
            batch_event_counter[label] += 1

    type_distribution = []
    for t, cnt in type_counter.items():
        type_distribution.append({
            "event_type": t,
            "event_type_name": ABNORMAL_EVENT_TYPE_NAMES.get(t, t),
            "count": cnt,
            "percent": round(cnt / total_event_count * 100, 1) if total_event_count > 0 else 0,
        })
    type_distribution.sort(key=lambda x: -x["count"])

    related_batch_ranking = sorted(
        [{"batch_label": k, "event_count": v} for k, v in batch_event_counter.items()],
        key=lambda x: -x["event_count"],
    )
    for i, item in enumerate(related_batch_ranking):
        item["rank"] = i + 1
        item["percent"] = round(item["event_count"] / total_event_count * 100, 1) if total_event_count > 0 else 0

    recurrence_risk_score = 0.0
    recurrence_risk_factors = []

    if total_event_count >= 5:
        recurrence_risk_score += 35
        recurrence_risk_factors.append(f"统计周期内异常事件次数较多（{total_event_count}次）")
    elif total_event_count >= 3:
        recurrence_risk_score += 20
        recurrence_risk_factors.append(f"统计周期内存在多次异常事件（{total_event_count}次）")

    if high_risk_count >= 2:
        recurrence_risk_score += 30
        recurrence_risk_factors.append(f"高风险/危重事件达 {high_risk_count} 次")
    elif high_risk_count >= 1:
        recurrence_risk_score += 15
        recurrence_risk_factors.append(f"存在 {high_risk_count} 次高风险事件")

    recent_window_days = 7
    today = date.today()
    recent_start = today - timedelta(days=recent_window_days)
    recent_count = 0
    for e in events:
        e_date = e.event_time.date() if hasattr(e.event_time, "date") else e.event_time
        if isinstance(e_date, datetime):
            e_date = e_date.date()
        if e_date >= recent_start:
            recent_count += 1
    if recent_count >= 2:
        recurrence_risk_score += 25
        recurrence_risk_factors.append(f"近7天内发生 {recent_count} 次异常，时间密度较高")

    if handling_completion_rate < 70:
        recurrence_risk_score += 15
        recurrence_risk_factors.append(f"处置完成率偏低（{handling_completion_rate}%），可能存在未闭环的风险因素")

    transition_in_progress = False
    if active_transition_plans:
        for p in active_transition_plans:
            if p.status == "in_progress":
                transition_in_progress = True
                break
    if transition_in_progress and transition_related_count > 0:
        recurrence_risk_score += 15
        recurrence_risk_factors.append("转段进行中且存在转段相关异常，需警惕持续适应问题")

    if related_batch_ranking and related_batch_ranking[0]["event_count"] >= 3:
        recurrence_risk_score += 20
        recurrence_risk_factors.append(f"同一批次关联事件较多（{related_batch_ranking[0]['batch_label']}: {related_batch_ranking[0]['event_count']}次）")

    batch_risk_related_count = sum(1 for e in events if e.auto_batch_risk_related)
    if batch_risk_related_count >= 2:
        recurrence_risk_score += 15
        recurrence_risk_factors.append(f"{batch_risk_related_count} 次事件被判定与批次风险相关")

    if not recurrence_risk_factors:
        recurrence_risk_factors.append("统计周期内风险因素较少，整体态势平稳")

    recurrence_risk_score = min(100.0, recurrence_risk_score)
    if recurrence_risk_score >= 70:
        recurrence_risk_level = "high"
    elif recurrence_risk_score >= 40:
        recurrence_risk_level = "medium"
    else:
        recurrence_risk_level = "low"

    suggestions = []
    if recurrence_risk_level == "high":
        suggestions.append("复发风险较高，建议系统性排查喂养方案、批次质量和宝宝健康状况")
        suggestions.append("建议尽快进行医生咨询，必要时做全面身体检查")
        if related_batch_ranking:
            suggestions.append(f"重点排查关联批次: {related_batch_ranking[0]['batch_label']}")
        if transition_in_progress:
            suggestions.append("建议暂停转段计划，待状态稳定后重新评估")
    elif recurrence_risk_level == "medium":
        suggestions.append("存在一定复发风险，需加强日常观察和喂养记录")
        if digestion_abnormal_count > total_event_count * 0.5:
            suggestions.append("消化类异常占比较高，建议评估奶粉配方适配性和冲泡流程")
        if handling_completion_rate < 80:
            suggestions.append("建议提升事件处置闭环率，确保每个异常都有完整跟踪")
    else:
        suggestions.append("复发风险较低，继续保持良好的喂养习惯和事件记录习惯")
        suggestions.append("定期进行宝宝健康评估，防患于未然")

    overall_suggestion = "；".join(suggestions)

    return {
        "baby_id": baby.id,
        "baby_name": baby.baby_name,
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "total_event_count": total_event_count,
        "type_distribution": type_distribution,
        "high_risk_count": high_risk_count,
        "closed_event_count": closed_event_count,
        "handling_completion_rate": handling_completion_rate,
        "related_batch_ranking": related_batch_ranking,
        "digestion_abnormal_count": digestion_abnormal_count,
        "transition_related_count": transition_related_count,
        "recurrence_risk_level": recurrence_risk_level,
        "recurrence_risk_score": round(recurrence_risk_score, 1),
        "recurrence_risk_factors": recurrence_risk_factors,
        "overall_suggestion": overall_suggestion,
    }


ABNORMAL_EVENT_TYPE_NAMES = {
    "vomiting": "呕吐", "diarrhea": "腹泻", "constipation": "便秘",
    "allergy": "过敏", "fever": "发热", "low_appetite": "食欲差",
    "bloating": "腹胀", "skin_rash": "皮疹", "other": "其他",
}


def generate_feeding_report(
    baby,
    report_type: str,
    period_start: date,
    period_end: date,
    health_records: List,
    brewing_records: List,
    formula_batches: List,
    abnormal_events: List,
    transition_plans: List,
    transition_records: List,
    doctor_consultations: List,
) -> Dict:
    import json

    period_days = (period_end - period_start).days + 1
    birth_date = baby.birth_date.date() if hasattr(baby.birth_date, "date") else baby.birth_date
    month_age_start = calculate_month_age(birth_date, period_start)
    month_age_end = calculate_month_age(birth_date, period_end)

    total_milk_ml = 0.0
    brewing_days = set()
    brewing_abnormal_count = 0
    batch_risk_count = 0
    digestion_abnormal_count = 0
    batch_usage = {}

    for record in brewing_records:
        total_milk_ml += record.actual_consumed_ml
        brewing_days.add(record.brewing_time.date())
        batch = next((b for b in formula_batches if b.id == record.batch_id), None)
        if batch:
            analysis = analyze_brewing_record(record, batch, baby)
            if analysis["issues"]:
                brewing_abnormal_count += 1
            if analysis["batch_risk_level"] in ("high", "critical"):
                batch_risk_count += 1
            batch_key = f"{batch.id}-{batch.brand_name}-{batch.product_name}"
            if batch_key not in batch_usage:
                batch_usage[batch_key] = {
                    "batch_id": batch.id,
                    "brand_name": batch.brand_name,
                    "product_name": batch.product_name,
                    "stage": batch.stage,
                    "batch_number": batch.batch_number,
                    "total_consumed_ml": 0.0,
                    "usage_count": 0,
                }
            batch_usage[batch_key]["total_consumed_ml"] += record.actual_consumed_ml
            batch_usage[batch_key]["usage_count"] += 1

    avg_daily_milk_ml = round(total_milk_ml / period_days, 1) if period_days > 0 else 0.0

    weight_start = None
    weight_end = None
    weight_change_kg = 0.0
    nutrient_gap_trend = []
    stage_match_records = []

    sorted_health = sorted(health_records, key=lambda r: r.record_date)
    if sorted_health:
        first_record = sorted_health[0]
        last_record = sorted_health[-1]
        weight_start = first_record.weight_kg
        weight_end = last_record.weight_kg
        weight_change_kg = round(weight_end - weight_start, 3)

        for rec in sorted_health:
            nutrient_analysis = analyze_nutrient_gap(
                rec.month_age, rec.current_stage, rec.daily_intake_ml, rec.weight_kg
            )
            nutrient_gap_trend.append({
                "date": rec.record_date.date().isoformat() if hasattr(rec.record_date, "date") else str(rec.record_date),
                "gap_score": nutrient_analysis["overall_gap_score"],
                "status": nutrient_analysis["overall_status"],
            })
            stage_suit = calculate_stage_suitability(rec.month_age, rec.current_stage)
            stage_match_records.append({
                "date": rec.record_date.date().isoformat() if hasattr(rec.record_date, "date") else str(rec.record_date),
                "current_stage": rec.current_stage,
                "recommended_stage": stage_suit["recommended_stage"],
                "suitability": stage_suit["suitability"],
                "suitability_score": stage_suit["suitability_score"],
            })

    digestion_abnormal_statuses = {"constipation", "diarrhea", "allergy", "vomiting"}
    for rec in sorted_health:
        if rec.digestion_status in digestion_abnormal_statuses:
            digestion_abnormal_count += 1

    transition_progress = 0.0
    active_transition_plan = None
    if transition_plans:
        active_plans = [p for p in transition_plans if p.status == "in_progress"]
        if active_plans:
            active_transition_plan = active_plans[0]
        else:
            active_transition_plan = transition_plans[0]

        if active_transition_plan:
            plan_records = [r for r in transition_records if r.plan_id == active_transition_plan.id]
            sorted_plan_recs = sorted(plan_records, key=lambda r: r.record_date)
            if sorted_plan_recs:
                plan_start = active_transition_plan.start_date.date() if hasattr(active_transition_plan.start_date, "date") else active_transition_plan.start_date
                days_passed = (period_end - plan_start).days + 1
                transition_progress = min(1.0, max(0.0, days_passed / active_transition_plan.transition_days))
                transition_progress = round(transition_progress, 3)

    doctor_consultation_count = len(doctor_consultations)

    total_events = len(abnormal_events)
    closed_events = sum(1 for e in abnormal_events if e.status == "closed")
    abnormal_event_completion_rate = round(
        (closed_events / total_events * 100) if total_events > 0 else 100.0, 1
    )

    batch_stock_summary = []
    for batch in formula_batches:
        batch_analysis = analyze_formula_batch(batch, baby, sorted_health[-1] if sorted_health else None)
        batch_stock_summary.append({
            "batch_id": batch.id,
            "brand_name": batch.brand_name,
            "product_name": batch.product_name,
            "stage": batch.stage,
            "batch_number": batch.batch_number,
            "current_remaining_grams": batch.current_remaining_grams,
            "stock_available_days": batch_analysis.get("stock_available_days", 0),
            "risk_level": batch_analysis["risk_level"],
        })

    overall_score = _calculate_overall_score(
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
        health_records_count=len(sorted_health),
    )

    summary = _generate_report_summary(
        report_type=report_type,
        baby_name=baby.baby_name,
        period_start=period_start,
        period_end=period_end,
        total_milk_ml=total_milk_ml,
        avg_daily_milk_ml=avg_daily_milk_ml,
        weight_change_kg=weight_change_kg,
        overall_score=overall_score,
        abnormal_event_count=total_events,
        digestion_abnormal_count=digestion_abnormal_count,
    )

    report_data = {
        "baby_profile": {
            "baby_name": baby.baby_name,
            "gender": baby.gender,
            "birth_date": birth_date.isoformat(),
            "current_stage": baby.current_stage,
            "guardian_name": baby.guardian_name,
            "month_age_start": month_age_start,
            "month_age_end": month_age_end,
        },
        "period_info": {
            "report_type": report_type,
            "period_start": period_start.isoformat(),
            "period_end": period_end.isoformat(),
            "period_days": period_days,
        },
        "milk_intake": {
            "total_milk_ml": round(total_milk_ml, 1),
            "avg_daily_milk_ml": avg_daily_milk_ml,
            "brewing_days_count": len(brewing_days),
            "brewing_total_count": len(brewing_records),
            "batch_usage_distribution": list(batch_usage.values()),
        },
        "growth": {
            "weight_start_kg": weight_start,
            "weight_end_kg": weight_end,
            "weight_change_kg": weight_change_kg,
            "health_records_count": len(sorted_health),
        },
        "digestion": {
            "digestion_abnormal_count": digestion_abnormal_count,
            "digestion_records": [
                {
                    "date": r.record_date.date().isoformat() if hasattr(r.record_date, "date") else str(r.record_date),
                    "status": r.digestion_status,
                    "note": r.digestion_note,
                }
                for r in sorted_health
                if r.digestion_status != "normal"
            ],
        },
        "formula_stage": {
            "stage_match_records": stage_match_records,
            "current_stage": baby.current_stage,
            "recommended_stage": stage_match_records[-1]["recommended_stage"] if stage_match_records else baby.current_stage,
        },
        "nutrient_gap": {
            "trend": nutrient_gap_trend,
            "avg_gap_score": round(
                sum(t["gap_score"] for t in nutrient_gap_trend) / len(nutrient_gap_trend), 2
            ) if nutrient_gap_trend else 0.0,
        },
        "transition_plan": {
            "has_active_plan": active_transition_plan is not None,
            "plan_name": active_transition_plan.plan_name if active_transition_plan else None,
            "original_stage": active_transition_plan.original_stage if active_transition_plan else None,
            "target_stage": active_transition_plan.target_stage if active_transition_plan else None,
            "progress": transition_progress,
            "transition_records_count": len([r for r in transition_records if r.plan_id == (active_transition_plan.id if active_transition_plan else 0)]),
        },
        "batch_stock": {
            "batches": batch_stock_summary,
            "total_batches": len(batch_stock_summary),
            "batch_risk_count": batch_risk_count,
        },
        "brewing_safety": {
            "total_brewing_count": len(brewing_records),
            "abnormal_count": brewing_abnormal_count,
            "abnormal_rate": round(
                (brewing_abnormal_count / len(brewing_records) * 100) if brewing_records else 0.0, 1
            ),
        },
        "abnormal_events": {
            "total_count": total_events,
            "closed_count": closed_events,
            "completion_rate": abnormal_event_completion_rate,
            "type_distribution": _get_event_type_distribution(abnormal_events),
        },
        "doctor_consultations": {
            "total_count": doctor_consultation_count,
            "consultations": [
                {
                    "id": c.id,
                    "type": c.consultation_type,
                    "symptoms": c.symptoms,
                    "suggestion": c.suggestion,
                    "status": c.status,
                    "created_at": c.created_at.isoformat() if hasattr(c.created_at, "isoformat") else str(c.created_at),
                }
                for c in doctor_consultations
            ],
        },
        "overall_score": overall_score,
        "summary": summary,
    }

    return {
        "title": f"{baby.baby_name}的{'周' if report_type == 'weekly' else '月'}喂养报告",
        "summary": summary,
        "report_data": json.dumps(report_data, ensure_ascii=False, default=str),
        "total_milk_ml": round(total_milk_ml, 1),
        "avg_daily_milk_ml": avg_daily_milk_ml,
        "weight_change_kg": weight_change_kg,
        "digestion_abnormal_count": digestion_abnormal_count,
        "brewing_abnormal_count": brewing_abnormal_count,
        "batch_risk_count": batch_risk_count,
        "transition_progress": transition_progress,
        "doctor_consultation_count": doctor_consultation_count,
        "abnormal_event_completion_rate": abnormal_event_completion_rate,
        "overall_score": overall_score,
    }


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
    score = 100.0

    if baby.current_stage in STAGE_INFO:
        stage_info = STAGE_INFO[baby.current_stage]
        expected_daily = (stage_info["daily_intake_min"] + stage_info["daily_intake_max"]) / 2
        actual_daily = total_milk_ml / period_days if period_days > 0 else 0
        intake_ratio = actual_daily / expected_daily if expected_daily > 0 else 0
        if intake_ratio < 0.5:
            score -= 20
        elif intake_ratio < 0.7:
            score -= 10
        elif intake_ratio > 1.3:
            score -= 5

    if weight_change_kg < -0.2:
        score -= 15
    elif weight_change_kg < 0:
        score -= 8
    elif weight_change_kg > 1.0:
        score -= 5

    if digestion_abnormal_count > 5:
        score -= 15
    elif digestion_abnormal_count > 2:
        score -= 8
    elif digestion_abnormal_count > 0:
        score -= 3

    if brewing_abnormal_count > 10:
        score -= 12
    elif brewing_abnormal_count > 5:
        score -= 6
    elif brewing_abnormal_count > 0:
        score -= 2

    if batch_risk_count > 3:
        score -= 10
    elif batch_risk_count > 0:
        score -= 4

    if abnormal_event_completion_rate < 50:
        score -= 10
    elif abnormal_event_completion_rate < 80:
        score -= 5

    if doctor_consultation_count > 3:
        score -= 5

    return round(max(0.0, min(100.0, score)), 1)


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
    period_str = f"{period_start.isoformat()} 至 {period_end.isoformat()}"
    parts = []
    parts.append(f"本报告汇总了{baby_name}在{period_str}期间的喂养数据。")
    parts.append(f"周期总奶量约 {total_milk_ml:.0f}ml，日均奶量 {avg_daily_milk_ml:.0f}ml。")

    if weight_change_kg > 0:
        parts.append(f"体重增长 {weight_change_kg:.3f}kg，生长态势良好。")
    elif weight_change_kg < 0:
        parts.append(f"体重下降 {abs(weight_change_kg):.3f}kg，需引起关注。")
    else:
        parts.append("体重基本保持稳定。")

    if abnormal_event_count == 0:
        parts.append("本期无异常事件，喂养情况平稳。")
    else:
        parts.append(f"本期共记录 {abnormal_event_count} 次异常事件，其中消化类异常 {digestion_abnormal_count} 次。")

    parts.append(f"综合喂养评分为 {overall_score:.1f} 分。")

    return "".join(parts)


def _get_event_type_distribution(events: List) -> List[Dict]:
    type_count = {}
    for e in events:
        t = e.event_type
        if t not in type_count:
            type_count[t] = 0
        type_count[t] += 1
    return [
        {"event_type": t, "count": c, "name": ABNORMAL_EVENT_TYPE_NAMES.get(t, t)}
        for t, c in sorted(type_count.items(), key=lambda x: x[1], reverse=True)
    ]


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
