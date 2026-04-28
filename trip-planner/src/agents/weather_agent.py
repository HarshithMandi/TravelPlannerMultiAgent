from typing import Optional

from src.state.schemas import TripPlannerState
from src.config.settings import settings
from src.services.weather_service import WeatherService


def run(state: TripPlannerState, weather_service: Optional[WeatherService] = None) -> TripPlannerState:
    weather_service = weather_service or WeatherService()
    destination = state.trip_preferences.get("destination")
    if not destination:
        state.weather_data = {"source": "fallback", "summary": "Destination missing"}
        return state

    state.weather_data = weather_service.fetch_weather(destination)
    return state
