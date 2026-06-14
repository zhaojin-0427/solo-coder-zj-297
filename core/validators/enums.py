from typing import Tuple, Optional

VALID_DIGESTION_STATUSES = {"normal", "mild_discomfort", "constipation", "diarrhea", "allergy", "vomiting"}
VALID_CONSULTATION_TYPES = {"digestion", "growth", "nutrition", "transition", "other"}
VALID_STORAGE_METHODS = {"refrigerated", "cool_dry", "room_temperature"}
VALID_REMAINING_HANDLING = {"discarded", "stored", "used_later", "other"}
VALID_ABNORMAL_EVENT_TYPES = {"vomiting", "diarrhea", "constipation", "allergy", "fever", "low_appetite", "bloating", "skin_rash", "other"}
VALID_SEVERITY_LEVELS = {"mild", "moderate", "severe", "critical"}
VALID_EVENT_STATUSES = {"open", "investigating", "handling", "observing", "closed", "reopened"}
VALID_HANDLING_TYPES = {"onsite", "doctor", "medication", "diet_adjust", "observation", "batch_change", "transition_pause", "other"}
VALID_FAMILY_MEMBER_ROLES = {"viewer", "manager"}
VALID_REPORT_TYPES = {"weekly", "monthly"}
VALID_REPORT_STATUSES = {"pending", "generating", "completed", "failed"}
VALID_TRANSITION_PLAN_STATUSES = {"draft", "in_progress", "paused", "completed", "cancelled"}


def _validate_enum(value: str, valid_values: set, field_name: str) -> Tuple[bool, Optional[str]]:
    if value not in valid_values:
        return False, f"无效的{field_name}: {value}，有效值为: {', '.join(sorted(valid_values))}"
    return True, None


def validate_digestion_status(status: str) -> Tuple[bool, Optional[str]]:
    return _validate_enum(status, VALID_DIGESTION_STATUSES, "消化状态")


def validate_storage_method(method: str) -> Tuple[bool, Optional[str]]:
    return _validate_enum(method, VALID_STORAGE_METHODS, "储存方式")


def validate_remaining_handling(handling: str) -> Tuple[bool, Optional[str]]:
    return _validate_enum(handling, VALID_REMAINING_HANDLING, "剩余处理方式")


def validate_abnormal_event_type(event_type: str) -> Tuple[bool, Optional[str]]:
    return _validate_enum(event_type, VALID_ABNORMAL_EVENT_TYPES, "事件类型")


def validate_severity_level(level: str) -> Tuple[bool, Optional[str]]:
    return _validate_enum(level, VALID_SEVERITY_LEVELS, "严重程度")


def validate_event_status(status: str) -> Tuple[bool, Optional[str]]:
    return _validate_enum(status, VALID_EVENT_STATUSES, "事件状态")


def validate_handling_type(handling_type: str) -> Tuple[bool, Optional[str]]:
    return _validate_enum(handling_type, VALID_HANDLING_TYPES, "处置类型")


def validate_family_role(role: str) -> Tuple[bool, Optional[str]]:
    return _validate_enum(role, VALID_FAMILY_MEMBER_ROLES, "角色")


def validate_report_type(report_type: str) -> Tuple[bool, Optional[str]]:
    return _validate_enum(report_type, VALID_REPORT_TYPES, "报告类型")


def validate_report_status(status: str) -> Tuple[bool, Optional[str]]:
    return _validate_enum(status, VALID_REPORT_STATUSES, "报告状态")


def validate_transition_plan_status(status: str) -> Tuple[bool, Optional[str]]:
    return _validate_enum(status, VALID_TRANSITION_PLAN_STATUSES, "计划状态")


def validate_consultation_type(consultation_type: str) -> Tuple[bool, Optional[str]]:
    return _validate_enum(consultation_type, VALID_CONSULTATION_TYPES, "咨询类型")
