from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime, date


VALID_DIGESTION_STATUSES = {"normal", "mild_discomfort", "constipation", "diarrhea", "allergy", "vomiting"}
VALID_CONSULTATION_TYPES = {"digestion", "growth", "nutrition", "transition", "other"}


class ApiResponse(BaseModel):
    code: int = Field(default=200, description="响应状态码")
    message: str = Field(default="success", description="响应消息")
    data: Optional[dict] = Field(default=None, description="响应数据")


class BabyProfileCreate(BaseModel):
    baby_name: str = Field(..., min_length=1, max_length=50, description="宝宝姓名")
    gender: str = Field(..., pattern="^(boy|girl)$", description="性别: boy/girl")
    birth_date: date = Field(..., description="出生日期")
    current_stage: Optional[int] = Field(default=1, ge=1, le=4, description="当前奶粉段位 1-4")
    guardian_name: Optional[str] = Field(None, max_length=50, description="监护人姓名")
    guardian_phone: Optional[str] = Field(None, max_length=20, description="监护人电话")

    @field_validator("birth_date")
    @classmethod
    def birth_date_not_in_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("出生日期不能是未来日期")
        return v


class BabyProfileUpdate(BaseModel):
    baby_name: Optional[str] = Field(None, min_length=1, max_length=50)
    gender: Optional[str] = Field(None, pattern="^(boy|girl)$")
    birth_date: Optional[date] = None
    current_stage: Optional[int] = Field(None, ge=1, le=4)
    guardian_name: Optional[str] = Field(None, max_length=50)
    guardian_phone: Optional[str] = Field(None, max_length=20)

    @field_validator("birth_date")
    @classmethod
    def birth_date_not_in_future(cls, v: Optional[date]) -> Optional[date]:
        if v is not None and v > date.today():
            raise ValueError("出生日期不能是未来日期")
        return v


class BabyProfileOut(BaseModel):
    id: int
    baby_name: str
    gender: str
    birth_date: date
    current_stage: int
    guardian_name: Optional[str]
    guardian_phone: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class HealthRecordCreate(BaseModel):
    baby_id: int = Field(..., description="宝宝档案ID")
    month_age: int = Field(..., ge=0, le=72, description="月龄")
    current_stage: int = Field(..., ge=1, le=4, description="当前段位")
    daily_intake_ml: float = Field(..., gt=0, description="每日奶量(ml)")
    digestion_status: str = Field(..., description="消化状态: normal/mild_discomfort/constipation/diarrhea/allergy/vomiting")
    digestion_note: Optional[str] = Field(None, description="消化情况备注")
    weight_kg: float = Field(..., gt=0, description="体重(kg)")
    height_cm: Optional[float] = Field(None, gt=0, description="身高(cm)")
    record_date: Optional[datetime] = None

    @field_validator("digestion_status")
    @classmethod
    def validate_digestion_status(cls, v: str) -> str:
        if v not in VALID_DIGESTION_STATUSES:
            raise ValueError(f"无效的消化状态: {v}，有效值为: {', '.join(sorted(VALID_DIGESTION_STATUSES))}")
        return v


class HealthRecordOut(BaseModel):
    id: int
    baby_id: int
    month_age: int
    current_stage: int
    daily_intake_ml: float
    digestion_status: str
    digestion_note: Optional[str]
    weight_kg: float
    height_cm: Optional[float]
    record_date: datetime
    created_at: datetime

    class Config:
        from_attributes = True


class StageMatchRequest(BaseModel):
    baby_id: int
    month_age: int = Field(..., ge=0, le=72, description="月龄")
    current_stage: Optional[int] = Field(None, ge=1, le=4, description="当前奶粉段位 1-4")


class NutritionAdviceRequest(BaseModel):
    baby_id: int
    month_age: int = Field(..., ge=0, le=72, description="月龄")
    current_stage: int = Field(..., ge=1, le=4, description="当前奶粉段位 1-4")
    daily_intake_ml: float = Field(..., gt=0, description="每日奶量(ml)")
    weight_kg: float = Field(..., gt=0, description="体重(kg)")


