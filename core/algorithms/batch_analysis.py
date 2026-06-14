from typing import Dict, Optional
from datetime import date
from constants import STAGE_INFO
from schemas import (
    STORAGE_METHOD_NAMES, OPENING_SAFE_DAYS,
)
from core.algorithms.stage_matching import calculate_stage_suitability
from core.algorithms.health_analysis import analyze_nutrient_gap, analyze_digestion
from core.utils import calculate_month_age, calculate_stock_days, to_date


def analyze_formula_batch(
    batch,
    baby,
    latest_health_record=None,
) -> Dict:
    today = date.today()
    risks = []
    warnings = []
    suggestions = []

    birth_date = to_date(baby.birth_date)
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
