from typing import Dict, List, Optional, Tuple
from datetime import date, datetime, timedelta
from collections import Counter, defaultdict

from constants import STAGE_INFO, DIGESTION_STATUS
from schemas import SCOOP_TO_WATER_RATIO
from core.algorithms.health_analysis import (
    analyze_digestion, analyze_weight_growth, analyze_nutrient_gap,
)
from core.algorithms.batch_analysis import analyze_formula_batch
from core.algorithms.brewing_safety import analyze_brewing_record
from core.utils.date_calculator import calculate_month_age


SEVERITY_LEVEL_MAP = {
    "vomiting": "呕吐", "diarrhea": "腹泻", "constipation": "便秘",
    "allergy": "过敏反应", "fever": "体温", "low_appetite": "食欲",
    "bloating": "腹胀", "skin_rash": "皮疹", "other": "症状",
}

ABNORMAL_EVENT_TYPE_NAMES = {
    "vomiting": "呕吐", "diarrhea": "腹泻", "constipation": "便秘",
    "allergy": "过敏", "fever": "发热", "low_appetite": "食欲差",
    "bloating": "腹胀", "skin_rash": "皮疹", "other": "其他",
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
        batch_for_analysis = batch
        if not batch_for_analysis and db_batches and brewing_record.batch_id in db_batches:
            batch_for_analysis = db_batches[brewing_record.batch_id]
        brewing_analysis = analyze_brewing_record(
            brewing_record, batch_for_analysis, baby, latest_health_record,
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


def generate_abnormal_event_replay(
    baby,
    start_date: date,
    end_date: date,
    events: List,
    batches_map: Dict = None,
    active_transition_plans: List = None,
) -> Dict:
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
