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
        if distance > 800:
            recommendations.append({"mode": "flight", "reason": "Long distance route"})
        if distance > 150 and distance <= 800:
            recommendations.append({"mode": "train", "reason": "Balanced cost and time"})
        if distance <= 150:
            recommendations.append({"mode": "car", "reason": "Short route, flexible travel"})
        if transport_pref and all(item["mode"] != transport_pref for item in recommendations):
            recommendations.insert(0, {"mode": transport_pref, "reason": "User preference"})

        if not recommendations:
            recommendations.append({"mode": transport_pref or "flight", "reason": "Fallback recommendation"})

        return {
            "route": route_data,
            "recommendations": recommendations,
            "budget_signal": "tight" if budget and budget < 20000 else "normal",
            "source": route_data.get("source", "routing"),
            "summary": f"Route estimate {distance:.1f} km, {duration:.1f} min" if distance and duration else "Route estimate unavailable",
        }
