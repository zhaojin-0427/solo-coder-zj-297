from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from database import get_db
from models import BabyProfile, HealthRecord
from schemas import (
    BabyProfileCreate, BabyProfileUpdate, BabyProfileOut,
    HealthRecordCreate, HealthRecordOut, ApiResponse,
)

router = APIRouter(prefix="/api/baby", tags=["宝宝档案管理"])


@router.post("", response_model=ApiResponse)
def create_baby_profile(data: BabyProfileCreate, db: Session = Depends(get_db)):
    baby = BabyProfile(
        baby_name=data.baby_name,
        gender=data.gender,
        birth_date=datetime.combine(data.birth_date, datetime.min.time()),
        current_stage=data.current_stage,
        guardian_name=data.guardian_name,
        guardian_phone=data.guardian_phone,
    )
    db.add(baby)
    db.commit()
    db.refresh(baby)
    return ApiResponse(code=200, message="宝宝档案创建成功", data={"baby": BabyProfileOut.model_validate(baby).model_dump()})


@router.get("", response_model=ApiResponse)
def list_baby_profiles(db: Session = Depends(get_db)):
    babies = db.query(BabyProfile).order_by(BabyProfile.created_at.desc()).all()
    data = [BabyProfileOut.model_validate(b).model_dump() for b in babies]
    return ApiResponse(code=200, message="查询成功", data={"list": data, "total": len(data)})


@router.get("/{baby_id}", response_model=ApiResponse)
def get_baby_profile(baby_id: int, db: Session = Depends(get_db)):
    baby = db.query(BabyProfile).filter(BabyProfile.id == baby_id).first()
    if not baby:
        return ApiResponse(code=404, message="宝宝档案不存在", data=None)
    return ApiResponse(code=200, message="查询成功", data={"baby": BabyProfileOut.model_validate(baby).model_dump()})


@router.put("/{baby_id}", response_model=ApiResponse)
def update_baby_profile(baby_id: int, data: BabyProfileUpdate, db: Session = Depends(get_db)):
    baby = db.query(BabyProfile).filter(BabyProfile.id == baby_id).first()
    if not baby:
        return ApiResponse(code=404, message="宝宝档案不存在", data=None)
    update_data = data.model_dump(exclude_unset=True)
    if "birth_date" in update_data and update_data["birth_date"]:
        update_data["birth_date"] = datetime.combine(update_data["birth_date"], datetime.min.time())
    for key, value in update_data.items():
        if value is not None:
            setattr(baby, key, value)
    baby.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(baby)
    return ApiResponse(code=200, message="更新成功", data={"baby": BabyProfileOut.model_validate(baby).model_dump()})


@router.delete("/{baby_id}", response_model=ApiResponse)
def delete_baby_profile(baby_id: int, db: Session = Depends(get_db)):
    baby = db.query(BabyProfile).filter(BabyProfile.id == baby_id).first()
    if not baby:
        return ApiResponse(code=404, message="宝宝档案不存在", data=None)
    db.delete(baby)
    db.commit()
    return ApiResponse(code=200, message="删除成功", data=None)


@router.post("/record", response_model=ApiResponse)
def create_health_record(data: HealthRecordCreate, db: Session = Depends(get_db)):
    baby = db.query(BabyProfile).filter(BabyProfile.id == data.baby_id).first()
    if not baby:
        return ApiResponse(code=404, message="宝宝档案不存在", data=None)
    record = HealthRecord(
        baby_id=data.baby_id,
        month_age=data.month_age,
        current_stage=data.current_stage,
        daily_intake_ml=data.daily_intake_ml,
        digestion_status=data.digestion_status,
        digestion_note=data.digestion_note,
        weight_kg=data.weight_kg,
        height_cm=data.height_cm,
        record_date=data.record_date or datetime.utcnow(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return ApiResponse(code=200, message="健康记录上报成功", data={"record": HealthRecordOut.model_validate(record).model_dump()})


@router.get("/{baby_id}/records", response_model=ApiResponse)
def list_health_records(baby_id: int, db: Session = Depends(get_db)):
    baby = db.query(BabyProfile).filter(BabyProfile.id == baby_id).first()
    if not baby:
        return ApiResponse(code=404, message="宝宝档案不存在", data=None)
    records = db.query(HealthRecord).filter(HealthRecord.baby_id == baby_id).order_by(HealthRecord.record_date.desc()).all()
    data = [HealthRecordOut.model_validate(r).model_dump() for r in records]
    return ApiResponse(code=200, message="查询成功", data={"list": data, "total": len(data)})
