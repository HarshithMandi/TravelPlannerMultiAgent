from typing import Optional

from src.state.schemas import TripPlannerState
from src.services.hotel_service import HotelService


def run(state: TripPlannerState, hotel_service: Optional[HotelService] = None) -> TripPlannerState:
    hotel_service = hotel_service or HotelService()
    prefs = state.trip_preferences
    budget = prefs.get("budget", 0)
    style = prefs.get("luxury", "budget")
    destination = prefs.get("destination", "")
    preference = prefs.get("hotel_pref", "")

    if not destination:
        state.hotel_data = {"source": "fallback", "hotels": []}
        return state

    hotel_result = hotel_service.search_hotels(destination, budget=budget, travel_type=style, preference=preference)
    hotels = hotel_result.get("hotels", [])
    if not hotels:
        hotels = [
            {"name": f"{destination} Center Stay", "type": "fallback", "summary": "No live hotel data available", "source": "fallback"},
        ]

    state.hotel_data = {"source": hotel_result.get("source", "fallback"), "location": hotel_result.get("location", destination), "suggestions": hotels}
    return state
