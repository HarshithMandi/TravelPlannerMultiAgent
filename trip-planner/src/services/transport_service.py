import logging
from typing import Dict, Optional

from src.services.routing_service import RoutingService

logger = logging.getLogger(__name__)


class TransportService:
    """Builds transport recommendations from route data."""

    def __init__(self, routing_service: Optional[RoutingService] = None):
        self.routing_service = routing_service or RoutingService()

    def recommend(self, source: str, destination: str, transport_pref: str, budget: float) -> Dict:
        route_data = self.routing_service.route(source, destination)
        distance = route_data.get("distance_km") or 0
        duration = route_data.get("duration_min") or 0

        recommendations = []
        destination_lower = (destination or "").lower()
        island_destination = any(term in destination_lower for term in ["maldives", "andaman", "lakshadweep", "sri lanka", "bali"])

        if island_destination:
            recommendations.append({"mode": "flight", "reason": "Primary practical route for island destination"})
            recommendations.append({"mode": "speedboat/ferry", "reason": "Common transfer from airport or capital to local islands/resorts"})
        elif distance > 800:
            recommendations.append({"mode": "flight", "reason": "Long distance route"})
        if not island_destination and distance > 150 and distance <= 800:
            recommendations.append({"mode": "train", "reason": "Balanced cost and time"})
        if not island_destination and distance <= 150:
            recommendations.append({"mode": "car", "reason": "Short route, flexible travel"})
        if transport_pref and all(item["mode"] != transport_pref for item in recommendations):
            recommendations.insert(0, {"mode": transport_pref, "reason": "User preference"})

        if not recommendations:
            recommendations.append({"mode": transport_pref or "flight", "reason": "Fallback recommendation"})

        primary = recommendations[0] if recommendations else {}
        flight_details = {
            "recommended_mode": primary.get("mode") or transport_pref or "flight",
            "reason": primary.get("reason") or "Fallback recommendation",
            "summary": (
                "Use flight plus island transfer; road distance is not meaningful for this destination"
                if island_destination
                else f"Route estimate {distance:.1f} km, {duration:.1f} min" if distance and duration else "Route estimate unavailable"
            ),
            "route": route_data,
            "options": recommendations,
        }

        return {
            "route": route_data,
            "recommendations": recommendations,
            "budget_signal": "tight" if budget and budget < 20000 else "normal",
            "source": route_data.get("source", "routing"),
            "summary": flight_details["summary"],
            "flight_details": flight_details,
        }
