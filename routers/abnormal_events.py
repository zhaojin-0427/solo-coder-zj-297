from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime, date, timedelta
import json

from database import get_db
from models import (
    BabyProfile, AbnormalEvent, EventHandlingRecord,
    FormulaBatch, BrewingRecord, HealthRecord, TransitionPlan,
)
from schemas import (
    ApiResponse,
    AbnormalEventCreate, AbnormalEventOut, AbnormalEventWithDetails,
    AbnormalEventStatusUpdate, AbnormalEventAutoAnalysis,
    EventHandlingRecordCreate, EventHandlingRecordOut,
    AbnormalEventReplayRequest, AbnormalEventReplaySummary,
    ABNORMAL_EVENT_TYPE_NAMES, SEVERITY_LEVEL_NAMES, EVENT_STATUS_NAMES,
    HANDLING_TYPE_NAMES, RISK_LEVEL_NAMES,
)
from services import (
    analyze_abnormal_event_risk, generate_abnormal_event_replay,
    analyze_brewing_record, analyze_formula_batch,
)

router = APIRouter(prefix="/api/abnormal-events", tags=["喂养异常事件管理"])


def _serialize_event_out(event: AbnormalEvent) -> dict:
    base = AbnormalEventOut.model_validate(event).model_dump()
    suspected_causes = []
    if event.auto_suspected_causes:
        try:
            suspected_causes = json.loads(event.auto_suspected_causes)
        except (json.JSONDecodeError, TypeError):
            suspected_causes = [event.auto_suspected_causes]
    observation_suggestions = []
    if event.auto_observation_suggestions:
        try:
            observation_suggestions = json.loads(event.auto_observation_suggestions)
        except (json.JSONDecodeError, TypeError):
            observation_suggestions = [event.auto_observation_suggestions]
    base["auto_analysis"] = AbnormalEventAutoAnalysis(
        risk_level=event.auto_risk_level,
        risk_level_name=RISK_LEVEL_NAMES.get(event.auto_risk_level, event.auto_risk_level) if event.auto_risk_level else None,
        suspected_causes=suspected_causes,
        brewing_abnormal_related=event.auto_brewing_abnormal_related,
        batch_risk_related=event.auto_batch_risk_related,
        suggest_pause_batch=event.auto_suggest_pause_batch,
        suggest_stop_transition=event.auto_suggest_stop_transition,
        suggest_doctor_consultation=event.auto_suggest_doctor_consultation,
        observation_suggestions=observation_suggestions,
    ).model_dump() if event.auto_risk_level else None
    if base["auto_analysis"] and base["auto_analysis"].get("risk_level"):
        rl = base["auto_analysis"]["risk_level"]
        base["auto_analysis"]["risk_level_name"] = RISK_LEVEL_NAMES.get(rl, rl)
    base["event_type_name"] = ABNORMAL_EVENT_TYPE_NAMES.get(event.event_type, event.event_type)
    base["severity_level_name"] = SEVERITY_LEVEL_NAMES.get(event.severity_level, event.severity_level)
    base["status_name"] = EVENT_STATUS_NAMES.get(event.status, event.status)
    return base


def _enrich_event_details(event: AbnormalEvent, db: Session, baby=None) -> dict:
    event_dict = _serialize_event_out(event)
    baby = baby or db.query(BabyProfile).filter(BabyProfile.id == event.baby_id).first()
    if baby:
        event_dict["baby_info"] = {
            "id": baby.id,
            "baby_name": baby.baby_name,
            "gender": baby.gender,
            "birth_date": baby.birth_date.isoformat() if hasattr(baby.birth_date, "isoformat") else str(baby.birth_date),
            "current_stage": baby.current_stage,
        }
    if event.batch_id:
        batch = db.query(FormulaBatch).filter(FormulaBatch.id == event.batch_id).first()
        if batch:
            event_dict["batch_info"] = {
                "id": batch.id,
                "brand_name": batch.brand_name,
                "product_name": batch.product_name,
                "stage": batch.stage,
                "batch_number": batch.batch_number,
                "is_active": batch.is_active,
            }
    if event.brewing_record_id:
        br = db.query(BrewingRecord).filter(BrewingRecord.id == event.brewing_record_id).first()
        if br:
            event_dict["brewing_record_info"] = {
                "id": br.id,
                "brewing_time": br.brewing_time.isoformat() if hasattr(br.brewing_time, "isoformat") else str(br.brewing_time),
                "water_temperature": br.water_temperature,
                "formula_scoops": br.formula_scoops,
                "water_volume_ml": br.water_volume_ml,
                "actual_consumed_ml": br.actual_consumed_ml,
            }
    handling_records = (
        db.query(EventHandlingRecord)
        .filter(EventHandlingRecord.event_id == event.id)
        .order_by(EventHandlingRecord.handling_time.desc(), EventHandlingRecord.created_at.desc())
        .all()
    )
    hr_list = []
    for hr in handling_records:
        hr_dict = EventHandlingRecordOut.model_validate(hr).model_dump()
        hr_dict["handling_type_name"] = HANDLING_TYPE_NAMES.get(hr.handling_type, hr.handling_type)
        if hr.status_after:
            hr_dict["status_after_name"] = EVENT_STATUS_NAMES.get(hr.status_after, hr.status_after)
        hr_list.append(hr_dict)
    event_dict["handling_records"] = hr_list
    return event_dict


