from typing import Optional

from src.state.schemas import TripPlannerState
from src.services.hotel_service import HotelService
from src.services.llm_service import SarvamLLMService


def run(
    state: TripPlannerState,
    hotel_service: Optional[HotelService] = None,
    llm_service: Optional[SarvamLLMService] = None,
) -> TripPlannerState:
    hotel_service = hotel_service or HotelService()
    prefs = state.trip_preferences
    budget = prefs.get("budget", 0)
    style = prefs.get("luxury", "budget")
    destination = prefs.get("destination", "")
    preference = prefs.get("hotel_pref", "")

    if not destination:
        state.hotel_data = {"source": "fallback", "hotels": []}
        state.agent_reasoning["hotel_agent"] = "Skipped hotel lookup because destination was missing."
        return state

    hotel_result = hotel_service.search_hotels(destination, budget=budget, travel_type=style, preference=preference)
    hotels = hotel_result.get("hotels", [])
    if not hotels:
        hotels = [
            {"name": f"{destination} Center Stay", "type": "fallback", "summary": "No live hotel data available", "source": "fallback"},
        ]

    state.hotel_data = {"source": hotel_result.get("source", "fallback"), "location": hotel_result.get("location", destination), "suggestions": hotels}

    top = hotels[0] if hotels else {}
    reasoning = (
        f"Selected hotel candidates for {destination} using budget={budget}, style={style}, preference='{preference}'. "
        f"Top pick: {top.get('name', 'N/A')}."
    )

    if llm_service is not None and getattr(llm_service, "enabled", False):
        try:
            llm_reason = llm_service.chat_text(
                system="You are a hotel recommender. Provide a short justification for the top suggestion.",
                user=f"Prefs: {prefs}\nHotels: {state.hotel_data}",
                timeout=10,
            ).strip()
            if llm_reason:
                reasoning = llm_reason
        except Exception:
            pass

    state.agent_reasoning["hotel_agent"] = reasoning
    return state
