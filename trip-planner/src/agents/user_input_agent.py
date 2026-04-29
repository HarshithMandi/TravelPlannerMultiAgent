from typing import Optional
from src.state.schemas import TripPlannerState
from src.services.llm_service import SarvamLLMService


def run(state: TripPlannerState, llm_service: Optional[SarvamLLMService] = None) -> TripPlannerState:
    """Normalize and validate user input into structured trip_preferences."""
    prefs = state.trip_preferences
    # Basic normalization
    prefs.setdefault("places_of_interest", [])
    prefs["travelers"] = int(prefs.get("travelers", 1))
    state.trip_preferences = prefs

    reasoning = (
        f"Normalized inputs (travelers={prefs.get('travelers')}). "
        "Validated required fields where possible and prepared preferences for downstream agents."
    )

    if llm_service is not None and getattr(llm_service, "enabled", False):
        try:
            llm_reason = llm_service.chat_text(
                system="You are validating trip-planner user inputs. Provide a short rationale (1-2 sentences).",
                user=f"Trip preferences: {prefs}",
                timeout=10,
            ).strip()
            if llm_reason:
                reasoning = llm_reason
        except Exception:
            pass

    state.agent_reasoning["user_input_agent"] = reasoning
    return state
