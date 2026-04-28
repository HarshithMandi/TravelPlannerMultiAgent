from src.state.schemas import TripPlannerState


def run(state: TripPlannerState) -> TripPlannerState:
    # Create a simple day-wise mock itinerary respecting trip dates
    start = state.trip_preferences.get("start_date")
    end = state.trip_preferences.get("end_date")
    itinerary = {"days": []}
    # Very naive example: fill daily plans from places_data
    places = state.places_data.get("places", []) if state.places_data else []
    for i, place in enumerate(places, start=1):
        itinerary["days"].append({"day": i, "activity": place["name"], "notes": place.get("notes")})

    state.itinerary = itinerary
    return state
