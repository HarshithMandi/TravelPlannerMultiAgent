from src.state.schemas import TripPlannerState
from src.services.embedding_service import OpenAIEmbeddingService


def run(state: TripPlannerState, embedding_service: OpenAIEmbeddingService) -> TripPlannerState:
    # For demo: return empty memory context or placeholder
    # In production: perform vector search over stored memory using embeddings
    prefs = state.trip_preferences
    memory_ctx = {"note": f"No stored memory for {prefs.get('destination')}"}
    state.memory_context = memory_ctx
    return state
