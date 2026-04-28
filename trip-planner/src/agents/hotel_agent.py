from src.state.schemas import TripPlannerState


def run(state: TripPlannerState) -> TripPlannerState:
    prefs = state.trip_preferences
    budget = prefs.get("budget", 0)
    style = prefs.get("luxury", "budget")
    # Mock hotel suggestions
    hotels = [
        {"name": "Coastal Retreat", "price_per_night": 4000, "match": "beach resort"},
        {"name": "City Stay", "price_per_night": 2500, "match": "city"},
    ]
    if style == "budget":
        hotels = sorted(hotels, key=lambda h: h["price_per_night"]) 

    state.hotel_data = {"suggestions": hotels}
    return state
