import logging
from typing import Dict, List, Optional

import requests

from src.services.duckduckgo_service import DuckDuckGoSearchService
from src.services.geocoding_service import GeocodingService

logger = logging.getLogger(__name__)


class HotelService:
    """Finds hotel-like stays using OpenStreetMap Overpass results.

    Free, public hotel inventory APIs are limited, so this service uses map data
    to produce realistic, web-backed recommendations with fallback heuristics.
    """

    def __init__(self, geocoding_service: Optional[GeocodingService] = None):
        self.geocoding_service = geocoding_service or GeocodingService()
        self.duckduckgo = DuckDuckGoSearchService()

    def search_hotels(self, destination: str, budget: float, travel_type: str, preference: str, timeout: int = 12) -> Dict:
        hotels = self._search_duckduckgo_hotels(destination, preference, min(timeout, 6))
        location_name = destination
        if len(hotels) < 5:
            location = self.geocoding_service.geocode(destination)
            if location:
                location_name = location.display_name
                hotels.extend(self._search_overpass_hotels(location.lat, location.lon, min(timeout, 8)))

        if len(hotels) < 3:
            hotels.extend(self._destination_fallback_hotels(destination, budget, preference))

        ranked = self._rank_hotels(hotels, budget=budget, travel_type=travel_type, preference=preference)
        return {
            "source": "web",
            "location": location_name,
            "hotels": self._dedupe_hotels(ranked)[:10],
        }

    def _search_duckduckgo_hotels(self, destination: str, preference: str, timeout: int) -> List[Dict]:
        query = f"{destination} hotels {preference}".strip()
        return [
            {
                "name": item.get("name"),
                "type": "hotel",
                "rating_hint": "web",
                "summary": item.get("summary", ""),
                "url": item.get("url", ""),
                "source": "duckduckgo",
            }
            for item in self.duckduckgo.search(query, limit=7, timeout=timeout)
            if item.get("name")
        ]

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

    def _dedupe_hotels(self, hotels: List[Dict]) -> List[Dict]:
        seen = set()
        unique = []
        for hotel in hotels:
            name = str(hotel.get("name") or "").strip()
            if not name:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            unique.append(hotel)
        return unique

    def _destination_fallback_hotels(self, destination: str, budget: float, preference: str) -> List[Dict]:
        lower = (destination or "").lower()
        if "maldives" in lower:
            budget_note = "For a tight INR budget, prioritize local-island guesthouses over private-island resorts."
            return [
                {
                    "name": "Maafushi local-island guesthouses",
                    "type": "guest_house",
                    "rating_hint": "budget area",
                    "summary": f"{budget_note} Maafushi is strong for beach access, snorkel tours, and lower transfer costs.",
                    "source": "curated-fallback",
                },
                {
                    "name": "Hulhumale airport-area hotels",
                    "type": "hotel",
                    "rating_hint": "arrival night",
                    "summary": "Useful for late arrivals or early departures near Velana airport before moving to an island.",
                    "source": "curated-fallback",
                },
                {
                    "name": "Thulusdhoo guesthouses",
                    "type": "guest_house",
                    "rating_hint": "budget surf island",
                    "summary": "Good for a casual beach base with surf, cafes, and public ferry/speedboat access.",
                    "source": "curated-fallback",
                },
                {
                    "name": "Gulhi beach guesthouses",
                    "type": "guest_house",
                    "rating_hint": "quiet budget island",
                    "summary": "Smaller local-island option near Maafushi for quieter beaches and simple seafood meals.",
                    "source": "curated-fallback",
                },
            ]

        return [
            {
                "name": f"{destination} central budget stay",
                "type": "hotel",
                "rating_hint": "fallback",
                "summary": f"Look near the main transport area and filter for {preference or 'clean, well-reviewed stays'}.",
                "source": "generic-fallback",
            }
        ]
