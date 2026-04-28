from typing import Tuple
from src.state.schemas import TripPlannerState


def run(state: TripPlannerState) -> TripPlannerState:
    """Normalize and validate user input into structured trip_preferences."""
    prefs = state.trip_preferences
    # Basic normalization
    prefs.setdefault("places_of_interest", [])
    prefs["travelers"] = int(prefs.get("travelers", 1))
    state.trip_preferences = prefs
    return state
