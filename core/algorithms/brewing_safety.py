from typing import Dict, List, Optional
from datetime import date
from constants import STAGE_INFO
from schemas import (
    MIN_WATER_TEMPERATURE, MAX_WATER_TEMPERATURE, SCOOP_TO_WATER_RATIO,
    REMAINING_HANDLING_NAMES,
)
from core.algorithms.batch_analysis import analyze_formula_batch
from core.utils import calculate_month_age, to_date


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

    birth_date = to_date(baby.birth_date)
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
