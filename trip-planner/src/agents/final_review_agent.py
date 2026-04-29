from src.state.schemas import TripPlannerState
from src.services.llm_service import SarvamLLMService


from typing import Optional


def run(state: TripPlannerState, llm_service: Optional[SarvamLLMService] = None) -> TripPlannerState:
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

    reasoning = "Approved: all required components present and budget constraints satisfied." if approved else f"Rejected due to: {reasons}"

    if llm_service is not None and getattr(llm_service, "enabled", False):
        try:
            llm_reason = llm_service.chat_text(
                system="You are a strict itinerary reviewer. Explain approval/rejection in 1-2 sentences.",
                user=f"Budget summary: {state.budget_summary}\nItinerary: {state.itinerary}\nWeather: {state.weather_data}\nHotels: {state.hotel_data}\nTransport: {state.transport_data}",
                timeout=10,
            ).strip()
            if llm_reason:
                reasoning = llm_reason
        except Exception:
            pass

    state.agent_reasoning["final_review_agent"] = reasoning
    return state
