from typing import Optional

from src.state.schemas import TripPlannerState
from src.config.settings import settings
from src.services.weather_service import WeatherService
from src.services.llm_service import SarvamLLMService


def run(
    state: TripPlannerState,
    weather_service: Optional[WeatherService] = None,
    llm_service: Optional[SarvamLLMService] = None,
) -> TripPlannerState:
    weather_service = weather_service or WeatherService()
    destination = state.trip_preferences.get("destination")
    if not destination:
        state.weather_data = {"source": "fallback", "summary": "Destination missing"}
        state.agent_reasoning["weather_agent"] = "Skipped weather lookup because destination was missing."
        return state

    state.weather_data = weather_service.fetch_weather(destination)

    source = (state.weather_data or {}).get("source", "unknown")
    forecast_count = len((state.weather_data or {}).get("forecast") or [])
    reasoning = f"Fetched forecast for {destination} using {source} ({forecast_count} points)."

    if llm_service is not None and getattr(llm_service, "enabled", False):
        try:
            llm_reason = llm_service.chat_text(
                system=(
                    "You are a travel weather assistant. Explain how the forecast affects planning in 1-2 sentences."
                ),
                user=f"Destination: {destination}\nForecast: {state.weather_data}",
                timeout=10,
            ).strip()
            if llm_reason:
                reasoning = llm_reason
        except Exception:
            pass

    state.agent_reasoning["weather_agent"] = reasoning
    return state