class WeightHistoryItem(BaseModel):
    month_age: int = Field(..., ge=0, le=72, description="月龄")
    weight_kg: float = Field(..., gt=0, description="体重(kg)")


class TransitionWarningRequest(BaseModel):
    baby_id: int
    month_age: int = Field(..., ge=0, le=72, description="月龄")
    current_stage: int = Field(..., ge=1, le=4, description="当前奶粉段位 1-4")
    daily_intake_ml: float = Field(..., gt=0, description="每日奶量(ml)")
    digestion_status: str = Field(..., description="消化状态")
    weight_kg: float = Field(..., gt=0, description="体重(kg)")
    weight_history: Optional[List[WeightHistoryItem]] = Field(None, description="体重历史数据")

    @field_validator("digestion_status")
    @classmethod
    def validate_digestion_status(cls, v: str) -> str:
        if v not in VALID_DIGESTION_STATUSES:
            raise ValueError(f"无效的消化状态: {v}，有效值为: {', '.join(sorted(VALID_DIGESTION_STATUSES))}")
        return v


class DoctorConsultationCreate(BaseModel):
    baby_id: int = Field(..., description="宝宝档案ID")
    consultation_type: str = Field(..., description="咨询类型: digestion/growth/nutrition/transition/other")
    symptoms: str = Field(..., min_length=1, max_length=2000, description="症状描述")
    scheduled_time: Optional[datetime] = None

    @field_validator("consultation_type")
    @classmethod
    def validate_consultation_type(cls, v: str) -> str:
        if v not in VALID_CONSULTATION_TYPES:
            raise ValueError(f"无效的咨询类型: {v}，有效值为: {', '.join(sorted(VALID_CONSULTATION_TYPES))}")
        return v


class DoctorConsultationOut(BaseModel):
    id: int
    baby_id: int
    consultation_type: str
    symptoms: str
    suggestion: Optional[str]
    status: str
    scheduled_time: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


VALID_TRANSITION_PLAN_STATUSES = {"draft", "in_progress", "paused", "completed", "cancelled"}


class DailyRatioItem(BaseModel):
    day: int = Field(..., ge=1, description="第几天")
    old_ratio: int = Field(..., ge=0, le=100, description="旧奶粉比例(%)")
    new_ratio: int = Field(..., ge=0, le=100, description="新奶粉比例(%)")

    @field_validator("new_ratio")
    @classmethod
    def ratios_sum_to_100(cls, v: int, info) -> int:
        old = info.data.get("old_ratio")
        if old is not None and old + v != 100:
            raise ValueError(f"新旧比例之和必须等于100，当前为 {old} + {v} = {old + v}")
        return v


