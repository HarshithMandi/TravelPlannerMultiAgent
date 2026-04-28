from src.state.schemas import TripPlannerState


def run(state: TripPlannerState) -> TripPlannerState:
    prefs = state.trip_preferences
    interests = prefs.get("places_of_interest", [])
    # Mock places
    places = [
        {"name": "Beautiful Beach", "type": "beach", "notes": "Great for sunset"},
        {"name": "Historic Fort", "type": "sightseeing", "notes": "Cultural site"},
    ]
    state.places_data = {"places": places, "requested": interests}
    return state
