from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
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
