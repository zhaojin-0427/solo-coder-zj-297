from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import datetime, date
import json
from database import get_db
from models import BabyProfile, TransitionPlan, TransitionRecord
from schemas import (
    ApiResponse,
    TransitionPlanCreate,
    TransitionPlanStatusUpdate,
    TransitionPlanOut,
    TransitionRecordCreate,
    TransitionRecordOut,
)
from services import generate_phase_review, generate_plan_review

router = APIRouter(prefix="/api/transition-plans", tags=["转段跟踪计划与复盘"])


@router.post("", response_model=ApiResponse)
def create_transition_plan(data: TransitionPlanCreate, db: Session = Depends(get_db)):
    baby = db.query(BabyProfile).filter(BabyProfile.id == data.baby_id).first()
    if not baby:
        return ApiResponse(code=404, message="宝宝档案不存在", data=None)

    if data.original_stage != baby.current_stage:
        return ApiResponse(code=400, message=f"原段位({data.original_stage})与宝宝当前段位({baby.current_stage})不一致", data=None)

    schedule_json = json.dumps([item.model_dump() for item in data.daily_ratio_schedule], ensure_ascii=False)

    plan = TransitionPlan(
        baby_id=data.baby_id,
        plan_name=data.plan_name.strip(),
        original_stage=data.original_stage,
        target_stage=data.target_stage,
        start_date=datetime.combine(data.start_date, datetime.min.time()),
        transition_days=data.transition_days,
        daily_ratio_schedule=schedule_json,
        observation_focus=data.observation_focus,
        status=data.status,
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)

    plan_out = TransitionPlanOut.model_validate(plan).model_dump()
    return ApiResponse(code=200, message="转段计划创建成功", data={"plan": plan_out})


@router.get("", response_model=ApiResponse)
def list_transition_plans(
    baby_id: Optional[int] = Query(None, description="按宝宝ID过滤"),
    status: Optional[str] = Query(None, description="按计划状态过滤"),
    db: Session = Depends(get_db),
):
    query = db.query(TransitionPlan)
    if baby_id is not None:
        baby = db.query(BabyProfile).filter(BabyProfile.id == baby_id).first()
        if not baby:
            return ApiResponse(code=404, message="宝宝档案不存在", data=None)
        query = query.filter(TransitionPlan.baby_id == baby_id)
    if status:
        from models import VALID_TRANSITION_PLAN_STATUSES
        if status not in VALID_TRANSITION_PLAN_STATUSES:
            return ApiResponse(
                code=400,
                message=f"无效的计划状态: {status}，有效值为: {', '.join(sorted(VALID_TRANSITION_PLAN_STATUSES))}",
                data=None,
            )
        query = query.filter(TransitionPlan.status == status)

    plans = query.order_by(TransitionPlan.created_at.desc()).all()
    plan_list = []
    for p in plans:
        plan_out = TransitionPlanOut.model_validate(p).model_dump()
        baby = db.query(BabyProfile).filter(BabyProfile.id == p.baby_id).first()
        plan_out["baby_name"] = baby.baby_name if baby else None
        plan_list.append(plan_out)

    return ApiResponse(code=200, message="查询成功", data={"list": plan_list, "total": len(plan_list)})


