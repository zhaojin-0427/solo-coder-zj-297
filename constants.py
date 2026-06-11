from typing import Dict, List, Tuple


STAGE_INFO: Dict[int, Dict] = {
    1: {
        "name": "一段",
        "min_month": 0,
        "max_month": 6,
        "description": "新生儿至6个月宝宝专用配方，贴近母乳，易消化",
        "daily_intake_min": 600,
        "daily_intake_max": 1000,
        "nutrients": {"protein": 1.8, "fat": 3.6, "carb": 7.0, "calcium": 42, "iron": 0.42, "dha": 20},
    },
    2: {
        "name": "二段",
        "min_month": 6,
        "max_month": 12,
        "description": "6-12个月较大婴儿配方，强化铁锌，支持脑部发育",
        "daily_intake_min": 700,
        "daily_intake_max": 1100,
        "nutrients": {"protein": 2.2, "fat": 3.4, "carb": 7.5, "calcium": 50, "iron": 0.6, "dha": 25},
    },
    3: {
        "name": "三段",
        "min_month": 12,
        "max_month": 36,
        "description": "1-3岁幼儿配方，钙铁锌强化，支持骨骼和免疫",
        "daily_intake_min": 500,
        "daily_intake_max": 800,
        "nutrients": {"protein": 2.5, "fat": 3.0, "carb": 8.0, "calcium": 62, "iron": 0.8, "dha": 30},
    },
    4: {
        "name": "四段",
        "min_month": 36,
        "max_month": 72,
        "description": "3-6岁儿童配方，DHA+ARA，促进认知发展",
        "daily_intake_min": 400,
        "daily_intake_max": 600,
        "nutrients": {"protein": 2.8, "fat": 2.8, "carb": 8.5, "calcium": 80, "iron": 1.0, "dha": 40},
    },
}


WEIGHT_REFERENCE: Dict[int, Dict[str, float]] = {
    0: {"boy_min": 2.5, "boy_max": 4.4, "girl_min": 2.4, "girl_max": 4.2},
    1: {"boy_min": 3.4, "boy_max": 5.8, "girl_min": 3.2, "girl_max": 5.5},
    2: {"boy_min": 4.3, "boy_max": 7.1, "girl_min": 4.0, "girl_max": 6.6},
    3: {"boy_min": 5.0, "boy_max": 8.0, "girl_min": 4.7, "girl_max": 7.5},
    4: {"boy_min": 5.6, "boy_max": 8.7, "girl_min": 5.1, "girl_max": 8.1},
    5: {"boy_min": 6.0, "boy_max": 9.3, "girl_min": 5.5, "girl_max": 8.7},
    6: {"boy_min": 6.4, "boy_max": 9.8, "girl_min": 5.8, "girl_max": 9.2},
    7: {"boy_min": 6.7, "boy_max": 10.3, "girl_min": 6.1, "girl_max": 9.6},
    8: {"boy_min": 7.0, "boy_max": 10.7, "girl_min": 6.3, "girl_max": 10.0},
    9: {"boy_min": 7.2, "boy_max": 11.0, "girl_min": 6.5, "girl_max": 10.4},
    10: {"boy_min": 7.4, "boy_max": 11.4, "girl_min": 6.7, "girl_max": 10.7},
    11: {"boy_min": 7.6, "boy_max": 11.7, "girl_min": 6.9, "girl_max": 11.0},
    12: {"boy_min": 7.8, "boy_max": 12.0, "girl_min": 7.0, "girl_max": 11.3},
    15: {"boy_min": 8.3, "boy_max": 12.8, "girl_min": 7.6, "girl_max": 12.1},
    18: {"boy_min": 8.8, "boy_max": 13.7, "girl_min": 8.1, "girl_max": 12.9},
    24: {"boy_min": 9.7, "boy_max": 15.3, "girl_min": 9.0, "girl_max": 14.5},
    30: {"boy_min": 10.5, "boy_max": 16.9, "girl_min": 9.8, "girl_max": 16.2},
    36: {"boy_min": 11.3, "boy_max": 18.3, "girl_min": 10.6, "girl_max": 17.7},
    48: {"boy_min": 12.7, "boy_max": 21.2, "girl_min": 12.0, "girl_max": 20.8},
    60: {"boy_min": 14.1, "boy_max": 24.2, "girl_min": 13.5, "girl_max": 23.9},
    72: {"boy_min": 15.9, "boy_max": 27.1, "girl_min": 15.3, "girl_max": 26.8},
}


DAILY_NUTRIENT_REQUIREMENT: Dict[int, Dict[str, float]] = {
    0: {"protein": 10.0, "fat": 25.0, "carb": 40.0, "calcium": 300, "iron": 0.3, "dha": 100},
    6: {"protein": 15.0, "fat": 30.0, "carb": 70.0, "calcium": 400, "iron": 10, "dha": 150},
    12: {"protein": 25.0, "fat": 35.0, "carb": 120.0, "calcium": 600, "iron": 12, "dha": 200},
    36: {"protein": 35.0, "fat": 40.0, "carb": 180.0, "calcium": 800, "iron": 15, "dha": 250},
}


DIGESTION_STATUS = {"normal": "正常", "mild_discomfort": "轻度不适", "constipation": "便秘", "diarrhea": "腹泻", "allergy": "过敏", "vomiting": "吐奶/呕吐"}


TRANSITION_SUCCESS_BASE = {
    (1, 2): 0.92,
    (2, 3): 0.88,
    (3, 4): 0.85,
}


def get_weight_range(month_age: int, gender: str) -> Tuple[float, float]:
    keys = sorted(WEIGHT_REFERENCE.keys())
    target = month_age
    lower = 0
    upper = keys[-1]
    for k in keys:
        if k <= target:
            lower = k
        if k >= target:
            upper = k
            break
    if lower == upper:
        ref = WEIGHT_REFERENCE[lower]
    else:
        ratio = (target - lower) / (upper - lower)
        ref_lower = WEIGHT_REFERENCE[lower]
        ref_upper = WEIGHT_REFERENCE[upper]
        ref = {}
        for key in ref_lower:
            ref[key] = ref_lower[key] + (ref_upper[key] - ref_lower[key]) * ratio
    if gender == "boy":
        return ref["boy_min"], ref["boy_max"]
    else:
        return ref["girl_min"], ref["girl_max"]


def get_nutrient_requirement(month_age: int) -> Dict[str, float]:
    keys = sorted(DAILY_NUTRIENT_REQUIREMENT.keys())
    if month_age <= keys[0]:
        return DAILY_NUTRIENT_REQUIREMENT[keys[0]].copy()
    if month_age >= keys[-1]:
        return DAILY_NUTRIENT_REQUIREMENT[keys[-1]].copy()
    lower, upper = 0, keys[-1]
    for k in keys:
        if k <= month_age:
            lower = k
        if k >= month_age:
            upper = k
            break
    ratio = (month_age - lower) / (upper - lower) if upper != lower else 0
    req = {}
    for key in DAILY_NUTRIENT_REQUIREMENT[lower]:
        req[key] = DAILY_NUTRIENT_REQUIREMENT[lower][key] + (
            DAILY_NUTRIENT_REQUIREMENT[upper][key] - DAILY_NUTRIENT_REQUIREMENT[lower][key]
        ) * ratio
    return req
