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
