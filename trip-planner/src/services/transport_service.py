import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

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

        flight_recommendations = self._build_flight_recommendations(
            source=source,
            destination=destination,
            distance_km=float(distance or 0),
            user_pref=transport_pref,
        )

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
            "flight_recommendations": flight_recommendations,
        }

        return {
            "route": route_data,
            "recommendations": recommendations,
            "budget_signal": "tight" if budget and budget < 20000 else "normal",
            "source": route_data.get("source", "routing"),
            "summary": flight_details["summary"],
            "flight_details": flight_details,
        }

    def _build_flight_recommendations(self, source: str, destination: str, distance_km: float, user_pref: str) -> List[Dict]:
        if not source or not destination:
            return []

        preferred_flight = (user_pref or "").lower().strip() == "flight"
        # For shorter routes, still provide an option but tag it as optional.
        if distance_km and distance_km < 140 and not preferred_flight:
            return []

        estimated_duration_min = self._estimate_flight_duration(distance_km)
        airlines = [
            ("IndiGo", "6E"),
            ("Air India", "AI"),
            ("Akasa Air", "QP"),
        ]
        departure_slots = ["06:15", "11:20", "18:40"]

        recommendations: List[Dict] = []
        for idx, ((airline, code), dep_time) in enumerate(zip(airlines, departure_slots), start=1):
            arr_time = self._add_minutes(dep_time, estimated_duration_min)
            recommendations.append(
                {
                    "airline": airline,
                    "flight_number": f"{code}{410 + idx}",
                    "from": source,
                    "to": destination,
                    "departure_time": dep_time,
                    "arrival_time": arr_time,
                    "duration_min": estimated_duration_min,
                    "note": "Estimated schedule from routing heuristics; verify live inventory before booking.",
                }
            )
        return recommendations

    def _estimate_flight_duration(self, distance_km: float) -> int:
        if distance_km <= 0:
            return 110
        # Coarse estimate for domestic/short-haul flight block time.
        estimated = int((distance_km / 7.8) + 45)
        return max(70, min(300, estimated))

    def _add_minutes(self, hhmm: str, minutes: int) -> str:
        base = datetime.strptime(hhmm, "%H:%M")
        result = base + timedelta(minutes=int(minutes))
        return result.strftime("%H:%M")
