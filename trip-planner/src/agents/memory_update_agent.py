from __future__ import annotations

import hashlib
from typing import Optional

from src.state.schemas import TripPlannerState
from src.services.embedding_service import OpenAIEmbeddingService
from src.services.memory_store import ChromaMemoryStore
from src.services.llm_service import SarvamLLMService


def _stable_id(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]


def _build_memory_text(state: TripPlannerState) -> str:
    prefs = state.trip_preferences or {}
    destination = str(prefs.get("destination", "")).strip()
    travel_type = str(prefs.get("travel_type", "")).strip()
    hotel_pref = str(prefs.get("hotel_pref", "")).strip()
    transport_pref = str(prefs.get("transport_pref", "")).strip()
    interests = prefs.get("places_of_interest", []) or []
    budget = prefs.get("budget")

    parts = [
        f"Destination: {destination}",
        f"Travel type: {travel_type}",
        f"Budget: {budget}",
        f"Hotel preference: {hotel_pref}",
        f"Transport preference: {transport_pref}",
        f"Interests: {', '.join([str(x) for x in interests if x])}",
    ]

    itinerary = state.itinerary or {}
    if itinerary.get("days"):
        parts.append(f"Itinerary days: {len(itinerary.get('days') or [])}")

    return "\n".join([p for p in parts if p and not p.endswith(": ")])


def run(
    state: TripPlannerState,
    *,
    embedding_service: Optional[OpenAIEmbeddingService] = None,
    memory_store: Optional[ChromaMemoryStore] = None,
    llm_service: Optional[SarvamLLMService] = None,
) -> TripPlannerState:
    """Persist a compact memory entry after a successful plan.

    Designed to be called by the orchestrator after final approval.
    """

    if not (state.review_status and state.review_status.approved):
        state.agent_reasoning["memory_update_agent"] = "Skipped memory update because plan was not approved."
        return state

    if memory_store is None or embedding_service is None:
        state.agent_reasoning["memory_update_agent"] = "Skipped memory update because memory store/embedding service is not configured."
        return state

    prefs = state.trip_preferences or {}
    if not ((state.user_profile or {}).get("user_id") or prefs.get("remember_preferences")):
        state.agent_reasoning["memory_update_agent"] = "Skipped memory update because persistent memory was not requested."
        return state

    base_text = _build_memory_text(state)

    # Optional: LLM-compressed summary for better retrieval quality.
    final_text = base_text
    if llm_service is not None and getattr(llm_service, "enabled", False):
        try:
            summary = llm_service.chat_text(
                system=(
                    "You compress trip preferences into a short memory note for future retrieval. "
                    "Return 3-5 bullet points, each <= 15 words. No extra commentary."
                ),
                user=base_text,
                timeout=15,
            )
            summary = (summary or "").strip()
            if summary:
                final_text = summary
        except Exception:
            # Don't fail the run if LLM is unavailable.
            pass

    embedding = embedding_service.embed_batch([final_text])[0]

    user_id = str((state.user_profile or {}).get("user_id") or state.session_id)
    destination = str((state.trip_preferences or {}).get("destination") or "")
    entry_id = _stable_id(f"{user_id}:{destination}:{final_text}")

    memory_store.upsert(
        entry_id=entry_id,
        user_id=user_id,
        destination=destination,
        text=final_text,
        embedding=embedding,
        metadata={"session_id": state.session_id},
    )

    state.agent_reasoning["memory_update_agent"] = "Stored a compact preference summary for future trips."
    return state
