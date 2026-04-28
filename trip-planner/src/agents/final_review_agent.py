from src.state.schemas import TripPlannerState


def run(state: TripPlannerState) -> TripPlannerState:
    reasons = []
    within_budget = state.budget_summary.get("within_budget", True)
    if not within_budget:
        reasons.append("Estimated cost exceeds budget")

    # check itinerary conflicts (mock: ensure at least one day)
    if not state.itinerary.get("days"):
        reasons.append("Itinerary is empty")

    approved = len(reasons) == 0
    state.review_status.approved = approved
    state.review_status.reasons = reasons
    return state
