from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict
from datetime import datetime, date


VALID_DIGESTION_STATUSES = {"normal", "mild_discomfort", "constipation", "diarrhea", "allergy", "vomiting"}
VALID_CONSULTATION_TYPES = {"digestion", "growth", "nutrition", "transition", "other"}
VALID_STORAGE_METHODS = {"refrigerated", "cool_dry", "room_temperature"}
VALID_REMAINING_HANDLING = {"discarded", "stored", "used_later", "other"}
STORAGE_METHOD_NAMES = {
    "refrigerated": "冷藏",
    "cool_dry": "阴凉干燥",
    "room_temperature": "常温",
}
REMAINING_HANDLING_NAMES = {
    "discarded": "丢弃",
    "stored": "储存",
    "used_later": "稍后使用",
    "other": "其他",
}
MIN_WATER_TEMPERATURE = 40.0
MAX_WATER_TEMPERATURE = 70.0
SCOOP_TO_WATER_RATIO = 30.0
OPENING_SAFE_DAYS = 30


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


class FormulaBatchCreate(BaseModel):
    baby_id: int = Field(..., description="宝宝档案ID")
    brand_name: str = Field(..., min_length=1, max_length=100, description="品牌名")
    product_name: str = Field(..., min_length=1, max_length=100, description="产品名")
    stage: int = Field(..., ge=1, le=4, description="奶粉段位 1-4")
    batch_number: str = Field(..., min_length=1, max_length=100, description="批次号")
    opening_date: date = Field(..., description="开封日期")
    expiry_date: date = Field(..., description="保质期")
    can_capacity_grams: float = Field(..., gt=0, description="每罐容量(克)")
    current_remaining_grams: float = Field(..., ge=0, description="当前剩余量(克)")
    storage_method: str = Field(..., description="储存方式: refrigerated/cool_dry/room_temperature")
    notes: Optional[str] = Field(None, max_length=500, description="备注")

    @field_validator("opening_date")
    @classmethod
    def opening_date_not_future(cls, v: date) -> date:
        if v > date.today():
            raise ValueError("开封日期不能是未来日期")
        return v

    @field_validator("expiry_date")
    @classmethod
    def expiry_date_valid(cls, v: date, info) -> date:
        opening = info.data.get("opening_date")
        if opening and v <= opening:
            raise ValueError("保质期必须晚于开封日期")
        if v < date.today():
            raise ValueError("保质期不能早于今天")
        return v

    @field_validator("current_remaining_grams")
    @classmethod
    def remaining_not_exceed_capacity(cls, v: float, info) -> float:
        capacity = info.data.get("can_capacity_grams")
        if capacity is not None and v > capacity:
            raise ValueError("当前剩余量不能超过每罐容量")
        return v

    @field_validator("storage_method")
    @classmethod
    def validate_storage_method(cls, v: str) -> str:
        if v not in VALID_STORAGE_METHODS:
            raise ValueError(f"无效的储存方式: {v}，有效值为: {', '.join(sorted(VALID_STORAGE_METHODS))}")
        return v


class FormulaBatchUpdateRemaining(BaseModel):
    current_remaining_grams: float = Field(..., ge=0, description="当前剩余量(克)")


class FormulaBatchOut(BaseModel):
    id: int
    baby_id: int
    brand_name: str
    product_name: str
    stage: int
    batch_number: str
    opening_date: date
    expiry_date: date
    can_capacity_grams: float
    current_remaining_grams: float
    storage_method: str
    notes: Optional[str]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class FormulaBatchWithAnalysis(FormulaBatchOut):
    risk_analysis: Optional[Dict] = None


