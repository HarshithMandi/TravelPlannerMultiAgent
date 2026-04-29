from typing import Optional

from src.state.schemas import TripPlannerState
from src.services.transport_service import TransportService
from src.services.llm_service import SarvamLLMService


def run(
    state: TripPlannerState,
    transport_service: Optional[TransportService] = None,
    llm_service: Optional[SarvamLLMService] = None,
) -> TripPlannerState:
    transport_service = transport_service or TransportService()
    prefs = state.trip_preferences
    source = prefs.get("source", "")
    destination = prefs.get("destination", "")
    tp = prefs.get("transport_pref", "flight")
    budget = float(prefs.get("budget", 0) or 0)

    if not source or not destination:
        state.transport_data = {"source": "fallback", "recommendations": [{"mode": tp, "reason": "Missing route data"}]}
        state.agent_reasoning["transport_agent"] = "Returned fallback transport recommendation due to missing source/destination."
        return state

    state.transport_data = transport_service.recommend(source, destination, tp, budget)

    recs = (state.transport_data or {}).get("recommendations") or []
    top = recs[0] if recs else {}
    reasoning = f"Recommended {top.get('mode', tp)} primarily due to: {top.get('reason', 'routing heuristics')}."

    if llm_service is not None and getattr(llm_service, "enabled", False):
        try:
            llm_reason = llm_service.chat_text(
                system="You are a transport planner. Justify the recommended mode in 1-2 sentences.",
                user=f"Prefs: {prefs}\nRoute+recs: {state.transport_data}",
                timeout=10,
            ).strip()
            if llm_reason:
                reasoning = llm_reason
        except Exception:
            pass

    state.agent_reasoning["transport_agent"] = reasoning
    return state
