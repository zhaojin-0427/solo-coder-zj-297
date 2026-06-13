from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import date, datetime, timedelta
from database import get_db
from models import BabyProfile, HealthRecord, FormulaBatch, BrewingRecord
from schemas import (
    BrewingRecordCreate, BrewingRecordOut,
    BrewingRecordWithAnalysis, ApiResponse, SCOOP_TO_WATER_RATIO,
)
from services import (
    analyze_brewing_record, generate_brewing_daily_report,
    analyze_formula_batch,
)

router = APIRouter(prefix="/api/brewing-records", tags=["冲泡记录与安全追踪"])


def _calculate_formula_used_grams(formula_scoops: float, scoop_weight_grams: float = 4.5) -> float:
    return formula_scoops * scoop_weight_grams


@router.post("", response_model=ApiResponse)
def create_brewing_record(data: BrewingRecordCreate, db: Session = Depends(get_db)):
    baby = db.query(BabyProfile).filter(BabyProfile.id == data.baby_id).first()
    if not baby:
        return ApiResponse(code=404, message="宝宝档案不存在", data=None)

    batch = db.query(FormulaBatch).filter(FormulaBatch.id == data.batch_id).first()
    if not batch:
        return ApiResponse(code=404, message="奶粉批次不存在", data=None)

    if batch.baby_id != data.baby_id:
        return ApiResponse(code=400, message="该批次不属于当前宝宝，无法使用", data=None)

    if not batch.is_active:
        return ApiResponse(code=400, message="该批次已停用，无法使用", data=None)

    today = date.today()
    days_until_expiry = (batch.expiry_date - today).days
    if days_until_expiry <= 0:
        return ApiResponse(
            code=400,
            message=f"该批次已过期 {abs(days_until_expiry)} 天，严禁继续使用",
            data=None
        )

    formula_used_grams = _calculate_formula_used_grams(data.formula_scoops)
    if formula_used_grams > batch.current_remaining_grams:
        return ApiResponse(
            code=400,
            message=f"库存不足，当前剩余 {batch.current_remaining_grams:.1f} 克，本次需要 {formula_used_grams:.1f} 克",
            data=None
        )

    latest_health_record = db.query(HealthRecord).filter(
        HealthRecord.baby_id == data.baby_id
    ).order_by(HealthRecord.record_date.desc()).first()

    batch_analysis = analyze_formula_batch(batch, baby, latest_health_record)
    if batch_analysis.get("is_opening_overdue"):
        return ApiResponse(
            code=400,
            message=f"该批次已开封超过30天安全期，存在变质风险，建议更换新批次",
            data=None
        )

    record = BrewingRecord(
        baby_id=data.baby_id,
        batch_id=data.batch_id,
        brewing_time=data.brewing_time,
        water_temperature=data.water_temperature,
        formula_scoops=data.formula_scoops,
        water_volume_ml=data.water_volume_ml,
        actual_consumed_ml=data.actual_consumed_ml,
        has_remaining=data.has_remaining,
        remaining_handling=data.remaining_handling,
        abnormal_notes=data.abnormal_notes,
    )
    db.add(record)

    batch.current_remaining_grams -= formula_used_grams
    if batch.current_remaining_grams < 0:
        batch.current_remaining_grams = 0

    db.commit()
    db.refresh(record)
    db.refresh(batch)

    analysis = analyze_brewing_record(record, batch, baby, latest_health_record)
    record_dict = BrewingRecordOut.model_validate(record).model_dump()
    record_dict["safety_analysis"] = analysis

    return ApiResponse(
        code=200,
        message="冲泡记录提交成功",
        data={"record": record_dict}
    )


