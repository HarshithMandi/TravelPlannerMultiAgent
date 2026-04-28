from src.state.schemas import TripPlannerState


def run(state: TripPlannerState) -> TripPlannerState:
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
    state.budget_summary = {"estimated_total": total_est, "within_budget": total_est <= state.trip_preferences.get("budget", 0)}
    return state