class BrewingRecordCreate(BaseModel):
    baby_id: int = Field(..., description="宝宝档案ID")
    batch_id: int = Field(..., description="奶粉批次ID")
    brewing_time: datetime = Field(..., description="冲泡时间")
    water_temperature: float = Field(..., description="水温(摄氏度)")
    formula_scoops: float = Field(..., gt=0, description="奶粉勺数")
    water_volume_ml: float = Field(..., gt=0, description="水量(毫升)")
    actual_consumed_ml: float = Field(..., ge=0, description="实际饮用量(毫升)")
    has_remaining: bool = Field(default=False, description="是否剩余")
    remaining_handling: Optional[str] = Field(None, description="剩余处理方式")
    abnormal_notes: Optional[str] = Field(None, max_length=500, description="异常备注")

    @field_validator("brewing_time")
    @classmethod
    def brewing_time_not_future(cls, v: datetime) -> datetime:
        if v > datetime.now():
            raise ValueError("冲泡时间不能是未来时间")
        return v

    @field_validator("water_temperature")
    @classmethod
    def validate_water_temperature(cls, v: float) -> float:
        if v < MIN_WATER_TEMPERATURE or v > MAX_WATER_TEMPERATURE:
            raise ValueError(
                f"水温超出合理范围: {v}°C，合理范围为 {MIN_WATER_TEMPERATURE}-{MAX_WATER_TEMPERATURE}°C"
            )
        return v

    @field_validator("actual_consumed_ml")
    @classmethod
    def consumed_not_exceed_water(cls, v: float, info) -> float:
        water = info.data.get("water_volume_ml")
        if water is not None and v > water:
            raise ValueError("实际饮用量不能超过冲泡水量")
        return v

    @field_validator("remaining_handling")
    @classmethod
    def validate_remaining_handling(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_REMAINING_HANDLING:
            raise ValueError(f"无效的剩余处理方式: {v}，有效值为: {', '.join(sorted(VALID_REMAINING_HANDLING))}")
        return v


class BrewingRecordOut(BaseModel):
    id: int
    baby_id: int
    batch_id: int
    brewing_time: datetime
    water_temperature: float
    formula_scoops: float
    water_volume_ml: float
    actual_consumed_ml: float
    has_remaining: bool
    remaining_handling: Optional[str]
    abnormal_notes: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class BrewingRecordWithAnalysis(BrewingRecordOut):
    safety_analysis: Optional[Dict] = None


class BrewingDailyReport(BaseModel):
    baby_id: int
    baby_name: str
    report_date: date
    total_brewing_count: int
    total_water_volume_ml: float
    total_formula_scoops: float
    total_actual_consumed_ml: float
    total_wasted_ml: float
    batch_usage_distribution: List[Dict]
    abnormal_count: int
    abnormal_details: List[Dict]
    risk_level: str
    overall_suggestions: List[str]
    records: List[BrewingRecordWithAnalysis]


VALID_ABNORMAL_EVENT_TYPES = {"vomiting", "diarrhea", "constipation", "allergy", "fever", "low_appetite", "bloating", "skin_rash", "other"}
ABNORMAL_EVENT_TYPE_NAMES = {
    "vomiting": "呕吐",
    "diarrhea": "腹泻",
    "constipation": "便秘",
    "allergy": "过敏",
    "fever": "发热",
    "low_appetite": "食欲差",
    "bloating": "腹胀",
    "skin_rash": "皮疹",
    "other": "其他",
}
VALID_SEVERITY_LEVELS = {"mild", "moderate", "severe", "critical"}
SEVERITY_LEVEL_NAMES = {
    "mild": "轻度",
    "moderate": "中度",
    "severe": "重度",
    "critical": "危重",
}
VALID_EVENT_STATUSES = {"open", "investigating", "handling", "observing", "closed", "reopened"}
EVENT_STATUS_NAMES = {
    "open": "待处理",
    "investigating": "调查中",
    "handling": "处置中",
    "observing": "观察中",
    "closed": "已关闭",
    "reopened": "重新开启",
}
VALID_HANDLING_TYPES = {"onsite", "doctor", "medication", "diet_adjust", "observation", "batch_change", "transition_pause", "other"}
HANDLING_TYPE_NAMES = {
    "onsite": "现场处理",
    "doctor": "医生处置",
    "medication": "用药",
    "diet_adjust": "饮食调整",
    "observation": "观察跟进",
    "batch_change": "更换批次",
    "transition_pause": "暂停转段",
    "other": "其他",
}
RISK_LEVEL_NAMES = {
    "low": "低风险",
    "medium": "中风险",
    "high": "高风险",
    "critical": "危重风险",
}


class AbnormalEventCreate(BaseModel):
    baby_id: int = Field(..., description="宝宝档案ID")
    event_type: str = Field(..., description="事件类型: vomiting/diarrhea/constipation/allergy/fever/low_appetite/bloating/skin_rash/other")
    event_time: datetime = Field(..., description="事件发生时间")
    batch_id: Optional[int] = Field(None, description="关联奶粉批次ID")
    brewing_record_id: Optional[int] = Field(None, description="关联冲泡记录ID")
    daily_milk_intake_ml: Optional[float] = Field(None, gt=0, description="当日奶量(ml)")
    digestion_status: Optional[str] = Field(None, description="消化状态")
    body_temperature: Optional[float] = Field(None, description="体温(摄氏度)")
    weight_kg: Optional[float] = Field(None, gt=0, description="体重(kg)")
    symptom_description: str = Field(..., min_length=1, max_length=2000, description="症状描述")
    severity_level: str = Field(..., description="严重程度: mild/moderate/severe/critical")
    on_site_measures: Optional[str] = Field(None, max_length=1000, description="现场处理措施")

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        if v not in VALID_ABNORMAL_EVENT_TYPES:
            raise ValueError(f"无效的事件类型: {v}，有效值为: {', '.join(sorted(VALID_ABNORMAL_EVENT_TYPES))}")
        return v

    @field_validator("severity_level")
    @classmethod
    def validate_severity(cls, v: str) -> str:
        if v not in VALID_SEVERITY_LEVELS:
            raise ValueError(f"无效的严重程度: {v}，有效值为: {', '.join(sorted(VALID_SEVERITY_LEVELS))}")
        return v

    @field_validator("event_time")
    @classmethod
    def event_time_not_future(cls, v: datetime) -> datetime:
        if v > datetime.now():
            raise ValueError("事件发生时间不能是未来时间")
        return v

    @field_validator("digestion_status")
    @classmethod
    def validate_digestion(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_DIGESTION_STATUSES:
            raise ValueError(f"无效的消化状态: {v}，有效值为: {', '.join(sorted(VALID_DIGESTION_STATUSES))}")
        return v


class AbnormalEventStatusUpdate(BaseModel):
    status: str = Field(..., description="事件状态: open/investigating/handling/observing/closed/reopened")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_EVENT_STATUSES:
            raise ValueError(f"无效的事件状态: {v}，有效值为: {', '.join(sorted(VALID_EVENT_STATUSES))}")
        return v


class EventHandlingRecordCreate(BaseModel):
    event_id: int = Field(..., description="异常事件ID")
    handler_name: Optional[str] = Field(None, max_length=50, description="处置人员")
    handling_time: Optional[datetime] = Field(None, description="处置时间")
    handling_type: str = Field(..., description="处置类型: onsite/doctor/medication/diet_adjust/observation/batch_change/transition_pause/other")
    handling_description: str = Field(..., min_length=1, max_length=2000, description="处置描述")
    follow_up_plan: Optional[str] = Field(None, max_length=1000, description="后续跟进计划")
    status_after: Optional[str] = Field(None, description="处置后状态")

    @field_validator("handling_type")
    @classmethod
    def validate_handling_type(cls, v: str) -> str:
        if v not in VALID_HANDLING_TYPES:
            raise ValueError(f"无效的处置类型: {v}，有效值为: {', '.join(sorted(VALID_HANDLING_TYPES))}")
        return v

    @field_validator("status_after")
    @classmethod
    def validate_status_after(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_EVENT_STATUSES:
            raise ValueError(f"无效的处置后状态: {v}，有效值为: {', '.join(sorted(VALID_EVENT_STATUSES))}")
        return v


class EventHandlingRecordOut(BaseModel):
    id: int
    event_id: int
    handler_name: Optional[str]
    handling_time: Optional[datetime]
    handling_type: str
    handling_description: str
    follow_up_plan: Optional[str]
    status_after: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class AbnormalEventAutoAnalysis(BaseModel):
    risk_level: Optional[str] = None
    suspected_causes: Optional[List[str]] = None
    brewing_abnormal_related: Optional[bool] = None
    batch_risk_related: Optional[bool] = None
    suggest_pause_batch: Optional[bool] = None
    suggest_stop_transition: Optional[bool] = None
    suggest_doctor_consultation: Optional[bool] = None
    observation_suggestions: Optional[List[str]] = None


class AbnormalEventOut(BaseModel):
    id: int
    baby_id: int
    event_type: str
    event_time: datetime
    batch_id: Optional[int]
    brewing_record_id: Optional[int]
    daily_milk_intake_ml: Optional[float]
    digestion_status: Optional[str]
    body_temperature: Optional[float]
    weight_kg: Optional[float]
    symptom_description: str
    severity_level: str
    on_site_measures: Optional[str]
    status: str
    auto_analysis: Optional[AbnormalEventAutoAnalysis] = None
    closed_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AbnormalEventWithDetails(AbnormalEventOut):
    handling_records: Optional[List[EventHandlingRecordOut]] = None
    batch_info: Optional[Dict] = None
    brewing_record_info: Optional[Dict] = None
    baby_info: Optional[Dict] = None


class AbnormalEventReplayRequest(BaseModel):
    baby_id: int = Field(..., description="宝宝档案ID")
    start_date: date = Field(..., description="开始日期")
    end_date: date = Field(..., description="结束日期")

    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, v: date, info) -> date:
        start = info.data.get("start_date")
        if start is not None and v < start:
            raise ValueError("结束日期不能早于开始日期")
        return v


class AbnormalEventReplaySummary(BaseModel):
    baby_id: int
    baby_name: str
    start_date: date
    end_date: date
    total_event_count: int
    type_distribution: List[Dict]
    high_risk_count: int
    closed_event_count: int
    handling_completion_rate: float
    related_batch_ranking: List[Dict]
    digestion_abnormal_count: int
    transition_related_count: int
    recurrence_risk_level: str
    recurrence_risk_score: float
    recurrence_risk_factors: List[str]
    overall_suggestion: str


VALID_FAMILY_MEMBER_ROLES = {"viewer", "manager"}
FAMILY_MEMBER_ROLE_NAMES = {
    "viewer": "查看者",
    "manager": "管理者",
}


class FamilyMemberCreate(BaseModel):
    baby_id: int = Field(..., description="宝宝档案ID")
    member_name: str = Field(..., min_length=1, max_length=50, description="成员姓名")
    relation: str = Field(..., min_length=1, max_length=30, description="与宝宝关系")
    phone: Optional[str] = Field(None, max_length=20, description="联系电话")
    role: Optional[str] = Field("viewer", description="角色: viewer/manager")

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Optional[str]) -> str:
        if v is None:
            return "viewer"
        if v not in VALID_FAMILY_MEMBER_ROLES:
            raise ValueError(f"无效的角色: {v}，有效值为: {', '.join(sorted(VALID_FAMILY_MEMBER_ROLES))}")
        return v


class FamilyMemberUpdate(BaseModel):
    member_name: Optional[str] = Field(None, min_length=1, max_length=50)
    relation: Optional[str] = Field(None, min_length=1, max_length=30)
    phone: Optional[str] = Field(None, max_length=20)
    role: Optional[str] = Field(None, description="角色: viewer/manager")
    is_active: Optional[bool] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_FAMILY_MEMBER_ROLES:
            raise ValueError(f"无效的角色: {v}，有效值为: {', '.join(sorted(VALID_FAMILY_MEMBER_ROLES))}")
        return v


class FamilyMemberOut(BaseModel):
    id: int
    baby_id: int
    member_name: str
    relation: str
    phone: Optional[str]
    role: str
    role_name: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def model_validate(cls, obj, **kwargs):
        instance = super().model_validate(obj, **kwargs)
        instance.role_name = FAMILY_MEMBER_ROLE_NAMES.get(instance.role, instance.role)
        return instance


VALID_REPORT_TYPES = {"weekly", "monthly"}
REPORT_TYPE_NAMES = {
    "weekly": "周报",
    "monthly": "月报",
}
VALID_REPORT_STATUSES = {"pending", "generating", "completed", "failed"}
REPORT_STATUS_NAMES = {
    "pending": "待生成",
    "generating": "生成中",
    "completed": "已完成",
    "failed": "生成失败",
}


class FeedingReportGenerateRequest(BaseModel):
    baby_id: int = Field(..., description="宝宝档案ID")
    report_type: str = Field(..., description="报告类型: weekly/monthly")
    period_start: Optional[date] = Field(None, description="周期开始日期，默认自动计算")
    period_end: Optional[date] = Field(None, description="周期结束日期，默认自动计算")

    @field_validator("report_type")
    @classmethod
    def validate_report_type(cls, v: str) -> str:
        if v not in VALID_REPORT_TYPES:
            raise ValueError(f"无效的报告类型: {v}，有效值为: {', '.join(sorted(VALID_REPORT_TYPES))}")
        return v


class FeedingReportStatusUpdate(BaseModel):
    status: str = Field(..., description="报告状态: pending/generating/completed/failed")

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: str) -> str:
        if v not in VALID_REPORT_STATUSES:
            raise ValueError(f"无效的报告状态: {v}，有效值为: {', '.join(sorted(VALID_REPORT_STATUSES))}")
        return v


