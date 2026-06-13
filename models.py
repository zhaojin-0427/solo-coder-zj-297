from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean, Date
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class BabyProfile(Base):
    __tablename__ = "baby_profiles"

    id = Column(Integer, primary_key=True, index=True)
    baby_name = Column(String(50), nullable=False)
    gender = Column(String(10), nullable=False)
    birth_date = Column(DateTime, nullable=False)
    current_stage = Column(Integer, default=1)
    guardian_name = Column(String(50))
    guardian_phone = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    records = relationship("HealthRecord", back_populates="baby", cascade="all, delete-orphan")
    consultations = relationship("DoctorConsultation", back_populates="baby", cascade="all, delete-orphan")


class HealthRecord(Base):
    __tablename__ = "health_records"

    id = Column(Integer, primary_key=True, index=True)
    baby_id = Column(Integer, ForeignKey("baby_profiles.id"), nullable=False)
    month_age = Column(Integer, nullable=False)
    current_stage = Column(Integer, nullable=False)
    daily_intake_ml = Column(Float, nullable=False)
    digestion_status = Column(String(30), nullable=False)
    digestion_note = Column(Text)
    weight_kg = Column(Float, nullable=False)
    height_cm = Column(Float)
    record_date = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    baby = relationship("BabyProfile", back_populates="records")


class DoctorConsultation(Base):
    __tablename__ = "doctor_consultations"

    id = Column(Integer, primary_key=True, index=True)
    baby_id = Column(Integer, ForeignKey("baby_profiles.id"), nullable=False)
    consultation_type = Column(String(50), nullable=False)
    symptoms = Column(Text, nullable=False)
    suggestion = Column(Text)
    status = Column(String(20), default="pending")
    scheduled_time = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    baby = relationship("BabyProfile", back_populates="consultations")


VALID_TRANSITION_PLAN_STATUSES = {"draft", "in_progress", "paused", "completed", "cancelled"}


class TransitionPlan(Base):
    __tablename__ = "transition_plans"

    id = Column(Integer, primary_key=True, index=True)
    baby_id = Column(Integer, ForeignKey("baby_profiles.id"), nullable=False)
    plan_name = Column(String(100), nullable=False)
    original_stage = Column(Integer, nullable=False)
    target_stage = Column(Integer, nullable=False)
    start_date = Column(DateTime, nullable=False)
    transition_days = Column(Integer, nullable=False)
    daily_ratio_schedule = Column(Text, nullable=False)
    observation_focus = Column(Text)
    status = Column(String(20), default="draft", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    baby = relationship("BabyProfile")
    records = relationship("TransitionRecord", back_populates="plan", cascade="all, delete-orphan")


class TransitionRecord(Base):
    __tablename__ = "transition_records"

    id = Column(Integer, primary_key=True, index=True)
    plan_id = Column(Integer, ForeignKey("transition_plans.id"), nullable=False)
    record_date = Column(DateTime, nullable=False)
    old_formula_ratio = Column(Integer, nullable=False)
    new_formula_ratio = Column(Integer, nullable=False)
    milk_intake_ml = Column(Float, nullable=False)
    digestion_status = Column(String(30), nullable=False)
    weight_kg = Column(Float)
    note = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    plan = relationship("TransitionPlan", back_populates="records")


VALID_STORAGE_METHODS = {"refrigerated", "cool_dry", "room_temperature"}
VALID_REMAINING_HANDLING = {"discarded", "stored", "used_later", "other"}


class FormulaBatch(Base):
    __tablename__ = "formula_batches"

    id = Column(Integer, primary_key=True, index=True)
    baby_id = Column(Integer, ForeignKey("baby_profiles.id"), nullable=False)
    brand_name = Column(String(100), nullable=False)
    product_name = Column(String(100), nullable=False)
    stage = Column(Integer, nullable=False)
    batch_number = Column(String(100), nullable=False)
    opening_date = Column(Date, nullable=False)
    expiry_date = Column(Date, nullable=False)
    can_capacity_grams = Column(Float, nullable=False)
    current_remaining_grams = Column(Float, nullable=False)
    storage_method = Column(String(30), nullable=False)
    notes = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    baby = relationship("BabyProfile")
    brewing_records = relationship("BrewingRecord", back_populates="batch", cascade="all, delete-orphan")


class BrewingRecord(Base):
    __tablename__ = "brewing_records"

    id = Column(Integer, primary_key=True, index=True)
    baby_id = Column(Integer, ForeignKey("baby_profiles.id"), nullable=False)
    batch_id = Column(Integer, ForeignKey("formula_batches.id"), nullable=False)
    brewing_time = Column(DateTime, nullable=False)
    water_temperature = Column(Float, nullable=False)
    formula_scoops = Column(Float, nullable=False)
    water_volume_ml = Column(Float, nullable=False)
    actual_consumed_ml = Column(Float, nullable=False)
    has_remaining = Column(Boolean, default=False)
    remaining_handling = Column(String(30))
    abnormal_notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    baby = relationship("BabyProfile")
    batch = relationship("FormulaBatch", back_populates="brewing_records")


VALID_ABNORMAL_EVENT_TYPES = {"vomiting", "diarrhea", "constipation", "allergy", "fever", "low_appetite", "bloating", "skin_rash", "other"}
VALID_SEVERITY_LEVELS = {"mild", "moderate", "severe", "critical"}
VALID_EVENT_STATUSES = {"open", "investigating", "handling", "observing", "closed", "reopened"}


class AbnormalEvent(Base):
    __tablename__ = "abnormal_events"

    id = Column(Integer, primary_key=True, index=True)
    baby_id = Column(Integer, ForeignKey("baby_profiles.id"), nullable=False)
    event_type = Column(String(30), nullable=False)
    event_time = Column(DateTime, nullable=False)
    batch_id = Column(Integer, ForeignKey("formula_batches.id"), nullable=True)
    brewing_record_id = Column(Integer, ForeignKey("brewing_records.id"), nullable=True)
    daily_milk_intake_ml = Column(Float)
    digestion_status = Column(String(30))
    body_temperature = Column(Float)
    weight_kg = Column(Float)
    symptom_description = Column(Text, nullable=False)
    severity_level = Column(String(20), nullable=False)
    on_site_measures = Column(Text)
    status = Column(String(20), default="open", nullable=False)
    auto_risk_level = Column(String(20))
    auto_suspected_causes = Column(Text)
    auto_brewing_abnormal_related = Column(Boolean, default=False)
    auto_batch_risk_related = Column(Boolean, default=False)
    auto_suggest_pause_batch = Column(Boolean, default=False)
    auto_suggest_stop_transition = Column(Boolean, default=False)
    auto_suggest_doctor_consultation = Column(Boolean, default=False)
    auto_observation_suggestions = Column(Text)
    closed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    baby = relationship("BabyProfile")
    batch = relationship("FormulaBatch")
    brewing_record = relationship("BrewingRecord")
    handling_records = relationship("EventHandlingRecord", back_populates="event", cascade="all, delete-orphan")


class EventHandlingRecord(Base):
    __tablename__ = "event_handling_records"

    id = Column(Integer, primary_key=True, index=True)
    event_id = Column(Integer, ForeignKey("abnormal_events.id"), nullable=False)
    handler_name = Column(String(50))
    handling_time = Column(DateTime, default=datetime.utcnow)
    handling_type = Column(String(30), nullable=False)
    handling_description = Column(Text, nullable=False)
    follow_up_plan = Column(Text)
    status_after = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)

    event = relationship("AbnormalEvent", back_populates="handling_records")
