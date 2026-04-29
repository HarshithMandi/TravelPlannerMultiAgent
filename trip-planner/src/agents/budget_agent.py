from src.state.schemas import TripPlannerState
from src.services.llm_service import SarvamLLMService


from typing import Optional


def run(state: TripPlannerState, llm_service: Optional[SarvamLLMService] = None) -> TripPlannerState:
    # Very simple budget estimation: sum hotel+transport rough estimates
    hotel_est = 0
    hotel_candidates = []
    if state.hotel_data:
        hotel_candidates = state.hotel_data.get("suggestions") or state.hotel_data.get("hotels") or []

    if hotel_candidates:
        first_hotel = hotel_candidates[0]
        nightly_rate = first_hotel.get("price_per_night")
        if nightly_rate is None:
            hotel_type = str(first_hotel.get("type", "")).lower()
            if hotel_type in {"hostel"}:
                nightly_rate = 1500
            elif hotel_type in {"guest_house", "guest house"}:
                nightly_rate = 2500
            elif hotel_type in {"hotel", "fallback"}:
                nightly_rate = 4000
            else:
                nightly_rate = 3500
        hotel_est = float(nightly_rate) * 3

    transport_est = 8000
    total_est = hotel_est + transport_est
    budget_limit = float(state.trip_preferences.get("budget", 0) or 0)
    within = total_est <= budget_limit
    state.budget_summary = {"estimated_total": total_est, "within_budget": within}

    reasoning = (
        f"Estimated total ~{total_est:.0f} (hotel ~{hotel_est:.0f} + transport ~{transport_est:.0f}) "
        f"vs budget {budget_limit:.0f} => within_budget={within}."
    )

    if llm_service is not None and getattr(llm_service, "enabled", False):
        try:
            llm_reason = llm_service.chat_text(
                system="You are a travel budget optimizer. Provide a short budget rationale and 1 suggestion.",
                user=f"Prefs: {state.trip_preferences}\nHotel data: {state.hotel_data}\nTransport data: {state.transport_data}\nComputed: {state.budget_summary}",
                timeout=10,
            ).strip()
            if llm_reason:
                reasoning = llm_reason
        except Exception:
            pass

    state.agent_reasoning["budget_agent"] = reasoning
    return state