@router.get("/{plan_id}", response_model=ApiResponse)
def get_transition_plan(plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(TransitionPlan).filter(TransitionPlan.id == plan_id).first()
    if not plan:
        return ApiResponse(code=404, message="转段计划不存在", data=None)

    baby = db.query(BabyProfile).filter(BabyProfile.id == plan.baby_id).first()
    records = db.query(TransitionRecord).filter(
        TransitionRecord.plan_id == plan_id
    ).order_by(TransitionRecord.record_date.asc()).all()

    plan_out = TransitionPlanOut.model_validate(plan).model_dump()
    plan_out["baby_name"] = baby.baby_name if baby else None
    plan_out["records_count"] = len(records)

    phase_review = None
    if baby:
        phase_review = generate_phase_review(plan, baby, records)

    records_out = [TransitionRecordOut.model_validate(r).model_dump() for r in records]

    return ApiResponse(code=200, message="查询成功", data={
        "plan": plan_out,
        "records": records_out,
        "phase_review": phase_review,
    })


@router.patch("/{plan_id}/status", response_model=ApiResponse)
def update_plan_status(plan_id: int, data: TransitionPlanStatusUpdate, db: Session = Depends(get_db)):
    plan = db.query(TransitionPlan).filter(TransitionPlan.id == plan_id).first()
    if not plan:
        return ApiResponse(code=404, message="转段计划不存在", data=None)

    plan.status = data.status
    plan.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(plan)

    plan_out = TransitionPlanOut.model_validate(plan).model_dump()
    return ApiResponse(code=200, message="计划状态更新成功", data={"plan": plan_out})


@router.post("/records", response_model=ApiResponse)
def create_transition_record(data: TransitionRecordCreate, db: Session = Depends(get_db)):
    plan = db.query(TransitionPlan).filter(TransitionPlan.id == data.plan_id).first()
    if not plan:
        return ApiResponse(code=404, message="转段计划不存在", data=None)

    if plan.status in ("paused", "completed", "cancelled"):
        status_map = {"paused": "已暂停", "completed": "已完成", "cancelled": "已取消"}
        return ApiResponse(code=400, message=f"转段计划{status_map[plan.status]}，无法提交新的跟踪记录", data=None)

    plan_start = plan.start_date.date() if hasattr(plan.start_date, "date") else plan.start_date
    from datetime import timedelta
    plan_end = plan_start + timedelta(days=plan.transition_days - 1)
    if data.record_date < plan_start:
        return ApiResponse(code=400, message=f"记录日期不能早于计划开始日期({plan_start.isoformat()})", data=None)
    if data.record_date > plan_end:
        return ApiResponse(code=400, message=f"记录日期不能晚于计划结束日期({plan_end.isoformat()})", data=None)

    schedule = json.loads(plan.daily_ratio_schedule) if plan.daily_ratio_schedule else []
    day_index = (data.record_date - plan_start).days
    if not schedule or day_index < 0 or day_index >= len(schedule):
        return ApiResponse(
            code=400,
            message=f"第{day_index + 1}天不在计划安排范围内，无法校验新旧奶粉比例",
            data=None,
        )
    expected_old = schedule[day_index]["old_ratio"]
    expected_new = schedule[day_index]["new_ratio"]
    if data.old_formula_ratio != expected_old or data.new_formula_ratio != expected_new:
        return ApiResponse(
            code=400,
            message=f"第{day_index + 1}天新旧奶粉比例应为 旧:{expected_old}% 新:{expected_new}%，当前提交为 旧:{data.old_formula_ratio}% 新:{data.new_formula_ratio}%",
            data=None,
        )

    start_of_day = datetime.combine(data.record_date, datetime.min.time())
    end_of_day = datetime.combine(data.record_date, datetime.max.time())
    existing = db.query(TransitionRecord).filter(
        TransitionRecord.plan_id == data.plan_id,
        TransitionRecord.record_date >= start_of_day,
        TransitionRecord.record_date <= end_of_day,
    ).first()
    if existing:
        return ApiResponse(code=400, message="该日期已存在跟踪记录，请更新而非重复创建", data=None)

    record = TransitionRecord(
        plan_id=data.plan_id,
        record_date=datetime.combine(data.record_date, datetime.min.time()),
        old_formula_ratio=data.old_formula_ratio,
        new_formula_ratio=data.new_formula_ratio,
        milk_intake_ml=data.milk_intake_ml,
        digestion_status=data.digestion_status,
        weight_kg=data.weight_kg,
        note=data.note,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    record_out = TransitionRecordOut.model_validate(record).model_dump()
    return ApiResponse(code=200, message="跟踪记录提交成功", data={"record": record_out})


@router.get("/{plan_id}/records", response_model=ApiResponse)
def list_plan_records(plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(TransitionPlan).filter(TransitionPlan.id == plan_id).first()
    if not plan:
        return ApiResponse(code=404, message="转段计划不存在", data=None)

    records = db.query(TransitionRecord).filter(
        TransitionRecord.plan_id == plan_id
    ).order_by(TransitionRecord.record_date.asc()).all()

    records_out = [TransitionRecordOut.model_validate(r).model_dump() for r in records]
    return ApiResponse(code=200, message="查询成功", data={"list": records_out, "total": len(records_out)})


@router.get("/{plan_id}/review", response_model=ApiResponse)
def get_plan_review(plan_id: int, db: Session = Depends(get_db)):
    plan = db.query(TransitionPlan).filter(TransitionPlan.id == plan_id).first()
    if not plan:
        return ApiResponse(code=404, message="转段计划不存在", data=None)

    baby = db.query(BabyProfile).filter(BabyProfile.id == plan.baby_id).first()
    if not baby:
        return ApiResponse(code=404, message="关联的宝宝档案不存在", data=None)

    records = db.query(TransitionRecord).filter(
        TransitionRecord.plan_id == plan_id
    ).order_by(TransitionRecord.record_date.asc()).all()

    review = generate_plan_review(plan, baby, records)
    return ApiResponse(code=200, message="计划复盘查询成功", data={"review": review})

