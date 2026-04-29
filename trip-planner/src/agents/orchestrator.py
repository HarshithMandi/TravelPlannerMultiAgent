from __future__ import annotations

from typing import Dict, List, Optional
import logging
from src.state.schemas import TripPlannerState
from src.agents import user_input_agent, memory_agent, weather_agent, transport_agent, hotel_agent, places_agent, budget_agent, itinerary_agent, final_review_agent, pdf_agent
from src.services.geocoding_service import GeocodingService
from src.services.weather_service import WeatherService
from src.services.routing_service import RoutingService
from src.services.places_service import PlacesService
from src.services.hotel_service import HotelService
from src.services.transport_service import TransportService

from langgraph.graph import END, StateGraph

logger = logging.getLogger(__name__)


class Orchestrator:
    """Central orchestrator controlling agent execution using shared state.

    This implementation uses a LangGraph `StateGraph` supervisor pattern.
    It records decisions into `orchestrator_decision`.
    """

    def __init__(self, llm_service=None, embedding_service=None):
        self.llm = llm_service
        self.embed = embedding_service
        self.geocoding_service = GeocodingService()
        self.weather_service = WeatherService(self.geocoding_service)
        self.routing_service = RoutingService(self.geocoding_service)
        self.places_service = PlacesService(self.geocoding_service)
        self.hotel_service = HotelService(self.geocoding_service)
        self.transport_service = TransportService(self.routing_service)

        self._graph = self._build_graph()

    def _record_decision(self, state: TripPlannerState, selected: List[str], reason: str):
        current = state.orchestrator_decision or {}
        if not isinstance(current, dict):
            current = {}
        current.update({"selected_next_agents": selected, "reason": reason})
        state.orchestrator_decision = current

    def _completed_agents(self, state: TripPlannerState) -> List[str]:
        completed = state.orchestrator_decision.get("completed_agents")
        if isinstance(completed, list):
            return completed
        return []

    def _mark_completed(self, state: TripPlannerState, agent_name: str) -> None:
        completed = self._completed_agents(state)
        if agent_name not in completed:
            completed.append(agent_name)
        state.orchestrator_decision["completed_agents"] = completed

    def _retry_count(self, state: TripPlannerState, key: str) -> int:
        try:
            return int((state.retry_counts or {}).get(key, 0))
        except Exception:
            return 0

    def _inc_retry(self, state: TripPlannerState, key: str) -> None:
        current = self._retry_count(state, key)
        state.retry_counts[key] = current + 1

    def _needs_itinerary(self, state: TripPlannerState) -> bool:
        if not state.itinerary:
            return True
        days = state.itinerary.get("days")
        return not bool(days)

    def _needs_budget(self, state: TripPlannerState) -> bool:
        return not bool(state.budget_summary)

    def _supervisor(self, state: TripPlannerState) -> TripPlannerState:
        completed = set(self._completed_agents(state))

        prefs = state.trip_preferences or {}
        if "user_input_agent" not in completed:
            self._record_decision(state, ["user_input_agent"], "Normalize/validate inputs")
            state.orchestrator_decision["next"] = "user_input_agent"
            return state

        # Basic completeness check (avoid calling downstream services with missing destination)
        destination = prefs.get("destination")
        if not destination:
            self._record_decision(state, [], "Missing destination: cannot plan trip")
            state.final_output = {"summary": "Missing destination", "reasons": ["Destination is required"]}
            state.orchestrator_decision["next"] = "finalize"
            return state

        if "memory_agent" not in completed:
            self._record_decision(state, ["memory_agent"], "Retrieve memory context")
            state.orchestrator_decision["next"] = "memory_agent"
            return state

        if not state.weather_data:
            self._record_decision(state, ["weather_agent"], "Fetch weather")
            state.orchestrator_decision["next"] = "weather_agent"
            return state

        if not state.transport_data:
            self._record_decision(state, ["transport_agent"], "Fetch transport")
            state.orchestrator_decision["next"] = "transport_agent"
            return state

        if not state.hotel_data:
            self._record_decision(state, ["hotel_agent"], "Fetch hotels")
            state.orchestrator_decision["next"] = "hotel_agent"
            return state

        if not state.places_data:
            self._record_decision(state, ["places_agent"], "Fetch places")
            state.orchestrator_decision["next"] = "places_agent"
            return state

        if self._needs_budget(state):
            self._record_decision(state, ["budget_agent"], "Estimate and optimize budget")
            state.orchestrator_decision["next"] = "budget_agent"
            return state

        if self._needs_itinerary(state):
            self._record_decision(state, ["itinerary_agent"], "Compose day-wise itinerary")
            state.orchestrator_decision["next"] = "itinerary_agent"
            return state

        # Review can be re-run if we do a retry cycle
        if "final_review_agent" not in completed or state.review_status is None:
            self._record_decision(state, ["final_review_agent"], "Validate completeness and conflicts")
            state.orchestrator_decision["next"] = "final_review_agent"
            return state

        # Conflict resolution loop: attempt a single retry for missing itinerary / over-budget
        if not state.review_status.approved:
            reasons = state.review_status.reasons or []
            if "Estimated cost exceeds budget" in reasons and self._retry_count(state, "budget_agent") < 1:
                self._inc_retry(state, "budget_agent")
                self._record_decision(state, ["budget_agent"], "Retry budget optimization after review")
                state.orchestrator_decision["next"] = "budget_agent"
                return state

            if "Itinerary is empty" in reasons and self._retry_count(state, "itinerary_agent") < 1:
                self._inc_retry(state, "itinerary_agent")
                self._record_decision(state, ["itinerary_agent"], "Retry itinerary generation after review")
                state.orchestrator_decision["next"] = "itinerary_agent"
                return state

        if state.review_status.approved and not (state.pdf_status and state.pdf_status.generated):
            self._record_decision(state, ["pdf_agent"], "Approved: generate report")
            state.orchestrator_decision["next"] = "pdf_agent"
            return state

        self._record_decision(state, [], "Done")
        state.orchestrator_decision["next"] = "finalize"
        return state

    def _route_from_supervisor(self, state: TripPlannerState) -> str:
        nxt = (state.orchestrator_decision or {}).get("next")
        if isinstance(nxt, str) and nxt:
            return nxt
        return "finalize"

    def _node_user_input(self, state: TripPlannerState) -> TripPlannerState:
        state = user_input_agent.run(state)
        self._mark_completed(state, "user_input_agent")
        return state

    def _node_memory(self, state: TripPlannerState) -> TripPlannerState:
        if self.embed is None:
            state.memory_context = {"note": "Embedding service not configured"}
        else:
            state = memory_agent.run(state, embedding_service=self.embed)
        self._mark_completed(state, "memory_agent")
        return state

    def _node_weather(self, state: TripPlannerState) -> TripPlannerState:
        state = weather_agent.run(state, weather_service=self.weather_service)
        self._mark_completed(state, "weather_agent")
        return state

    def _node_transport(self, state: TripPlannerState) -> TripPlannerState:
        state = transport_agent.run(state, transport_service=self.transport_service)
        self._mark_completed(state, "transport_agent")
        return state

    def _node_hotel(self, state: TripPlannerState) -> TripPlannerState:
        state = hotel_agent.run(state, hotel_service=self.hotel_service)
        self._mark_completed(state, "hotel_agent")
        return state

    def _node_places(self, state: TripPlannerState) -> TripPlannerState:
        state = places_agent.run(state, places_service=self.places_service)
        self._mark_completed(state, "places_agent")
        return state

    def _node_budget(self, state: TripPlannerState) -> TripPlannerState:
        state = budget_agent.run(state)
        self._mark_completed(state, "budget_agent")
        return state

    def _node_itinerary(self, state: TripPlannerState) -> TripPlannerState:
        state = itinerary_agent.run(state)
        self._mark_completed(state, "itinerary_agent")
        return state

    def _node_final_review(self, state: TripPlannerState) -> TripPlannerState:
        state = final_review_agent.run(state)
        self._mark_completed(state, "final_review_agent")
        return state

    def _node_pdf(self, state: TripPlannerState) -> TripPlannerState:
        state = pdf_agent.run(state)
        self._mark_completed(state, "pdf_agent")
        return state

    def _node_finalize(self, state: TripPlannerState) -> TripPlannerState:
        if state.review_status and state.review_status.approved:
            state.final_output = {"summary": "Trip planned and approved."}
        else:
            reasons = []
            if state.review_status:
                reasons = state.review_status.reasons or []
            state.final_output = {"summary": "Review failed", "reasons": reasons}
        self._mark_completed(state, "finalize")
        return state

    def _build_graph(self):
        graph = StateGraph(TripPlannerState)

        graph.add_node("supervisor", self._supervisor)
        graph.add_node("user_input_agent", self._node_user_input)
        graph.add_node("memory_agent", self._node_memory)
        graph.add_node("weather_agent", self._node_weather)
        graph.add_node("transport_agent", self._node_transport)
        graph.add_node("hotel_agent", self._node_hotel)
        graph.add_node("places_agent", self._node_places)
        graph.add_node("budget_agent", self._node_budget)
        graph.add_node("itinerary_agent", self._node_itinerary)
        graph.add_node("final_review_agent", self._node_final_review)
        graph.add_node("pdf_agent", self._node_pdf)
        graph.add_node("finalize", self._node_finalize)

        graph.set_entry_point("supervisor")

        graph.add_conditional_edges(
            "supervisor",
            self._route_from_supervisor,
            {
                "user_input_agent": "user_input_agent",
                "memory_agent": "memory_agent",
                "weather_agent": "weather_agent",
                "transport_agent": "transport_agent",
                "hotel_agent": "hotel_agent",
                "places_agent": "places_agent",
                "budget_agent": "budget_agent",
                "itinerary_agent": "itinerary_agent",
                "final_review_agent": "final_review_agent",
                "pdf_agent": "pdf_agent",
                "finalize": "finalize",
            },
        )

        # Every worker returns control back to the supervisor.
        for worker in [
            "user_input_agent",
            "memory_agent",
            "weather_agent",
            "transport_agent",
            "hotel_agent",
            "places_agent",
            "budget_agent",
            "itinerary_agent",
            "final_review_agent",
            "pdf_agent",
        ]:
            graph.add_edge(worker, "supervisor")

        graph.add_edge("finalize", END)
        return graph.compile()

    def run(self, state: TripPlannerState, debug: bool = False) -> TripPlannerState:
        try:
            result = self._graph.invoke(state)
        except Exception:
            logger.exception("LangGraph orchestration failed")
            raise

        # LangGraph returns a dict for Pydantic state schemas.
        if isinstance(result, TripPlannerState):
            return result
        if isinstance(result, dict):
            return TripPlannerState(**result)
        raise TypeError(f"Unexpected LangGraph result type: {type(result)}")
