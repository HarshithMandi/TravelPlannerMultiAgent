from src.state.schemas import TripPlannerState


def run(state: TripPlannerState) -> TripPlannerState:
    # Very simple budget estimation: sum hotel+transport rough estimates
    hotel_est = 0
    if state.hotel_data and state.hotel_data.get("suggestions"):
        hotel_est = state.hotel_data["suggestions"][0]["price_per_night"] * 3

    transport_est = 8000
    total_est = hotel_est + transport_est
    state.budget_summary = {"estimated_total": total_est, "within_budget": total_est <= state.trip_preferences.get("budget", 0)}
    return state
