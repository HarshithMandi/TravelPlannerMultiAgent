from typing import Optional

from src.state.schemas import TripPlannerState
from src.services.transport_service import TransportService


def run(state: TripPlannerState, transport_service: Optional[TransportService] = None) -> TripPlannerState:
    transport_service = transport_service or TransportService()
    prefs = state.trip_preferences
    source = prefs.get("source", "")
    destination = prefs.get("destination", "")
    tp = prefs.get("transport_pref", "flight")
    budget = float(prefs.get("budget", 0) or 0)

    if not source or not destination:
        state.transport_data = {"source": "fallback", "recommendations": [{"mode": tp, "reason": "Missing route data"}]}
        return state

    state.transport_data = transport_service.recommend(source, destination, tp, budget)
    return state
