from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from typing import List
from datetime import datetime
from database import get_db
from models import BabyProfile, FamilyMember
from schemas import (
    FamilyMemberCreate, FamilyMemberUpdate, FamilyMemberOut, ApiResponse,
)

router = APIRouter(prefix="/api/family", tags=["家庭成员管理"])


@router.post("", response_model=ApiResponse)
def add_family_member(data: FamilyMemberCreate, db: Session = Depends(get_db)):
    baby = db.query(BabyProfile).filter(BabyProfile.id == data.baby_id).first()
    if not baby:
        return ApiResponse(code=404, message="宝宝档案不存在", data=None)

    member = FamilyMember(
        baby_id=data.baby_id,
        member_name=data.member_name,
        relation=data.relation,
        phone=data.phone,
        role=data.role or "viewer",
        is_active=True,
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return ApiResponse(
        code=200,
        message="家庭成员添加成功",
        data={"member": FamilyMemberOut.model_validate(member).model_dump()},
    )


@router.get("/baby/{baby_id}", response_model=ApiResponse)
def list_family_members(baby_id: int, db: Session = Depends(get_db)):
    baby = db.query(BabyProfile).filter(BabyProfile.id == baby_id).first()
    if not baby:
        return ApiResponse(code=404, message="宝宝档案不存在", data=None)

    members = db.query(FamilyMember).filter(
        FamilyMember.baby_id == baby_id
    ).order_by(FamilyMember.created_at.desc()).all()
    data = [FamilyMemberOut.model_validate(m).model_dump() for m in members]
    return ApiResponse(code=200, message="查询成功", data={"list": data, "total": len(data)})


@router.get("/{member_id}", response_model=ApiResponse)
def get_family_member(member_id: int, db: Session = Depends(get_db)):
    member = db.query(FamilyMember).filter(FamilyMember.id == member_id).first()
    if not member:
        return ApiResponse(code=404, message="家庭成员不存在", data=None)
    return ApiResponse(
        code=200,
        message="查询成功",
        data={"member": FamilyMemberOut.model_validate(member).model_dump()},
    )


@router.put("/{member_id}", response_model=ApiResponse)
def update_family_member(member_id: int, data: FamilyMemberUpdate, db: Session = Depends(get_db)):
    member = db.query(FamilyMember).filter(FamilyMember.id == member_id).first()
    if not member:
        return ApiResponse(code=404, message="家庭成员不存在", data=None)

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        if value is not None:
            setattr(member, key, value)
    member.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(member)
    return ApiResponse(
        code=200,
        message="更新成功",
        data={"member": FamilyMemberOut.model_validate(member).model_dump()},
    )


@router.delete("/{member_id}", response_model=ApiResponse)
def delete_family_member(member_id: int, db: Session = Depends(get_db)):
    member = db.query(FamilyMember).filter(FamilyMember.id == member_id).first()
    if not member:
        return ApiResponse(code=404, message="家庭成员不存在", data=None)
    db.delete(member)
    db.commit()
    return ApiResponse(code=200, message="删除成功", data=None)


@router.post("/{member_id}/deactivate", response_model=ApiResponse)
def deactivate_family_member(member_id: int, db: Session = Depends(get_db)):
    member = db.query(FamilyMember).filter(FamilyMember.id == member_id).first()
    if not member:
        return ApiResponse(code=404, message="家庭成员不存在", data=None)
    member.is_active = False
    member.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(member)
    return ApiResponse(
        code=200,
        message="已停用该家庭成员权限",
        data={"member": FamilyMemberOut.model_validate(member).model_dump()},
    )


@router.post("/{member_id}/activate", response_model=ApiResponse)
def activate_family_member(member_id: int, db: Session = Depends(get_db)):
    member = db.query(FamilyMember).filter(FamilyMember.id == member_id).first()
    if not member:
        return ApiResponse(code=404, message="家庭成员不存在", data=None)
    member.is_active = True
    member.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(member)
    return ApiResponse(
        code=200,
        message="已启用该家庭成员权限",
        data={"member": FamilyMemberOut.model_validate(member).model_dump()},
    )
