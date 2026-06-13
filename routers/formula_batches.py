from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date
from database import get_db
from models import BabyProfile, HealthRecord, FormulaBatch
from schemas import (
    FormulaBatchCreate, FormulaBatchUpdateRemaining, FormulaBatchOut,
    FormulaBatchWithAnalysis, ApiResponse,
)
from services import analyze_formula_batch

router = APIRouter(prefix="/api/formula-batches", tags=["奶粉批次管理"])


@router.post("", response_model=ApiResponse)
def create_formula_batch(data: FormulaBatchCreate, db: Session = Depends(get_db)):
    baby = db.query(BabyProfile).filter(BabyProfile.id == data.baby_id).first()
    if not baby:
        return ApiResponse(code=404, message="宝宝档案不存在", data=None)

    existing = db.query(FormulaBatch).filter(
        FormulaBatch.baby_id == data.baby_id,
        FormulaBatch.batch_number == data.batch_number,
        FormulaBatch.brand_name == data.brand_name,
        FormulaBatch.product_name == data.product_name,
    ).first()
    if existing:
        return ApiResponse(code=400, message="该批次已存在", data=None)

    batch = FormulaBatch(
        baby_id=data.baby_id,
        brand_name=data.brand_name,
        product_name=data.product_name,
        stage=data.stage,
        batch_number=data.batch_number,
        opening_date=data.opening_date,
        expiry_date=data.expiry_date,
        can_capacity_grams=data.can_capacity_grams,
        current_remaining_grams=data.current_remaining_grams,
        storage_method=data.storage_method,
        notes=data.notes,
        is_active=True,
    )
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return ApiResponse(
        code=200,
        message="奶粉批次创建成功",
        data={"batch": FormulaBatchOut.model_validate(batch).model_dump()}
    )


@router.get("", response_model=ApiResponse)
def list_formula_batches(
    baby_id: Optional[int] = Query(None, description="宝宝ID，不传则查询所有"),
    include_inactive: bool = Query(False, description="是否包含已停用批次"),
    db: Session = Depends(get_db),
):
    query = db.query(FormulaBatch)
    if baby_id is not None:
        baby = db.query(BabyProfile).filter(BabyProfile.id == baby_id).first()
        if not baby:
            return ApiResponse(code=404, message="宝宝档案不存在", data=None)
        query = query.filter(FormulaBatch.baby_id == baby_id)
    if not include_inactive:
        query = query.filter(FormulaBatch.is_active == True)

    batches = query.order_by(FormulaBatch.created_at.desc()).all()
    data = [FormulaBatchOut.model_validate(b).model_dump() for b in batches]
    return ApiResponse(code=200, message="查询成功", data={"list": data, "total": len(data)})


@router.get("/with-analysis", response_model=ApiResponse)
def list_formula_batches_with_analysis(
    baby_id: int = Query(..., description="宝宝ID"),
    db: Session = Depends(get_db),
):
    baby = db.query(BabyProfile).filter(BabyProfile.id == baby_id).first()
    if not baby:
        return ApiResponse(code=404, message="宝宝档案不存在", data=None)

    latest_health_record = db.query(HealthRecord).filter(
        HealthRecord.baby_id == baby_id
    ).order_by(HealthRecord.record_date.desc()).first()

    batches = db.query(FormulaBatch).filter(
        FormulaBatch.baby_id == baby_id
    ).order_by(FormulaBatch.created_at.desc()).all()

    result = []
    for batch in batches:
        batch_dict = FormulaBatchOut.model_validate(batch).model_dump()
        analysis = analyze_formula_batch(batch, baby, latest_health_record)
        batch_dict["risk_analysis"] = analysis
        result.append(batch_dict)

    return ApiResponse(code=200, message="查询成功", data={"list": result, "total": len(result)})


@router.get("/{batch_id}", response_model=ApiResponse)
def get_formula_batch(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(FormulaBatch).filter(FormulaBatch.id == batch_id).first()
    if not batch:
        return ApiResponse(code=404, message="奶粉批次不存在", data=None)
    return ApiResponse(
        code=200,
        message="查询成功",
        data={"batch": FormulaBatchOut.model_validate(batch).model_dump()}
    )


@router.get("/{batch_id}/with-analysis", response_model=ApiResponse)
def get_formula_batch_with_analysis(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(FormulaBatch).filter(FormulaBatch.id == batch_id).first()
    if not batch:
        return ApiResponse(code=404, message="奶粉批次不存在", data=None)

    baby = db.query(BabyProfile).filter(BabyProfile.id == batch.baby_id).first()
    if not baby:
        return ApiResponse(code=404, message="宝宝档案不存在", data=None)

    latest_health_record = db.query(HealthRecord).filter(
        HealthRecord.baby_id == batch.baby_id
    ).order_by(HealthRecord.record_date.desc()).first()

    analysis = analyze_formula_batch(batch, baby, latest_health_record)
    batch_dict = FormulaBatchOut.model_validate(batch).model_dump()
    batch_dict["risk_analysis"] = analysis

    return ApiResponse(code=200, message="查询成功", data={"batch": batch_dict})


@router.patch("/{batch_id}/remaining", response_model=ApiResponse)
def update_batch_remaining(
    batch_id: int,
    data: FormulaBatchUpdateRemaining,
    db: Session = Depends(get_db),
):
    batch = db.query(FormulaBatch).filter(FormulaBatch.id == batch_id).first()
    if not batch:
        return ApiResponse(code=404, message="奶粉批次不存在", data=None)

    if not batch.is_active:
        return ApiResponse(code=400, message="该批次已停用，无法更新", data=None)

    if data.current_remaining_grams > batch.can_capacity_grams:
        return ApiResponse(code=400, message="剩余量不能超过每罐容量", data=None)

    batch.current_remaining_grams = data.current_remaining_grams
    db.commit()
    db.refresh(batch)
    return ApiResponse(
        code=200,
        message="剩余量更新成功",
        data={"batch": FormulaBatchOut.model_validate(batch).model_dump()}
    )


@router.patch("/{batch_id}/deactivate", response_model=ApiResponse)
def deactivate_batch(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(FormulaBatch).filter(FormulaBatch.id == batch_id).first()
    if not batch:
        return ApiResponse(code=404, message="奶粉批次不存在", data=None)

    if not batch.is_active:
        return ApiResponse(code=400, message="该批次已停用", data=None)

    batch.is_active = False
    db.commit()
    db.refresh(batch)
    return ApiResponse(
        code=200,
        message="批次已停用",
        data={"batch": FormulaBatchOut.model_validate(batch).model_dump()}
    )


@router.patch("/{batch_id}/activate", response_model=ApiResponse)
def activate_batch(batch_id: int, db: Session = Depends(get_db)):
    batch = db.query(FormulaBatch).filter(FormulaBatch.id == batch_id).first()
    if not batch:
        return ApiResponse(code=404, message="奶粉批次不存在", data=None)

    if batch.is_active:
        return ApiResponse(code=400, message="该批次已在启用状态", data=None)

    batch.is_active = True
    db.commit()
    db.refresh(batch)
    return ApiResponse(
        code=200,
        message="批次已启用",
        data={"batch": FormulaBatchOut.model_validate(batch).model_dump()}
    )
