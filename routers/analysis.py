from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import BabyProfile, HealthRecord
from schemas import ApiResponse, StageMatchRequest, NutritionAdviceRequest, TransitionWarningRequest
from core.algorithms import (
    match_stage_by_month, calculate_stage_suitability, analyze_weight_growth,
    analyze_nutrient_gap, analyze_digestion, calculate_transition_success_rate,
    comprehensive_analysis,
)
from core.utils import success_response, not_found_response, bad_request_response
from core.validators.stage import validate_stage, validate_month_age
from constants import STAGE_INFO

router = APIRouter(prefix="/api/analysis", tags=["分析服务"])


@router.get("/stages", response_model=ApiResponse)
def get_all_stage_info():
    stages = []
    for num in sorted(STAGE_INFO.keys()):
        info = STAGE_INFO[num]
        stages.append({
            "stage": num,
            "name": info["name"],
            "recommended_month_range": [info["min_month"], info["max_month"]],
            "description": info["description"],
            "recommended_daily_intake_ml": [info["daily_intake_min"], info["daily_intake_max"]],
            "nutrients_per_100ml": info["nutrients"],
        })
    return ApiResponse(code=200, message="查询成功", data={"stages": stages})


@router.post("/stage-match", response_model=ApiResponse)
def stage_match(data: StageMatchRequest, db: Session = Depends(get_db)):
    baby = db.query(BabyProfile).filter(BabyProfile.id == data.baby_id).first()
    if not baby:
        return ApiResponse(code=404, message="宝宝档案不存在", data=None)

    recommended = match_stage_by_month(data.month_age)

    current_stage = data.current_stage or baby.current_stage
    suitability = calculate_stage_suitability(data.month_age, current_stage)

    return ApiResponse(code=200, message="分析完成", data={
        "baby_id": data.baby_id,
        "baby_name": baby.baby_name,
        "month_age": data.month_age,
        "recommended": recommended,
        "suitability": suitability,
    })


@router.post("/nutrition", response_model=ApiResponse)
def nutrition_advice(data: NutritionAdviceRequest, db: Session = Depends(get_db)):
    baby = db.query(BabyProfile).filter(BabyProfile.id == data.baby_id).first()
    if not baby:
        return ApiResponse(code=404, message="宝宝档案不存在", data=None)

    nutrient_result = analyze_nutrient_gap(
        data.month_age, data.current_stage, data.daily_intake_ml, data.weight_kg
    )
    weight_result = analyze_weight_growth(data.month_age, data.weight_kg, baby.gender)

    suggestions = []
    if nutrient_result["intake_status"] == "奶量不足":
        suggestions.append(f"建议增加每日奶量至 {nutrient_result['recommended_intake_range'][0]}ml 以上")
    elif nutrient_result["intake_status"] == "奶量偏高":
        suggestions.append(f"建议适当减少奶量，控制在 {nutrient_result['recommended_intake_range'][1]}ml 以内")

    for nutrient, gap in nutrient_result["nutrient_gaps"].items():
        if gap["status"] == "不足" and gap["gap_amount"] > 0:
            name_map = {"protein": "蛋白质", "fat": "脂肪", "carb": "碳水化合物", "calcium": "钙", "iron": "铁", "dha": "DHA"}
            suggestions.append(f"{name_map.get(nutrient, nutrient)}摄入不足，每日缺口约 {gap['gap_amount']} 单位，建议通过辅食或补充剂补充")

    if weight_result["weight_level"] == "underweight":
        suggestions.append("体重偏轻，建议增加营养摄入并咨询医生")
    elif weight_result["weight_level"] == "overweight":
        suggestions.append("体重偏重，建议控制奶量并增加活动")

    return ApiResponse(code=200, message="分析完成", data={
        "baby_id": data.baby_id,
        "baby_name": baby.baby_name,
        "nutrition_analysis": nutrient_result,
        "weight_analysis": weight_result,
        "suggestions": suggestions,
    })


@router.post("/transition-warning", response_model=ApiResponse)
def transition_warning(data: TransitionWarningRequest, db: Session = Depends(get_db)):
    baby = db.query(BabyProfile).filter(BabyProfile.id == data.baby_id).first()
    if not baby:
        return ApiResponse(code=404, message="宝宝档案不存在", data=None)

    weight_history = None
    if data.weight_history:
        weight_history = [item.model_dump() for item in data.weight_history]
    else:
        records = db.query(HealthRecord).filter(
            HealthRecord.baby_id == data.baby_id
        ).order_by(HealthRecord.month_age).all()
        weight_history = [{"month_age": r.month_age, "weight_kg": r.weight_kg} for r in records]

    result = comprehensive_analysis(
        month_age=data.month_age,
        current_stage=data.current_stage,
        daily_intake_ml=data.daily_intake_ml,
        digestion_status=data.digestion_status,
        weight_kg=data.weight_kg,
        gender=baby.gender,
        weight_history=weight_history,
    )

    alerts = []
    if result["digestion_analysis"]["alert"]:
        alerts.append({
            "type": "digestion",
            "level": result["digestion_analysis"]["level"],
            "status": result["digestion_analysis"]["status_name"],
            "message": result["digestion_analysis"]["description"],
        })

    if result["weight_analysis"]["need_attention"]:
        alerts.append({
            "type": "growth",
            "level": "warning",
            "status": result["weight_analysis"]["weight_status"],
            "message": f"体重偏离参考范围 {result['weight_analysis']['deviation_percent']}%",
            "deviation_percent": result["weight_analysis"]["deviation_percent"],
        })

    if result["weight_analysis"].get("growth_abnormal"):
        alerts.append({
            "type": "growth_rate",
            "level": "warning",
            "status": result["weight_analysis"]["growth_rate_status"],
            "message": f"月均增重 {result['weight_analysis']['avg_monthly_gain_kg']}kg，{result['weight_analysis']['growth_rate_status']}",
        })

    if result["stage_suitability"]["suitability"] != "perfect":
        transition = result["transition_analysis"]
        transition_data = {
            "current_stage": result["stage_suitability"]["current_stage_name"],
            "recommended_stage": result["stage_suitability"]["recommended_stage_name"],
            "success_rate": transition["success_rate"],
            "readiness": transition["readiness"],
            "message": transition["message"],
            "risk_factors": transition["risk_factors"],
            "suggestions": transition["suggestions"],
            "transition_method": transition.get("transition_method"),
        }
    else:
        transition_data = {
            "status": "no_need",
            "message": "当前段位匹配良好，无需转段",
        }

    return ApiResponse(code=200, message="分析完成", data={
        "baby_id": data.baby_id,
        "baby_name": baby.baby_name,
        "month_age": data.month_age,
        "stage_suitability": result["stage_suitability"],
        "weight_analysis": result["weight_analysis"],
        "digestion_analysis": result["digestion_analysis"],
        "nutrition_gap": result["nutrient_analysis"],
        "transition_analysis": transition_data,
        "alerts": alerts,
        "warnings": result["warnings"],
        "need_doctor_consultation": result["need_doctor_consultation"],
        "overall_suggestion": result["overall_suggestion"],
    })
