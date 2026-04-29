from typing import Optional

from src.state.schemas import TripPlannerState
from src.services.places_service import PlacesService
from src.services.llm_service import SarvamLLMService


def run(
    state: TripPlannerState,
    places_service: Optional[PlacesService] = None,
    llm_service: Optional[SarvamLLMService] = None,
) -> TripPlannerState:
    places_service = places_service or PlacesService()
    prefs = state.trip_preferences
    interests = prefs.get("places_of_interest", [])
    destination = prefs.get("destination", "")

    if not destination:
        state.places_data = {"source": "fallback", "places": []}
        state.agent_reasoning["places_agent"] = "Skipped places lookup because destination was missing."
        return state

    state.places_data = places_service.search_places(destination, interests)

    count = len((state.places_data or {}).get("places") or [])
    reasoning = f"Fetched {count} attractions/experiences for {destination} based on interests: {interests}."

    if llm_service is not None and getattr(llm_service, "enabled", False):
        try:
            llm_reason = llm_service.chat_text(
                system="You are a travel guide. Explain why these places match the interests in 1-2 sentences.",
                user=f"Destination: {destination}\nInterests: {interests}\nPlaces: {state.places_data}",
                timeout=10,
            ).strip()
            if llm_reason:
                reasoning = llm_reason
        except Exception:
            pass

    state.agent_reasoning["places_agent"] = reasoning
    return state
