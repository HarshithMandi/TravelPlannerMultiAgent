from src.agents.orchestrator import Orchestrator
from src.state.schemas import TripPlannerState
from src.services.llm_service import SarvamLLMService
from src.services.embedding_service import OpenAIEmbeddingService


def test_orchestrator_runs_minimal():
    state = TripPlannerState(session_id="s1", trip_preferences={"source":"A","destination":"B","start_date":"2026-01-01","end_date":"2026-01-05","budget":100000})
    llm = SarvamLLMService(api_key="dummy", model="sarvam-m")
    emb = OpenAIEmbeddingService(api_key="dummy", model="text-embedding-3-small")
    orch = Orchestrator(llm_service=llm, embedding_service=emb)
    res = orch.run(state)
    assert res.session_id == "s1"
