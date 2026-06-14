import json
from typing import Dict, List, Optional, Tuple
from datetime import date, datetime, timedelta

from constants import STAGE_INFO
from core.algorithms.health_analysis import analyze_nutrient_gap
from core.algorithms.stage_matching import calculate_stage_suitability
from core.algorithms.batch_analysis import analyze_formula_batch
from core.algorithms.brewing_safety import analyze_brewing_record
from core.algorithms.event_risk import ABNORMAL_EVENT_TYPE_NAMES
from core.utils.date_calculator import calculate_month_age


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

    overall_score = calculate_overall_score(
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

    summary = generate_report_summary(
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
            "type_distribution": get_event_type_distribution(abnormal_events),
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


def calculate_overall_score(
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


def generate_report_summary(
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


def get_event_type_distribution(events: List) -> List[Dict]:
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
