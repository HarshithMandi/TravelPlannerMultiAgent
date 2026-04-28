from typing import Optional

from src.state.schemas import TripPlannerState
from src.services.places_service import PlacesService


def run(state: TripPlannerState, places_service: Optional[PlacesService] = None) -> TripPlannerState:
    places_service = places_service or PlacesService()
    prefs = state.trip_preferences
    interests = prefs.get("places_of_interest", [])
    destination = prefs.get("destination", "")

    if not destination:
        state.places_data = {"source": "fallback", "places": []}
        return state

    state.places_data = places_service.search_places(destination, interests)
    return state
