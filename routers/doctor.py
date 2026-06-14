from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from models import BabyProfile, DoctorConsultation, HealthRecord
from schemas import ApiResponse, DoctorConsultationCreate, DoctorConsultationOut
from core.algorithms import analyze_digestion, analyze_weight_growth, analyze_nutrient_gap, calculate_stage_suitability
from core.validators.enums import validate_consultation_type
from core.utils import success_response, not_found_response, bad_request_response
from datetime import datetime

router = APIRouter(prefix="/api/doctor", tags=["医生咨询"])


CONSULTATION_TEMPLATES = {
    "digestion": {
        "description": "消化问题咨询",
        "base_suggestion": "建议观察宝宝排便情况，记录奶量和辅食种类，必要时进行粪便检查。",
    },
    "growth": {
        "description": "生长发育咨询",
        "base_suggestion": "建议定期测量体重身高，绘制生长曲线，评估喂养方式是否合理。",
    },
    "nutrition": {
        "description": "营养咨询",
        "base_suggestion": "建议评估膳食结构，必要时进行微量元素检测，科学补充营养。",
    },
    "transition": {
        "description": "转段咨询",
        "base_suggestion": "建议采用渐进式转奶法，密切观察宝宝消化情况和生长指标。",
    },
    "other": {
        "description": "其他咨询",
        "base_suggestion": "建议详细记录症状，携带相关检查结果就诊。",
    },
}


@router.post("/consultation", response_model=ApiResponse)
def create_consultation(data: DoctorConsultationCreate, db: Session = Depends(get_db)):
    baby = db.query(BabyProfile).filter(BabyProfile.id == data.baby_id).first()
    if not baby:
        return ApiResponse(code=404, message="宝宝档案不存在", data=None)

    template = CONSULTATION_TEMPLATES.get(data.consultation_type, CONSULTATION_TEMPLATES["other"])

    recent_records = db.query(HealthRecord).filter(
        HealthRecord.baby_id == data.baby_id
    ).order_by(HealthRecord.record_date.desc()).limit(3).all()

    extra_suggestions = []
    if recent_records:
        latest = recent_records[0]
        digestion_info = analyze_digestion(latest.digestion_status, latest.digestion_note)
        if digestion_info["alert"]:
            extra_suggestions.append(f"近期消化异常（{digestion_info['status_name']}），建议重点检查肠胃功能")

        weight_info = analyze_weight_growth(latest.month_age, latest.weight_kg, baby.gender)
        if weight_info["need_attention"]:
            extra_suggestions.append(f"生长指标异常（{weight_info['weight_status']}），建议评估营养摄入")

        stage_info = calculate_stage_suitability(latest.month_age, latest.current_stage)
        if stage_info["suitability"] != "perfect":
            extra_suggestions.append(stage_info["suggestion"])

    full_suggestion = template["base_suggestion"]
    if extra_suggestions:
        full_suggestion += " 此外，" + "；".join(extra_suggestions)

    consultation = DoctorConsultation(
        baby_id=data.baby_id,
        consultation_type=data.consultation_type,
        symptoms=data.symptoms,
        suggestion=full_suggestion,
        status="pending",
        scheduled_time=data.scheduled_time,
    )
    db.add(consultation)
    db.commit()
    db.refresh(consultation)

    return ApiResponse(code=200, message="咨询请求提交成功", data={
        "consultation": DoctorConsultationOut.model_validate(consultation).model_dump(),
        "auto_suggestion": full_suggestion,
        "description": template["description"],
    })


@router.get("/consultation/{consultation_id}", response_model=ApiResponse)
def get_consultation(consultation_id: int, db: Session = Depends(get_db)):
    c = db.query(DoctorConsultation).filter(DoctorConsultation.id == consultation_id).first()
    if not c:
        return ApiResponse(code=404, message="咨询记录不存在", data=None)
    return ApiResponse(code=200, message="查询成功", data={
        "consultation": DoctorConsultationOut.model_validate(c).model_dump()
    })


@router.get("/consultations", response_model=ApiResponse)
def list_consultations(baby_id: int = None, db: Session = Depends(get_db)):
    query = db.query(DoctorConsultation)
    if baby_id:
        baby = db.query(BabyProfile).filter(BabyProfile.id == baby_id).first()
        if not baby:
            return ApiResponse(code=404, message="宝宝档案不存在", data=None)
        query = query.filter(DoctorConsultation.baby_id == baby_id)
    consultations = query.order_by(DoctorConsultation.created_at.desc()).all()
    data = [DoctorConsultationOut.model_validate(c).model_dump() for c in consultations]
    return ApiResponse(code=200, message="查询成功", data={"list": data, "total": len(data)})


@router.put("/consultation/{consultation_id}/reply", response_model=ApiResponse)
def reply_consultation(consultation_id: int, suggestion: str, db: Session = Depends(get_db)):
    c = db.query(DoctorConsultation).filter(DoctorConsultation.id == consultation_id).first()
    if not c:
        return ApiResponse(code=404, message="咨询记录不存在", data=None)
    c.suggestion = suggestion
    c.status = "replied"
    db.commit()
    db.refresh(c)
    return ApiResponse(code=200, message="回复成功", data={
        "consultation": DoctorConsultationOut.model_validate(c).model_dump()
    })


@router.get("/types", response_model=ApiResponse)
def get_consultation_types():
    types = []
    for key, val in CONSULTATION_TEMPLATES.items():
        types.append({"type": key, "description": val["description"]})
    return ApiResponse(code=200, message="查询成功", data={"types": types})