class FeedingReportOut(BaseModel):
    id: int
    baby_id: int
    baby_name: Optional[str] = None
    report_type: str
    report_type_name: Optional[str] = None
    period_start: date
    period_end: date
    status: str
    status_name: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    total_milk_ml: float
    avg_daily_milk_ml: float
    weight_change_kg: float
    digestion_abnormal_count: int
    brewing_abnormal_count: int
    batch_risk_count: int
    transition_progress: float
    doctor_consultation_count: int
    abnormal_event_completion_rate: float
    overall_score: float
    generated_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def model_validate(cls, obj, **kwargs):
        instance = super().model_validate(obj, **kwargs)
        instance.report_type_name = REPORT_TYPE_NAMES.get(instance.report_type, instance.report_type)
        instance.status_name = REPORT_STATUS_NAMES.get(instance.status, instance.status)
        if hasattr(obj, "baby") and obj.baby:
            instance.baby_name = obj.baby.baby_name
        return instance


class FeedingReportDetail(FeedingReportOut):
    report_data: Optional[Dict] = None

    @classmethod
    def model_validate(cls, obj, **kwargs):
        import json
        if isinstance(obj, object) and hasattr(obj, "report_data") and isinstance(obj.report_data, str):
            try:
                obj.report_data = json.loads(obj.report_data)
            except (json.JSONDecodeError, TypeError):
                obj.report_data = None
        return super().model_validate(obj, **kwargs)


class ReportShareCreate(BaseModel):
    report_id: int = Field(..., description="报告ID")
    shared_by: Optional[str] = Field(None, max_length=50, description="分享人")
    expires_days: Optional[int] = Field(7, ge=1, le=30, description="有效期天数")


class ReportShareOut(BaseModel):
    id: int
    report_id: int
    share_code: str
    shared_by: Optional[str]
    view_count: int
    expires_at: Optional[datetime]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SharedReportSummary(BaseModel):
    report_id: int
    baby_name: str
    report_type: str
    report_type_name: str
    period_start: date
    period_end: date
    title: Optional[str] = None
    summary: Optional[str] = None
    total_milk_ml: float
    avg_daily_milk_ml: float
    weight_change_kg: float
    digestion_abnormal_count: int
    brewing_abnormal_count: int
    batch_risk_count: int
    transition_progress: float
    doctor_consultation_count: int
    abnormal_event_completion_rate: float
    overall_score: float
    generated_at: Optional[datetime] = None
    shared_by: Optional[str] = None
