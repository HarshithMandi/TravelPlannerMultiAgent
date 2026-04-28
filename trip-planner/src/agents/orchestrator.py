from typing import List
import logging
from src.state.schemas import TripPlannerState
from src.agents import user_input_agent, memory_agent, weather_agent, transport_agent, hotel_agent, places_agent, budget_agent, itinerary_agent, final_review_agent, pdf_agent

logger = logging.getLogger(__name__)


class Orchestrator:
    """Central orchestrator controlling agent execution using shared state.

    This implementation is a LangGraph-style supervisor pattern without requiring
    the LangGraph runtime. It records decisions into `orchestrator_decision`.
    """

    def __init__(self, llm_service=None, embedding_service=None):
        self.llm = llm_service
        self.embed = embedding_service

    def _record_decision(self, state: TripPlannerState, selected: List[str], reason: str):
        state.orchestrator_decision = {"selected_next_agents": selected, "reason": reason}

    def run(self, state: TripPlannerState, debug: bool = False) -> TripPlannerState:
        # 1. User Input
        self._record_decision(state, ["user_input_agent"], "Normalize/validate inputs")
        state = user_input_agent.run(state)

        # 2. Memory retrieval
        self._record_decision(state, ["memory_agent"], "Retrieve memory context")
        state = memory_agent.run(state, embedding_service=self.embed)

        # 3. Decide parallel agents
        parallel = ["weather_agent", "transport_agent", "hotel_agent", "places_agent"]
        self._record_decision(state, parallel, "Fetch weather, transport, hotels, places in parallel (sequential here)")
        state = weather_agent.run(state)
        state = transport_agent.run(state)
        state = hotel_agent.run(state)
        state = places_agent.run(state)

        # 4. Budget
        self._record_decision(state, ["budget_agent"], "Estimate and optimize budget")
        state = budget_agent.run(state)

        # 5. Itinerary
        self._record_decision(state, ["itinerary_agent"], "Compose day-wise itinerary")
        state = itinerary_agent.run(state)

        # 6. Final review
        self._record_decision(state, ["final_review_agent"], "Validate completeness and conflicts")
        state = final_review_agent.run(state)

        # 7. If approved generate PDF and store to memory
        if state.review_status.approved:
            self._record_decision(state, ["pdf_agent"], "Approved: generate PDF and store memory")
            state = pdf_agent.run(state)
            state.final_output = {"summary": "Trip planned and approved."}
        else:
            self._record_decision(state, [], "Not approved: return review reasons")
            state.final_output = {"summary": "Review failed", "reasons": state.review_status.reasons}

        return state
