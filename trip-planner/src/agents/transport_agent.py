from src.state.schemas import TripPlannerState


def run(state: TripPlannerState) -> TripPlannerState:
    prefs = state.trip_preferences
    tp = prefs.get("transport_pref", "flight")
    # For free/demo: provide heuristic transport recommendations
    options = []
    if tp == "flight":
        options.append({"mode": "flight", "rationale": "fastest for intercity"})
    elif tp == "train":
        options.append({"mode": "train", "rationale": "cost-effective"})
    else:
        options.append({"mode": tp, "rationale": "preference"})

    state.transport_data = {"options": options}
    return state