class TransitionPlanCreate(BaseModel):
    baby_id: int = Field(..., description="宝宝档案ID")
    plan_name: str = Field(..., min_length=1, max_length=100, description="计划名称")
    original_stage: int = Field(..., ge=1, le=4, description="原段位 1-4")
    target_stage: int = Field(..., ge=1, le=4, description="目标段位 1-4")
    start_date: date = Field(..., description="计划开始日期")
    transition_days: int = Field(..., ge=1, le=60, description="过渡天数(1-60)")
    daily_ratio_schedule: List[DailyRatioItem] = Field(..., description="每日新旧奶粉比例安排")
    observation_focus: Optional[str] = Field(None, max_length=500, description="观察重点")
    status: Optional[str] = Field("draft", description="计划状态: draft/in_progress/paused/completed/cancelled")

    @field_validator("plan_name")
    @classmethod
    def plan_name_not_blank(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("计划名称不能为空或仅含空白字符")
        return stripped

    @field_validator("start_date")
    @classmethod
    def start_date_valid(cls, v: date) -> date:
        from datetime import timedelta
        if v > date.today():
            raise ValueError("开始日期不能是未来日期")
        if v < date.today() - timedelta(days=30):
            raise ValueError("开始日期不能早于30天前")
        return v

    @field_validator("target_stage")
    @classmethod
    def target_stage_different(cls, v: int, info) -> int:
        original = info.data.get("original_stage")
        if original is not None and v == original:
            raise ValueError("目标段位不能与原段位相同")
        if original is not None and abs(v - original) > 1:
            raise ValueError("不支持跨段转奶，目标段位只能与原段位相邻")
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> str:
        if v is None:
            return "draft"
        if v not in VALID_TRANSITION_PLAN_STATUSES:
            raise ValueError(f"无效的计划状态: {v}，有效值为: {', '.join(sorted(VALID_TRANSITION_PLAN_STATUSES))}")
        return v

    @field_validator("daily_ratio_schedule")
    @classmethod
    def validate_schedule(cls, v: List[DailyRatioItem], info) -> List[DailyRatioItem]:
        transition_days = info.data.get("transition_days")
        if transition_days is not None and len(v) != transition_days:
            raise ValueError(f"每日比例安排天数({len(v)})必须与过渡天数({transition_days})一致")
        days = [item.day for item in v]
        if sorted(days) != list(range(1, len(v) + 1)):
            raise ValueError("每日比例安排必须按顺序从第1天到第N天连续排列")
        return v


class TransitionPlanStatusUpdate(BaseModel):
    status: str = Field(..., description="计划状态: draft/in_progress/paused/completed/cancelled")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_TRANSITION_PLAN_STATUSES:
            raise ValueError(f"无效的计划状态: {v}，有效值为: {', '.join(sorted(VALID_TRANSITION_PLAN_STATUSES))}")
        return v


class TransitionPlanOut(BaseModel):
    id: int
    baby_id: int
    plan_name: str
    original_stage: int
    target_stage: int
    start_date: date
    transition_days: int
    daily_ratio_schedule: List[dict]
    observation_focus: Optional[str]
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def model_validate(cls, obj, **kwargs):
        if isinstance(obj, object) and hasattr(obj, "daily_ratio_schedule"):
            import json
            try:
                obj.daily_ratio_schedule = json.loads(obj.daily_ratio_schedule)
            except (json.JSONDecodeError, TypeError):
                obj.daily_ratio_schedule = []
        return super().model_validate(obj, **kwargs)


class TransitionRecordCreate(BaseModel):
    plan_id: int = Field(..., description="转段计划ID")
    record_date: date = Field(..., description="记录日期")
    old_formula_ratio: int = Field(..., ge=0, le=100, description="旧奶粉比例(%)")
    new_formula_ratio: int = Field(..., ge=0, le=100, description="新奶粉比例(%)")
    milk_intake_ml: float = Field(..., gt=0, description="当日奶量(ml)")
    digestion_status: str = Field(..., description="消化状态: normal/mild_discomfort/constipation/diarrhea/allergy/vomiting")
    weight_kg: Optional[float] = Field(None, gt=0, description="当日体重(kg)")
    note: Optional[str] = Field(None, max_length=500, description="备注")

    @field_validator("record_date")
    @classmethod
    def record_date_not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("记录日期不能是未来日期")
        return v

    @field_validator("new_formula_ratio")
    @classmethod
    def ratios_sum_to_100(cls, v: int, info) -> int:
        old = info.data.get("old_formula_ratio")
        if old is not None and old + v != 100:
            raise ValueError(f"新旧比例之和必须等于100，当前为 {old} + {v} = {old + v}")
        return v

    @field_validator("digestion_status")
    @classmethod
    def validate_digestion_status(cls, v: str) -> str:
        if v not in VALID_DIGESTION_STATUSES:
            raise ValueError(f"无效的消化状态: {v}，有效值为: {', '.join(sorted(VALID_DIGESTION_STATUSES))}")
        return v


class TransitionRecordOut(BaseModel):
    id: int
    plan_id: int
    record_date: date
    old_formula_ratio: int
    new_formula_ratio: int
    milk_intake_ml: float
    digestion_status: str
    weight_kg: Optional[float]
    note: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