@router.get("", response_model=ApiResponse)
def list_brewing_records(
    baby_id: Optional[int] = Query(None, description="宝宝ID，不传则查询所有"),
    batch_id: Optional[int] = Query(None, description="批次ID，不传则查询所有"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    limit: int = Query(50, ge=1, le=500, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: Session = Depends(get_db),
):
    if baby_id is not None:
        baby = db.query(BabyProfile).filter(BabyProfile.id == baby_id).first()
        if not baby:
            return ApiResponse(code=404, message="宝宝档案不存在", data=None)

    query = db.query(BrewingRecord)
    if baby_id is not None:
        query = query.filter(BrewingRecord.baby_id == baby_id)
    if batch_id is not None:
        query = query.filter(BrewingRecord.batch_id == batch_id)
    if start_date is not None:
        start_datetime = datetime.combine(start_date, datetime.min.time())
        query = query.filter(BrewingRecord.brewing_time >= start_datetime)
    if end_date is not None:
        end_datetime = datetime.combine(end_date, datetime.max.time())
        query = query.filter(BrewingRecord.brewing_time <= end_datetime)

    total = query.count()
    records = query.order_by(BrewingRecord.brewing_time.desc()).offset(offset).limit(limit).all()
    data = [BrewingRecordOut.model_validate(r).model_dump() for r in records]

    return ApiResponse(
        code=200,
        message="查询成功",
        data={"list": data, "total": total, "limit": limit, "offset": offset}
    )


@router.get("/with-analysis", response_model=ApiResponse)
def list_brewing_records_with_analysis(
    baby_id: int = Query(..., description="宝宝ID"),
    start_date: Optional[date] = Query(None, description="开始日期"),
    end_date: Optional[date] = Query(None, description="结束日期"),
    limit: int = Query(50, ge=1, le=500, description="返回数量限制"),
    offset: int = Query(0, ge=0, description="偏移量"),
    db: Session = Depends(get_db),
):
    baby = db.query(BabyProfile).filter(BabyProfile.id == baby_id).first()
    if not baby:
        return ApiResponse(code=404, message="宝宝档案不存在", data=None)

    latest_health_record = db.query(HealthRecord).filter(
        HealthRecord.baby_id == baby_id
    ).order_by(HealthRecord.record_date.desc()).first()

    query = db.query(BrewingRecord).filter(BrewingRecord.baby_id == baby_id)
    if start_date is not None:
        start_datetime = datetime.combine(start_date, datetime.min.time())
        query = query.filter(BrewingRecord.brewing_time >= start_datetime)
    if end_date is not None:
        end_datetime = datetime.combine(end_date, datetime.max.time())
        query = query.filter(BrewingRecord.brewing_time <= end_datetime)

    total = query.count()
    records = query.order_by(BrewingRecord.brewing_time.desc()).offset(offset).limit(limit).all()

    result = []
    for record in records:
        batch = db.query(FormulaBatch).filter(FormulaBatch.id == record.batch_id).first()
        record_dict = BrewingRecordOut.model_validate(record).model_dump()
        if batch:
            analysis = analyze_brewing_record(record, batch, baby, latest_health_record)
            record_dict["safety_analysis"] = analysis
        result.append(record_dict)

    return ApiResponse(
        code=200,
        message="查询成功",
        data={"list": result, "total": total, "limit": limit, "offset": offset}
    )


@router.get("/{record_id}", response_model=ApiResponse)
def get_brewing_record(record_id: int, db: Session = Depends(get_db)):
    record = db.query(BrewingRecord).filter(BrewingRecord.id == record_id).first()
    if not record:
        return ApiResponse(code=404, message="冲泡记录不存在", data=None)
    return ApiResponse(
        code=200,
        message="查询成功",
        data={"record": BrewingRecordOut.model_validate(record).model_dump()}
    )


@router.get("/{record_id}/with-analysis", response_model=ApiResponse)
def get_brewing_record_with_analysis(record_id: int, db: Session = Depends(get_db)):
    record = db.query(BrewingRecord).filter(BrewingRecord.id == record_id).first()
    if not record:
        return ApiResponse(code=404, message="冲泡记录不存在", data=None)

    baby = db.query(BabyProfile).filter(BabyProfile.id == record.baby_id).first()
    batch = db.query(FormulaBatch).filter(FormulaBatch.id == record.batch_id).first()
    if not baby or not batch:
        return ApiResponse(code=404, message="关联数据不存在", data=None)

    latest_health_record = db.query(HealthRecord).filter(
        HealthRecord.baby_id == record.baby_id
    ).order_by(HealthRecord.record_date.desc()).first()

    analysis = analyze_brewing_record(record, batch, baby, latest_health_record)
    record_dict = BrewingRecordOut.model_validate(record).model_dump()
    record_dict["safety_analysis"] = analysis

    return ApiResponse(code=200, message="查询成功", data={"record": record_dict})


@router.get("/daily-report/{baby_id}", response_model=ApiResponse)
def get_brewing_daily_report(
    baby_id: int,
    report_date: date = Query(None, description="查询日期，默认为今天"),
    db: Session = Depends(get_db),
):
    baby = db.query(BabyProfile).filter(BabyProfile.id == baby_id).first()
    if not baby:
        return ApiResponse(code=404, message="宝宝档案不存在", data=None)

    if report_date is None:
        report_date = date.today()

    if report_date > date.today():
        return ApiResponse(code=400, message="不能查询未来日期的报告", data=None)

    latest_health_record = db.query(HealthRecord).filter(
        HealthRecord.baby_id == baby_id
    ).order_by(HealthRecord.record_date.desc()).first()

    start_datetime = datetime.combine(report_date, datetime.min.time())
    end_datetime = datetime.combine(report_date, datetime.max.time())

    records = db.query(BrewingRecord).filter(
        BrewingRecord.baby_id == baby_id,
        BrewingRecord.brewing_time >= start_datetime,
        BrewingRecord.brewing_time <= end_datetime,
    ).order_by(BrewingRecord.brewing_time.asc()).all()

    batch_ids = [r.batch_id for r in records]
    batches = []
    if batch_ids:
        batches = db.query(FormulaBatch).filter(FormulaBatch.id.in_(batch_ids)).all()

    report = generate_brewing_daily_report(
        baby=baby,
        report_date=report_date,
        records=records,
        batches=batches,
        latest_health_record=latest_health_record,
    )

    return ApiResponse(
        code=200,
        message="冲泡安全日报生成成功",
        data={"report": report}
    )


@router.get("/batch-stock-warning/{baby_id}", response_model=ApiResponse)
def get_batch_stock_warning(baby_id: int, db: Session = Depends(get_db)):
    baby = db.query(BabyProfile).filter(BabyProfile.id == baby_id).first()
    if not baby:
        return ApiResponse(code=404, message="宝宝档案不存在", data=None)

    latest_health_record = db.query(HealthRecord).filter(
        HealthRecord.baby_id == baby_id
    ).order_by(HealthRecord.record_date.desc()).first()

    active_batches = db.query(FormulaBatch).filter(
        FormulaBatch.baby_id == baby_id,
        FormulaBatch.is_active == True,
    ).order_by(FormulaBatch.created_at.desc()).all()

    warnings = []
    critical_batches = []
    need_attention_batches = []
    ok_batches = []

    for batch in active_batches:
        analysis = analyze_formula_batch(batch, baby, latest_health_record)
        batch_dict = {
            "batch_id": batch.id,
            "brand_name": batch.brand_name,
            "product_name": batch.product_name,
            "stage": batch.stage,
            "batch_number": batch.batch_number,
            "remaining_grams": batch.current_remaining_grams,
            "stock_available_days": analysis.get("stock_available_days", 0),
            "risk_level": analysis.get("risk_level", "low"),
            "days_until_expiry": analysis.get("days_until_expiry", 0),
            "days_since_opening": analysis.get("days_since_opening", 0),
        }

        if analysis.get("risk_level") in ["critical", "high"]:
            critical_batches.append(batch_dict)
            warnings.extend(analysis.get("risks", []))
        elif analysis.get("risk_level") == "medium":
            need_attention_batches.append(batch_dict)
            warnings.extend(analysis.get("warnings", []))
        else:
            ok_batches.append(batch_dict)

    overall_status = "ok"
    overall_message = "所有批次状态良好"
    if critical_batches:
        overall_status = "critical"
        overall_message = "存在高风险批次，请立即处理"
    elif need_attention_batches:
        overall_status = "warning"
        overall_message = "存在需要关注的批次"

    total_remaining_grams = sum(b.current_remaining_grams for b in active_batches)
    total_stock_days = 0
    if latest_health_record and total_remaining_grams > 0:
        from services import calculate_stock_days
        total_stock_days = calculate_stock_days(
            total_remaining_grams, latest_health_record.daily_intake_ml
        )

    return ApiResponse(
        code=200,
        message="库存预警查询成功",
        data={
            "baby_id": baby_id,
            "baby_name": baby.baby_name,
            "overall_status": overall_status,
            "overall_message": overall_message,
            "total_active_batches": len(active_batches),
            "total_remaining_grams": round(total_remaining_grams, 1),
            "total_stock_available_days": total_stock_days,
            "critical_batches": critical_batches,
            "need_attention_batches": need_attention_batches,
            "ok_batches": ok_batches,
            "warnings": warnings,
        }
    )
