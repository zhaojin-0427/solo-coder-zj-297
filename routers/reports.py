from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime, timedelta
import uuid
import json
from database import get_db
from models import (
    BabyProfile, FeedingReport, ReportShare,
    HealthRecord, BrewingRecord, FormulaBatch, AbnormalEvent,
    TransitionPlan, TransitionRecord, DoctorConsultation,
)
from schemas import (
    FeedingReportGenerateRequest, FeedingReportStatusUpdate,
    FeedingReportOut, FeedingReportDetail,
    ReportShareCreate, ReportShareOut, SharedReportSummary,
    ApiResponse, REPORT_TYPE_NAMES,
)
from services import generate_feeding_report, calculate_report_period

router = APIRouter(prefix="/api/reports", tags=["喂养报告管理"])


@router.post("/generate", response_model=ApiResponse)
def generate_report(data: FeedingReportGenerateRequest, db: Session = Depends(get_db)):
    baby = db.query(BabyProfile).filter(BabyProfile.id == data.baby_id).first()
    if not baby:
        return ApiResponse(code=404, message="宝宝档案不存在", data=None)

    period_start = data.period_start
    period_end = data.period_end
    if not period_start or not period_end:
        period_start, period_end = calculate_report_period(data.report_type)

    if period_end < period_start:
        return ApiResponse(code=400, message="结束日期不能早于开始日期", data=None)

    existing = db.query(FeedingReport).filter(
        FeedingReport.baby_id == data.baby_id,
        FeedingReport.report_type == data.report_type,
        FeedingReport.period_start == period_start,
        FeedingReport.period_end == period_end,
    ).first()

    if existing and existing.status == "completed":
        return ApiResponse(
            code=200,
            message="该周期报告已存在",
            data={"report": FeedingReportOut.model_validate(existing).model_dump(), "is_new": False},
        )

    report = FeedingReport(
        baby_id=data.baby_id,
        report_type=data.report_type,
        period_start=period_start,
        period_end=period_end,
        status="generating",
    )
    if existing:
        report = existing
        report.status = "generating"
    else:
        db.add(report)
    db.commit()
    db.refresh(report)

    try:
        start_dt = datetime.combine(period_start, datetime.min.time())
        end_dt = datetime.combine(period_end, datetime.max.time())

        health_records = db.query(HealthRecord).filter(
            HealthRecord.baby_id == data.baby_id,
            HealthRecord.record_date >= start_dt,
            HealthRecord.record_date <= end_dt,
        ).order_by(HealthRecord.record_date.asc()).all()

        brewing_records = db.query(BrewingRecord).filter(
            BrewingRecord.baby_id == data.baby_id,
            BrewingRecord.brewing_time >= start_dt,
            BrewingRecord.brewing_time <= end_dt,
        ).order_by(BrewingRecord.brewing_time.asc()).all()

        formula_batches = db.query(FormulaBatch).filter(
            FormulaBatch.baby_id == data.baby_id,
        ).all()

        abnormal_events = db.query(AbnormalEvent).filter(
            AbnormalEvent.baby_id == data.baby_id,
            AbnormalEvent.event_time >= start_dt,
            AbnormalEvent.event_time <= end_dt,
        ).all()

        transition_plans = db.query(TransitionPlan).filter(
            TransitionPlan.baby_id == data.baby_id,
            TransitionPlan.start_date <= end_dt,
        ).all()

        plan_ids = [p.id for p in transition_plans]
        transition_records = []
        if plan_ids:
            transition_records = db.query(TransitionRecord).filter(
                TransitionRecord.plan_id.in_(plan_ids),
                TransitionRecord.record_date >= start_dt,
                TransitionRecord.record_date <= end_dt,
            ).all()

        doctor_consultations = db.query(DoctorConsultation).filter(
            DoctorConsultation.baby_id == data.baby_id,
            DoctorConsultation.created_at >= start_dt,
            DoctorConsultation.created_at <= end_dt,
        ).all()

        result = generate_feeding_report(
            baby=baby,
            report_type=data.report_type,
            period_start=period_start,
            period_end=period_end,
            health_records=health_records,
            brewing_records=brewing_records,
            formula_batches=formula_batches,
            abnormal_events=abnormal_events,
            transition_plans=transition_plans,
            transition_records=transition_records,
            doctor_consultations=doctor_consultations,
        )

        report.title = result["title"]
        report.summary = result["summary"]
        report.report_data = result["report_data"]
        report.total_milk_ml = result["total_milk_ml"]
        report.avg_daily_milk_ml = result["avg_daily_milk_ml"]
        report.weight_change_kg = result["weight_change_kg"]
        report.digestion_abnormal_count = result["digestion_abnormal_count"]
        report.brewing_abnormal_count = result["brewing_abnormal_count"]
        report.batch_risk_count = result["batch_risk_count"]
        report.transition_progress = result["transition_progress"]
        report.doctor_consultation_count = result["doctor_consultation_count"]
        report.abnormal_event_completion_rate = result["abnormal_event_completion_rate"]
        report.overall_score = result["overall_score"]
        report.status = "completed"
        report.generated_at = datetime.utcnow()

        db.commit()
        db.refresh(report)

        return ApiResponse(
            code=200,
            message="报告生成成功",
            data={"report": FeedingReportDetail.model_validate(report).model_dump(), "is_new": not existing},
        )
    except Exception as e:
        report.status = "failed"
        db.commit()
        return ApiResponse(code=500, message=f"报告生成失败: {str(e)}", data=None)


