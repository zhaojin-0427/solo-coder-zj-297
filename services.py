from typing import Dict, List, Optional, Tuple
from constants import STAGE_INFO, TRANSITION_SUCCESS_BASE, DIGESTION_STATUS, get_weight_range, get_nutrient_requirement


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
