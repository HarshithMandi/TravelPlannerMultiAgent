import requests
from src.state.schemas import TripPlannerState
from src.config.settings import settings


def run(state: TripPlannerState) -> TripPlannerState:
    api = settings.OPENWEATHERMAP_API_KEY
    dest = state.trip_preferences.get("destination")
    if not api:
        state.weather_data = {"note": "No OpenWeatherMap API key configured; using mock weather."}
        return state

    # Very simple geocoding via OpenWeatherMap not included; use mock for demo
    state.weather_data = {"forecast": "Sunny, pleasant; mock data"}
    return state
