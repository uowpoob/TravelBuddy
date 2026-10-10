"""轻量审核只保留展示和保存所需的基础数据检查。"""

from dataclasses import dataclass, field

from backend.app.schemas.itinerary import Itinerary
from backend.app.schemas.place import Candidates
from backend.app.schemas.review import ReviewResult
from backend.app.schemas.trip import TripRequest


@dataclass
class ItineraryRuleCheck:
    issues: list[str] = field(default_factory=list)


def check_itinerary_rules(
    request: TripRequest,
    itinerary: Itinerary | None,
    candidates: Candidates,
) -> ItineraryRuleCheck:
    """只检查空方案、日序和地点引用；不评价行程安排。"""
    checks = ItineraryRuleCheck()
    if itinerary is None or not itinerary.days:
        checks.issues.append("尚未生成具体行程，需要补齐方案。")
        return checks
    if request.days is not None and [day.day for day in itinerary.days] != list(
        range(1, request.days + 1)
    ):
        checks.issues.append(f"行程需按第 1 到第 {request.days} 天连续排列，不重复天数。")
    visits = [visit for day in itinerary.days for visit in day.visits]
    if not visits:
        checks.issues.append("行程没有任何活动，需要至少安排一个具体地点。")
    places = {
        place.id: place
        for place in candidates.attractions + candidates.restaurants + candidates.hotels
    }
    for day in itinerary.days:
        for index, visit in enumerate(day.visits, start=1):
            place = places.get(visit.place_id)
            if not visit.place_id.strip() or place is None or not place.name.strip():
                checks.issues.append(
                    f"第 {day.day} 天第 {index} 站地点不可用，需替换为已有的具名候选地点。"
                )
    checks.issues = list(dict.fromkeys(checks.issues))
    return checks


def enforce_rule_review(
    review: ReviewResult, checks: ItineraryRuleCheck
) -> ReviewResult:
    """保留模型的三种判断，只阻止基础数据错误被 pass 覆盖。"""
    model_issues = list(
        dict.fromkeys(issue.strip() for issue in review.issues if issue.strip())
    )
    decision = review.decision
    if checks.issues and decision == "pass":
        decision = "revise"
    return ReviewResult(
        decision=decision,
        issues=list(dict.fromkeys(checks.issues + model_issues)),
        clarification_question=(
            (review.clarification_question or "").strip() or None
            if decision == "needs_user"
            else None
        ),
    )
