from __future__ import annotations

from typing import Optional

from src.state.schemas import TripPlannerState
from src.services.embedding_service import OpenAIEmbeddingService
from src.services.llm_service import SarvamLLMService
from src.services.memory_store import ChromaMemoryStore


def run(
    state: TripPlannerState,
    embedding_service: OpenAIEmbeddingService,
    *,
    memory_store: Optional[ChromaMemoryStore] = None,
    llm_service: Optional[SarvamLLMService] = None,
    top_k: int = 3,
) -> TripPlannerState:
    prefs = state.trip_preferences or {}
    destination = str(prefs.get("destination") or "").strip()
    user_id = str((state.user_profile or {}).get("user_id") or state.session_id)

    if not destination:
        state.memory_context = {"note": "Memory retrieval skipped because destination is missing."}
        state.agent_reasoning["memory_agent"] = "Memory retrieval skipped because destination was missing."
        return state

    if memory_store is None:
        state.memory_context = {"note": f"No persistent memory store configured for {destination}"}
        state.agent_reasoning["memory_agent"] = "Memory retrieval skipped because no memory store is configured."
        return state

    query_text = f"destination={destination}; travel_type={prefs.get('travel_type')}; interests={prefs.get('places_of_interest')}; budget={prefs.get('budget')}"
    query_embedding = embedding_service.embed_batch([query_text])[0]

    matches = memory_store.search(query_embedding=query_embedding, user_id=user_id, destination=destination, top_k=top_k)
    retrieved = [
        {"id": entry.id, "destination": entry.destination, "text": entry.text, "score": float(score), "metadata": entry.metadata}
        for entry, score in matches
        if entry.text
    ]

    summary = "No matching past preferences found."
    if retrieved:
        summary = "Retrieved past preferences that may improve personalization."

    if llm_service is not None and getattr(llm_service, "enabled", False):
        try:
            llm_summary = llm_service.chat_text(
                system=(
                    "You are a memory retrieval assistant for trip planning. "
                    "Given retrieved memory notes, produce a concise summary (2-3 bullets) of actionable preferences."
                ),
                user=f"Current prefs: {prefs}\nRetrieved notes: {retrieved}",
                timeout=10,
            ).strip()
            if llm_summary:
                summary = llm_summary
        except Exception:
            pass

    state.memory_context = {
        "destination": destination,
        "user_id": user_id,
        "retrieved": retrieved,
        "summary": summary,
    }
    state.agent_reasoning["memory_agent"] = f"Vector-retrieved {len(retrieved)} memory notes for personalization."
    return state