@router.get("", response_model=ApiResponse)
def list_reports(
    baby_id: Optional[int] = Query(None, description="宝宝ID，可选"),
    report_type: Optional[str] = Query(None, description="报告类型: weekly/monthly"),
    status: Optional[str] = Query(None, description="报告状态"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(10, ge=1, le=100, description="每页条数"),
    db: Session = Depends(get_db),
):
    query = db.query(FeedingReport)
    if baby_id:
        query = query.filter(FeedingReport.baby_id == baby_id)
    if report_type:
        query = query.filter(FeedingReport.report_type == report_type)
    if status:
        query = query.filter(FeedingReport.status == status)

    total = query.count()
    reports = query.order_by(FeedingReport.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    data = [FeedingReportOut.model_validate(r).model_dump() for r in reports]
    return ApiResponse(
        code=200,
        message="查询成功",
        data={
            "list": data,
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    )


@router.get("/{report_id}", response_model=ApiResponse)
def get_report_detail(report_id: int, db: Session = Depends(get_db)):
    report = db.query(FeedingReport).filter(FeedingReport.id == report_id).first()
    if not report:
        return ApiResponse(code=404, message="报告不存在", data=None)
    return ApiResponse(
        code=200,
        message="查询成功",
        data={"report": FeedingReportDetail.model_validate(report).model_dump()},
    )


@router.post("/{report_id}/regenerate", response_model=ApiResponse)
def regenerate_report(report_id: int, db: Session = Depends(get_db)):
    report = db.query(FeedingReport).filter(FeedingReport.id == report_id).first()
    if not report:
        return ApiResponse(code=404, message="报告不存在", data=None)

    baby = db.query(BabyProfile).filter(BabyProfile.id == report.baby_id).first()
    if not baby:
        return ApiResponse(code=404, message="宝宝档案不存在", data=None)

    report.status = "generating"
    report.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(report)

    try:
        period_start = report.period_start
        period_end = report.period_end
        start_dt = datetime.combine(period_start, datetime.min.time())
        end_dt = datetime.combine(period_end, datetime.max.time())

        health_records = db.query(HealthRecord).filter(
            HealthRecord.baby_id == report.baby_id,
            HealthRecord.record_date >= start_dt,
            HealthRecord.record_date <= end_dt,
        ).order_by(HealthRecord.record_date.asc()).all()

        brewing_records = db.query(BrewingRecord).filter(
            BrewingRecord.baby_id == report.baby_id,
            BrewingRecord.brewing_time >= start_dt,
            BrewingRecord.brewing_time <= end_dt,
        ).order_by(BrewingRecord.brewing_time.asc()).all()

        formula_batches = db.query(FormulaBatch).filter(
            FormulaBatch.baby_id == report.baby_id,
        ).all()

        abnormal_events = db.query(AbnormalEvent).filter(
            AbnormalEvent.baby_id == report.baby_id,
            AbnormalEvent.event_time >= start_dt,
            AbnormalEvent.event_time <= end_dt,
        ).all()

        transition_plans = db.query(TransitionPlan).filter(
            TransitionPlan.baby_id == report.baby_id,
            TransitionPlan.start_date <= end_dt,
        ).all()

        plan_ids = [p.id for p in transition_plans]
        transition_records = []
        if plan_ids:
            transition_records = db.query(TransitionRecord).filter(
                TransitionRecord.plan_id.in_(plan_ids),
                TransitionRecord.record_date >= start_dt,
                TransitionRecord.record_date <= end_dt,
            ).all()

        doctor_consultations = db.query(DoctorConsultation).filter(
            DoctorConsultation.baby_id == report.baby_id,
            DoctorConsultation.created_at >= start_dt,
            DoctorConsultation.created_at <= end_dt,
        ).all()

        result = generate_feeding_report(
            baby=baby,
            report_type=report.report_type,
            period_start=period_start,
            period_end=period_end,
            health_records=health_records,
            brewing_records=brewing_records,
            formula_batches=formula_batches,
            abnormal_events=abnormal_events,
            transition_plans=transition_plans,
            transition_records=transition_records,
            doctor_consultations=doctor_consultations,
        )

        report.title = result["title"]
        report.summary = result["summary"]
        report.report_data = result["report_data"]
        report.total_milk_ml = result["total_milk_ml"]
        report.avg_daily_milk_ml = result["avg_daily_milk_ml"]
        report.weight_change_kg = result["weight_change_kg"]
        report.digestion_abnormal_count = result["digestion_abnormal_count"]
        report.brewing_abnormal_count = result["brewing_abnormal_count"]
        report.batch_risk_count = result["batch_risk_count"]
        report.transition_progress = result["transition_progress"]
        report.doctor_consultation_count = result["doctor_consultation_count"]
        report.abnormal_event_completion_rate = result["abnormal_event_completion_rate"]
        report.overall_score = result["overall_score"]
        report.status = "completed"
        report.generated_at = datetime.utcnow()
        report.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(report)

        return ApiResponse(
            code=200,
            message="报告重新生成成功",
            data={"report": FeedingReportDetail.model_validate(report).model_dump()},
        )
    except Exception as e:
        report.status = "failed"
        db.commit()
        return ApiResponse(code=500, message=f"报告重新生成失败: {str(e)}", data=None)


@router.put("/{report_id}/status", response_model=ApiResponse)
def update_report_status(report_id: int, data: FeedingReportStatusUpdate, db: Session = Depends(get_db)):
    report = db.query(FeedingReport).filter(FeedingReport.id == report_id).first()
    if not report:
        return ApiResponse(code=404, message="报告不存在", data=None)

    report.status = data.status
    report.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(report)
    return ApiResponse(
        code=200,
        message="报告状态更新成功",
        data={"report": FeedingReportOut.model_validate(report).model_dump()},
    )


@router.post("/{report_id}/share", response_model=ApiResponse)
def create_report_share(report_id: int, data: ReportShareCreate, db: Session = Depends(get_db)):
    report = db.query(FeedingReport).filter(FeedingReport.id == report_id).first()
    if not report:
        return ApiResponse(code=404, message="报告不存在", data=None)
    if report.status != "completed":
        return ApiResponse(code=400, message="仅已完成的报告可以分享", data=None)

    share_code = uuid.uuid4().hex[:12]
    expires_days = data.expires_days or 7
    expires_at = datetime.utcnow() + timedelta(days=expires_days)

    share = ReportShare(
        report_id=report_id,
        share_code=share_code,
        shared_by=data.shared_by,
        view_count=0,
        expires_at=expires_at,
        is_active=True,
    )
    db.add(share)
    db.commit()
    db.refresh(share)

    return ApiResponse(
        code=200,
        message="分享链接创建成功",
        data={
            "share": ReportShareOut.model_validate(share).model_dump(),
            "share_url": f"/api/reports/shared/{share_code}",
        },
    )


@router.get("/shared/{share_code}", response_model=ApiResponse)
def get_shared_report(share_code: str, db: Session = Depends(get_db)):
    share = db.query(ReportShare).filter(
        ReportShare.share_code == share_code,
        ReportShare.is_active == True,
    ).first()

    if not share:
        return ApiResponse(code=404, message="分享链接不存在或已失效", data=None)

    if share.expires_at and share.expires_at < datetime.utcnow():
        share.is_active = False
        db.commit()
        return ApiResponse(code=404, message="分享链接已过期", data=None)

    report = db.query(FeedingReport).filter(FeedingReport.id == share.report_id).first()
    if not report:
        return ApiResponse(code=404, message="报告不存在", data=None)

    baby = db.query(BabyProfile).filter(BabyProfile.id == report.baby_id).first()
    baby_name = baby.baby_name if baby else ""

    share.view_count += 1
    db.commit()

    summary = SharedReportSummary(
        report_id=report.id,
        baby_name=baby_name,
        report_type=report.report_type,
        report_type_name=REPORT_TYPE_NAMES.get(report.report_type, report.report_type),
        period_start=report.period_start,
        period_end=report.period_end,
        title=report.title,
        summary=report.summary,
        total_milk_ml=report.total_milk_ml,
        avg_daily_milk_ml=report.avg_daily_milk_ml,
        weight_change_kg=report.weight_change_kg,
        digestion_abnormal_count=report.digestion_abnormal_count,
        brewing_abnormal_count=report.brewing_abnormal_count,
        batch_risk_count=report.batch_risk_count,
        transition_progress=report.transition_progress,
        doctor_consultation_count=report.doctor_consultation_count,
        abnormal_event_completion_rate=report.abnormal_event_completion_rate,
        overall_score=report.overall_score,
        generated_at=report.generated_at,
        shared_by=share.shared_by,
    )

    return ApiResponse(
        code=200,
        message="查询成功",
        data={"report": summary.model_dump()},
    )


@router.get("/share/list/{report_id}", response_model=ApiResponse)
def list_report_shares(report_id: int, db: Session = Depends(get_db)):
    report = db.query(FeedingReport).filter(FeedingReport.id == report_id).first()
    if not report:
        return ApiResponse(code=404, message="报告不存在", data=None)

    shares = db.query(ReportShare).filter(
        ReportShare.report_id == report_id
    ).order_by(ReportShare.created_at.desc()).all()

    data = [ReportShareOut.model_validate(s).model_dump() for s in shares]
    return ApiResponse(code=200, message="查询成功", data={"list": data, "total": len(data)})


@router.delete("/share/{share_id}", response_model=ApiResponse)
def revoke_report_share(share_id: int, db: Session = Depends(get_db)):
    share = db.query(ReportShare).filter(ReportShare.id == share_id).first()
    if not share:
        return ApiResponse(code=404, message="分享记录不存在", data=None)

    share.is_active = False
    share.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(share)
    return ApiResponse(code=200, message="分享链接已撤销", data={"share": ReportShareOut.model_validate(share).model_dump()})