@router.post("", response_model=ApiResponse)
def create_abnormal_event(data: AbnormalEventCreate, db: Session = Depends(get_db)):
    baby = db.query(BabyProfile).filter(BabyProfile.id == data.baby_id).first()
    if not baby:
        return ApiResponse(code=404, message="宝宝档案不存在", data=None)

    batch = None
    if data.batch_id:
        batch = db.query(FormulaBatch).filter(FormulaBatch.id == data.batch_id).first()
        if not batch:
            return ApiResponse(code=404, message="关联的奶粉批次不存在", data=None)
        if batch.baby_id != data.baby_id:
            return ApiResponse(code=400, message="关联批次不属于该宝宝", data=None)

    brewing_record = None
    if data.brewing_record_id:
        brewing_record = db.query(BrewingRecord).filter(BrewingRecord.id == data.brewing_record_id).first()
        if not brewing_record:
            return ApiResponse(code=404, message="关联的冲泡记录不存在", data=None)
        if brewing_record.baby_id != data.baby_id:
            return ApiResponse(code=400, message="关联冲泡记录不属于该宝宝", data=None)

    latest_health_record = (
        db.query(HealthRecord)
        .filter(HealthRecord.baby_id == data.baby_id)
        .order_by(HealthRecord.record_date.desc())
        .first()
    )

    active_transition_plans = (
        db.query(TransitionPlan)
        .filter(
            TransitionPlan.baby_id == data.baby_id,
            TransitionPlan.status.in_(["in_progress", "draft"]),
        )
        .all()
    )

    event_time_date = data.event_time.date() if hasattr(data.event_time, "date") else data.event_time
    if isinstance(event_time_date, datetime):
        event_time_date = event_time_date.date()
    recent_start = event_time_date - timedelta(days=30)
    recent_events = (
        db.query(AbnormalEvent)
        .filter(
            AbnormalEvent.baby_id == data.baby_id,
            AbnormalEvent.id != 0,
        )
        .order_by(AbnormalEvent.event_time.desc())
        .limit(10)
        .all()
    )
    recent_events = [e for e in recent_events if e.id != 0]

    event_data_dict = data.model_dump()
    risk_analysis = analyze_abnormal_event_risk(
        event_data=event_data_dict,
        baby=baby,
        batch=batch,
        brewing_record=brewing_record,
        latest_health_record=latest_health_record,
        active_transition_plans=active_transition_plans,
        recent_events=recent_events,
    )

    event = AbnormalEvent(
        baby_id=data.baby_id,
        event_type=data.event_type,
        event_time=data.event_time,
        batch_id=data.batch_id,
        brewing_record_id=data.brewing_record_id,
        daily_milk_intake_ml=data.daily_milk_intake_ml,
        digestion_status=data.digestion_status,
        body_temperature=data.body_temperature,
        weight_kg=data.weight_kg,
        symptom_description=data.symptom_description,
        severity_level=data.severity_level,
        on_site_measures=data.on_site_measures,
        status="open",
        auto_risk_level=risk_analysis["risk_level"],
        auto_suspected_causes=json.dumps(risk_analysis["suspected_causes"], ensure_ascii=False),
        auto_brewing_abnormal_related=risk_analysis["brewing_abnormal_related"],
        auto_batch_risk_related=risk_analysis["batch_risk_related"],
        auto_suggest_pause_batch=risk_analysis["suggest_pause_batch"],
        auto_suggest_stop_transition=risk_analysis["suggest_stop_transition"],
        auto_suggest_doctor_consultation=risk_analysis["suggest_doctor_consultation"],
        auto_observation_suggestions=json.dumps(risk_analysis["observation_suggestions"], ensure_ascii=False),
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    return ApiResponse(
        code=200,
        message="异常事件创建成功，已完成风险评估",
        data={
            "event": _serialize_event_out(event),
            "risk_score": risk_analysis["risk_score"],
        },
    )


@router.get("", response_model=ApiResponse)
def list_abnormal_events(
    baby_id: Optional[int] = None,
    status: Optional[str] = None,
    event_type: Optional[str] = None,
    risk_level: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
):
    query = db.query(AbnormalEvent)
    if baby_id is not None:
        baby = db.query(BabyProfile).filter(BabyProfile.id == baby_id).first()
        if not baby:
            return ApiResponse(code=404, message="宝宝档案不存在", data=None)
        query = query.filter(AbnormalEvent.baby_id == baby_id)
    if status:
        query = query.filter(AbnormalEvent.status == status)
    if event_type:
        query = query.filter(AbnormalEvent.event_type == event_type)
    if risk_level:
        query = query.filter(AbnormalEvent.auto_risk_level == risk_level)
    if start_date:
        try:
            sd = date.fromisoformat(start_date)
            query = query.filter(AbnormalEvent.event_time >= datetime.combine(sd, datetime.min.time()))
        except ValueError:
            pass
    if end_date:
        try:
            ed = date.fromisoformat(end_date)
            query = query.filter(AbnormalEvent.event_time <= datetime.combine(ed, datetime.max.time()))
        except ValueError:
            pass

    events = query.order_by(AbnormalEvent.event_time.desc()).all()
    data = [_serialize_event_out(e) for e in events]
    return ApiResponse(code=200, message="查询成功", data={"list": data, "total": len(data)})


@router.get("/{event_id}", response_model=ApiResponse)
def get_abnormal_event_detail(event_id: int, db: Session = Depends(get_db)):
    event = db.query(AbnormalEvent).filter(AbnormalEvent.id == event_id).first()
    if not event:
        return ApiResponse(code=404, message="异常事件不存在", data=None)
    detail = _enrich_event_details(event, db)
    return ApiResponse(code=200, message="查询成功", data={"event": detail})


@router.put("/{event_id}/status", response_model=ApiResponse)
def update_abnormal_event_status(
    event_id: int,
    data: AbnormalEventStatusUpdate,
    db: Session = Depends(get_db),
):
    event = db.query(AbnormalEvent).filter(AbnormalEvent.id == event_id).first()
    if not event:
        return ApiResponse(code=404, message="异常事件不存在", data=None)

    if event.status == "closed" and data.status != "reopened":
        return ApiResponse(code=400, message="已关闭事件只能转为重新开启状态（reopened）", data=None)

    if data.status == "closed":
        event.closed_at = datetime.utcnow()
    else:
        event.closed_at = None

    event.status = data.status
    event.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(event)

    return ApiResponse(
        code=200,
        message=f"事件状态已更新为 {EVENT_STATUS_NAMES.get(data.status, data.status)}",
        data={"event": _serialize_event_out(event)},
    )


@router.post("/{event_id}/handling-records", response_model=ApiResponse)
def add_event_handling_record(
    event_id: int,
    data: EventHandlingRecordCreate,
    db: Session = Depends(get_db),
):
    event = db.query(AbnormalEvent).filter(AbnormalEvent.id == event_id).first()
    if not event:
        return ApiResponse(code=404, message="异常事件不存在", data=None)

    if event.id != data.event_id:
        return ApiResponse(code=400, message="URL中的event_id与请求体中不一致", data=None)

    if event.status == "closed":
        return ApiResponse(code=400, message="事件已关闭，无法追加处置记录，请先重新开启", data=None)

    hr = EventHandlingRecord(
        event_id=event_id,
        handler_name=data.handler_name,
        handling_time=data.handling_time or datetime.utcnow(),
        handling_type=data.handling_type,
        handling_description=data.handling_description,
        follow_up_plan=data.follow_up_plan,
        status_after=data.status_after,
    )
    db.add(hr)

    if data.status_after and data.status_after != event.status:
        if data.status_after == "closed":
            event.closed_at = datetime.utcnow()
        else:
            event.closed_at = None
        event.status = data.status_after

    event.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(hr)
    db.refresh(event)

    hr_dict = EventHandlingRecordOut.model_validate(hr).model_dump()
    hr_dict["handling_type_name"] = HANDLING_TYPE_NAMES.get(hr.handling_type, hr.handling_type)
    if hr.status_after:
        hr_dict["status_after_name"] = EVENT_STATUS_NAMES.get(hr.status_after, hr.status_after)

    return ApiResponse(
        code=200,
        message="处置记录追加成功",
        data={
            "handling_record": hr_dict,
            "event_status": EVENT_STATUS_NAMES.get(event.status, event.status),
        },
    )


@router.get("/{event_id}/handling-records", response_model=ApiResponse)
def list_event_handling_records(event_id: int, db: Session = Depends(get_db)):
    event = db.query(AbnormalEvent).filter(AbnormalEvent.id == event_id).first()
    if not event:
        return ApiResponse(code=404, message="异常事件不存在", data=None)
    records = (
        db.query(EventHandlingRecord)
        .filter(EventHandlingRecord.event_id == event_id)
        .order_by(EventHandlingRecord.handling_time.desc(), EventHandlingRecord.created_at.desc())
        .all()
    )
    data = []
    for hr in records:
        hr_dict = EventHandlingRecordOut.model_validate(hr).model_dump()
        hr_dict["handling_type_name"] = HANDLING_TYPE_NAMES.get(hr.handling_type, hr.handling_type)
        if hr.status_after:
            hr_dict["status_after_name"] = EVENT_STATUS_NAMES.get(hr.status_after, hr.status_after)
        data.append(hr_dict)
    return ApiResponse(code=200, message="查询成功", data={"list": data, "total": len(data)})


@router.put("/{event_id}/close", response_model=ApiResponse)
def close_abnormal_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(AbnormalEvent).filter(AbnormalEvent.id == event_id).first()
    if not event:
        return ApiResponse(code=404, message="异常事件不存在", data=None)

    event.status = "closed"
    event.closed_at = datetime.utcnow()
    event.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(event)

    return ApiResponse(
        code=200,
        message="事件已关闭",
        data={"event": _serialize_event_out(event)},
    )


@router.post("/replay", response_model=ApiResponse)
def abnormal_event_replay(data: AbnormalEventReplayRequest, db: Session = Depends(get_db)):
    baby = db.query(BabyProfile).filter(BabyProfile.id == data.baby_id).first()
    if not baby:
        return ApiResponse(code=404, message="宝宝档案不存在", data=None)

    start_dt = datetime.combine(data.start_date, datetime.min.time())
    end_dt = datetime.combine(data.end_date, datetime.max.time())
    events = (
        db.query(AbnormalEvent)
        .filter(
            AbnormalEvent.baby_id == data.baby_id,
            AbnormalEvent.event_time >= start_dt,
            AbnormalEvent.event_time <= end_dt,
        )
        .order_by(AbnormalEvent.event_time.desc())
        .all()
    )

    batch_ids = {e.batch_id for e in events if e.batch_id}
    batches_map = {}
    if batch_ids:
        batches = db.query(FormulaBatch).filter(FormulaBatch.id.in_(batch_ids)).all()
        for b in batches:
            batches_map[b.id] = {
                "brand_name": b.brand_name,
                "product_name": b.product_name,
                "batch_number": b.batch_number,
            }

    active_transition_plans = (
        db.query(TransitionPlan)
        .filter(
            TransitionPlan.baby_id == data.baby_id,
            TransitionPlan.status.in_(["in_progress", "draft"]),
        )
        .all()
    )

    summary = generate_abnormal_event_replay(
        baby=baby,
        start_date=data.start_date,
        end_date=data.end_date,
        events=events,
        batches_map=batches_map,
        active_transition_plans=active_transition_plans,
    )
    summary["recurrence_risk_level_name"] = RISK_LEVEL_NAMES.get(
        summary["recurrence_risk_level"], summary["recurrence_risk_level"]
    )

    return ApiResponse(
        code=200,
        message="异常事件复盘统计完成",
        data={"summary": summary},
    )


@router.get("/meta/types", response_model=ApiResponse)
def get_event_meta_types():
    types = [
        {"type": k, "name": v} for k, v in ABNORMAL_EVENT_TYPE_NAMES.items()
    ]
    severities = [
        {"level": k, "name": v} for k, v in SEVERITY_LEVEL_NAMES.items()
    ]
    statuses = [
        {"status": k, "name": v} for k, v in EVENT_STATUS_NAMES.items()
    ]
    handling_types = [
        {"type": k, "name": v} for k, v in HANDLING_TYPE_NAMES.items()
    ]
    risk_levels = [
        {"level": k, "name": v} for k, v in RISK_LEVEL_NAMES.items()
    ]
    return ApiResponse(
        code=200,
        message="查询成功",
        data={
            "event_types": types,
            "severity_levels": severities,
            "event_statuses": statuses,
            "handling_types": handling_types,
            "risk_levels": risk_levels,
        },
    )
