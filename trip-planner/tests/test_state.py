from src.state.schemas import TripPlannerState


def test_state_defaults():
    s = TripPlannerState(session_id="123", trip_preferences={})
    assert s.session_id == "123"
    assert isinstance(s.itinerary, dict)
