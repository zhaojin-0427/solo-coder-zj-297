from typing import Tuple, Optional

MIN_RATIO = 0
MAX_RATIO = 100


def validate_ratio_range(ratio: int, field_name: str = "比例") -> Tuple[bool, Optional[str]]:
    if ratio < MIN_RATIO or ratio > MAX_RATIO:
        return False, f"{field_name}必须在 {MIN_RATIO}-{MAX_RATIO} 之间"
    return True, None


def validate_ratio_sum_100(old_ratio: int, new_ratio: int) -> Tuple[bool, Optional[str]]:
    valid_old, msg_old = validate_ratio_range(old_ratio, "旧奶粉比例")
    if not valid_old:
        return False, msg_old
    valid_new, msg_new = validate_ratio_range(new_ratio, "新奶粉比例")
    if not valid_new:
        return False, msg_new
    if old_ratio + new_ratio != 100:
        return False, f"新旧比例之和必须等于100，当前为 {old_ratio} + {new_ratio} = {old_ratio + new_ratio}"
    return True, None
