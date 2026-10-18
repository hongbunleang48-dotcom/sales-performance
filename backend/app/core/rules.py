from enum import Enum
from typing import Dict, Any, Union, Tuple


class AchievementStatus(str, Enum):
    ACHIEVED = "Achieved"
    ON_TRACK = "On Track"
    UNDERPERFORMING = "Underperforming"


class PerformanceGrade(str, Enum):
    TIER_1 = "Tier 1 (High)"
    TIER_2 = "Tier 2 (Medium)"
    TIER_3 = "Tier 3 (Low)"


class ActionStatus(str, Enum):
    TOP_INCENTIVE = "Top Incentive"
    STANDARD_BONUS = "Standard Bonus"
    RETRAINING = "Retraining"
    PIP_WARNING = "PIP Warning"


class CreditHealth(str, Enum):
    HEALTHY = "Healthy"
    OVERDUE_NOTICE = "Overdue Notice"


# UI Color mapping definitions as per Project CORE guidelines
UI_COLOR_MAPPINGS: Dict[str, str] = {
    # Emerald (#10B981)
    PerformanceGrade.TIER_1.value: "#10B981",
    AchievementStatus.ACHIEVED.value: "#10B981",
    ActionStatus.TOP_INCENTIVE.value: "#10B981",
    CreditHealth.HEALTHY.value: "#10B981",
    "Compliant": "#10B981",
    # Amber (#F59E0B)
    PerformanceGrade.TIER_2.value: "#F59E0B",
    AchievementStatus.ON_TRACK.value: "#F59E0B",
    ActionStatus.STANDARD_BONUS.value: "#F59E0B",
    ActionStatus.RETRAINING.value: "#F59E0B",
    "Fair": "#F59E0B",
    # Rose (#EF4444)
    PerformanceGrade.TIER_3.value: "#EF4444",
    AchievementStatus.UNDERPERFORMING.value: "#EF4444",
    ActionStatus.PIP_WARNING.value: "#EF4444",
    CreditHealth.OVERDUE_NOTICE.value: "#EF4444",
    "Route Diverted": "#EF4444",
    "Poor": "#EF4444",
}


def calculate_achievement_and_tier(target_achieved_pct: float) -> Tuple[AchievementStatus, PerformanceGrade]:
    """
    Evaluates achievement status and performance grade based on target percentage:
    - Target >= 100% -> Achieved, Tier 1 (High)
    - 85% <= Target < 100% -> On Track, Tier 2 (Medium)
    - Target < 85% -> Underperforming, Tier 3 (Low)
    """
    if target_achieved_pct >= 100.0:
        return AchievementStatus.ACHIEVED, PerformanceGrade.TIER_1
    elif target_achieved_pct >= 85.0:
        return AchievementStatus.ON_TRACK, PerformanceGrade.TIER_2
    else:
        return AchievementStatus.UNDERPERFORMING, PerformanceGrade.TIER_3


def calculate_action_status(
    target_achieved_pct: float,
    credit_health: Union[CreditHealth, str]
) -> ActionStatus:
    """
    Evaluates action status based on target achieved percentage and credit health:
    - PIP Warning if credit_health == "Overdue Notice" or target < 85%.
    - Top Incentive if target >= 100% and credit_health == "Healthy".
    - Standard Bonus if target >= 90% and credit_health == "Healthy".
    - Otherwise Retraining.
    """
    credit_val = credit_health.value if isinstance(credit_health, Enum) else str(credit_health).strip()

    if credit_val == CreditHealth.OVERDUE_NOTICE.value or target_achieved_pct < 85.0:
        return ActionStatus.PIP_WARNING
    elif target_achieved_pct >= 100.0 and credit_val == CreditHealth.HEALTHY.value:
        return ActionStatus.TOP_INCENTIVE
    elif target_achieved_pct >= 90.0 and credit_val == CreditHealth.HEALTHY.value:
        return ActionStatus.STANDARD_BONUS
    else:
        return ActionStatus.RETRAINING


def evaluate_salesman_performance(
    target_achieved_pct: float,
    credit_health: Union[CreditHealth, str]
) -> Dict[str, str]:
    """
    Complete decision engine function evaluating target achievement and credit health.
    
    Returns:
        {
            "achievement_status": str,
            "performance_grade": str,
            "action_status": str
        }
    """
    achievement_status, performance_grade = calculate_achievement_and_tier(target_achieved_pct)
    action_status = calculate_action_status(target_achieved_pct, credit_health)

    return {
        "achievement_status": achievement_status.value,
        "performance_grade": performance_grade.value,
        "action_status": action_status.value,
    }


# Aliases for flexibility across service and API layers
evaluate_rules = evaluate_salesman_performance
calculate_performance = evaluate_salesman_performance
