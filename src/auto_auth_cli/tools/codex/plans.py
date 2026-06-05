AUTO_PLAN_PRIORITY = [
    "free",
    "go",
    "plus",
    "prolite",
    "pro",
    "team",
    "self_serve_business_usage_based",
    "business",
    "enterprise_cbp_usage_based",
    "enterprise",
    "edu",
]


def plan_priority(plan_type: str | None) -> int:
    if plan_type is None:
        return len(AUTO_PLAN_PRIORITY)
    normalized = plan_type.strip().lower()
    try:
        return AUTO_PLAN_PRIORITY.index(normalized)
    except ValueError:
        return len(AUTO_PLAN_PRIORITY)
