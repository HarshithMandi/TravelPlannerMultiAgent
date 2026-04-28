import logging
from typing import Dict, List, Optional

import requests

from src.services.geocoding_service import GeocodingService

logger = logging.getLogger(__name__)


class HotelService:
    """Finds hotel-like stays using OpenStreetMap Overpass results.

    Free, public hotel inventory APIs are limited, so this service uses map data
    to produce realistic, web-backed recommendations with fallback heuristics.
    """

    def __init__(self, geocoding_service: Optional[GeocodingService] = None):
        self.geocoding_service = geocoding_service or GeocodingService()

    def search_hotels(self, destination: str, budget: float, travel_type: str, preference: str, timeout: int = 20) -> Dict:
        location = self.geocoding_service.geocode(destination)
        if not location:
            return {"source": "fallback", "hotels": []}

        hotels = self._search_overpass_hotels(location.lat, location.lon, timeout)
        ranked = self._rank_hotels(hotels, budget=budget, travel_type=travel_type, preference=preference)
        return {
            "source": "overpass",
            "location": location.display_name,
            "hotels": ranked[:10],
        }

    def _search_overpass_hotels(self, lat: float, lon: float, timeout: int) -> List[Dict]:
        query = f"""
        [out:json][timeout:20];
        (
          node(around:8000,{lat},{lon})[tourism=hotel];
          node(around:8000,{lat},{lon})[tourism=guest_house];
          node(around:8000,{lat},{lon})[tourism=hostel];
          way(around:8000,{lat},{lon})[tourism=hotel];
          way(around:8000,{lat},{lon})[tourism=guest_house];
          way(around:8000,{lat},{lon})[tourism=hostel];
        );
        out center tags;
        """
        headers = {"User-Agent": "multi-agent-trip-planner/1.0", "Accept": "application/json"}
        try:
            response = requests.post("https://overpass-api.de/api/interpreter", data={"data": query}, headers=headers, timeout=timeout)
            response.raise_for_status()
            elements = response.json().get("elements", [])
            results = []
            for element in elements[:20]:
                tags = element.get("tags", {})
                name = tags.get("name")
                if not name:
                    continue
                results.append(
                    {
                        "name": name,
                        "type": tags.get("tourism", "hotel"),
                        "rating_hint": tags.get("stars") or tags.get("level") or tags.get("internet_access") or "unknown",
                        "summary": tags.get("description") or tags.get("operator") or "",
                        "source": "overpass",
                    }
                )
            return results
        except Exception as exc:
            logger.warning("Hotel overpass search failed: %s", exc)
            return []

    def _rank_hotels(self, hotels: List[Dict], budget: float, travel_type: str, preference: str) -> List[Dict]:
        preference_blob = f"{travel_type} {preference}".lower()

        def score(hotel: Dict) -> int:
            blob = f"{hotel.get('name', '')} {hotel.get('type', '')} {hotel.get('summary', '')}".lower()
            bonus = sum(1 for term in preference_blob.split() if term and term in blob)
            if budget and budget < 20000 and hotel.get("type") in {"hostel", "guest_house"}:
                bonus += 2
            return bonus

        return sorted(hotels, key=score, reverse=True)
