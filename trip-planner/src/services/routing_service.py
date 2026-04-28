import logging
from typing import Dict, Optional

import requests

from src.config.settings import settings
from src.services.geocoding_service import GeocodingService

logger = logging.getLogger(__name__)


class RoutingService:
    """Gets route estimates from OpenRouteService or OSRM fallback."""

    def __init__(self, geocoding_service: Optional[GeocodingService] = None):
        self.geocoding_service = geocoding_service or GeocodingService()

    def route(self, source: str, destination: str, timeout: int = 20) -> Dict:
        source_location = self.geocoding_service.geocode(source)
        destination_location = self.geocoding_service.geocode(destination)
        if not source_location or not destination_location:
            return {"origin": source, "destination": destination, "source": "fallback", "distance_km": None, "duration_min": None}

        if settings.OPENROUTESERVICE_API_KEY:
            return self._route_openrouteservice(source_location, destination_location, timeout)

        return self._route_osrm(source_location, destination_location, timeout)

    def _route_openrouteservice(self, source_location, destination_location, timeout: int) -> Dict:
        url = "https://api.openrouteservice.org/v2/directions/driving-car"
        headers = {"Authorization": settings.OPENROUTESERVICE_API_KEY, "Content-Type": "application/json"}
        payload = {
            "coordinates": [[source_location.lon, source_location.lat], [destination_location.lon, destination_location.lat]]
        }
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            summary = data["features"][0]["properties"]["summary"]
            return {
                "source": "openrouteservice",
                "distance_km": round(summary.get("distance", 0) / 1000, 2),
                "duration_min": round(summary.get("duration", 0) / 60, 2),
                "geometry": data["features"][0].get("geometry"),
            }
        except Exception as exc:
            # Suppress verbose logging, silently fallback to OSRM
            return self._route_osrm(source_location, destination_location, timeout)

    def _route_osrm(self, source_location, destination_location, timeout: int) -> Dict:
        url = f"https://router.project-osrm.org/route/v1/driving/{source_location.lon},{source_location.lat};{destination_location.lon},{destination_location.lat}"
        params = {"overview": "false", "alternatives": "false", "steps": "false"}
        try:
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            route = data["routes"][0]
            return {
                "source": "osrm",
                "distance_km": round(route.get("distance", 0) / 1000, 2),
                "duration_min": round(route.get("duration", 0) / 60, 2),
            }
        except Exception as exc:
            logger.warning("OSRM route fetch failed: %s", exc)
            return {"source": "fallback", "distance_km": None, "duration_min": None}
