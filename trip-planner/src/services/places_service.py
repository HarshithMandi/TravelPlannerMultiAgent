import logging
from typing import Dict, List, Optional

import requests

from src.config.settings import settings
from src.services.geocoding_service import GeocodingService

logger = logging.getLogger(__name__)


class PlacesService:
    """Finds attractions via Wikipedia and OpenStreetMap Overpass."""

    def __init__(self, geocoding_service: Optional[GeocodingService] = None):
        self.geocoding_service = geocoding_service or GeocodingService()

    def search_places(self, destination: str, interests: List[str], timeout: int = 20) -> Dict:
        location = self.geocoding_service.geocode(destination)
        if not location:
            return {"source": "fallback", "places": []}

        places = []
        places.extend(self._search_wikipedia(destination, timeout))
        places.extend(self._search_overpass(location.lat, location.lon, timeout))

        if settings.OPENTRIPMAP_API_KEY:
            places.extend(self._search_opentripmap(location.lat, location.lon, timeout))

        ranked = self._rank_places(places, interests)
        return {
            "source": "web",
            "location": location.display_name,
            "requested_interests": interests,
            "places": ranked[:10],
        }

    def _search_wikipedia(self, destination: str, timeout: int) -> List[Dict]:
        url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": f"{destination} tourist attractions",
            "format": "json",
            "srlimit": 5,
        }
        headers = {"User-Agent": "multi-agent-trip-planner/1.0", "Accept": "application/json"}
        try:
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
            results = response.json().get("query", {}).get("search", [])
            return [
                {
                    "name": item.get("title"),
                    "type": "wikipedia",
                    "summary": item.get("snippet", ""),
                    "source": "wikipedia",
                }
                for item in results
            ]
        except Exception as exc:
            logger.warning("Wikipedia search failed: %s", exc)
            return []

    def _search_overpass(self, lat: float, lon: float, timeout: int) -> List[Dict]:
        query = f"""
        [out:json][timeout:20];
        (
          node(around:5000,{lat},{lon})[tourism=attraction];
          node(around:5000,{lat},{lon})[historic=yes];
          node(around:5000,{lat},{lon})[leisure=park];
          node(around:5000,{lat},{lon})[natural=beach];
          node(around:5000,{lat},{lon})[amenity=restaurant];
          node(around:5000,{lat},{lon})[amenity=bar];
          way(around:5000,{lat},{lon})[tourism=attraction];
          way(around:5000,{lat},{lon})[historic=yes];
          way(around:5000,{lat},{lon})[leisure=park];
          way(around:5000,{lat},{lon})[natural=beach];
        );
        out center tags;
        """
        headers = {"User-Agent": "multi-agent-trip-planner/1.0", "Accept": "application/json"}
        try:
            response = requests.post("https://overpass-api.de/api/interpreter", data={"data": query}, headers=headers, timeout=timeout)
            response.raise_for_status()
            elements = response.json().get("elements", [])
            results = []
            for element in elements[:30]:
                tags = element.get("tags", {})
                name = tags.get("name")
                if not name:
                    continue
                place_type = tags.get("tourism") or tags.get("historic") or tags.get("leisure") or tags.get("natural") or tags.get("amenity") or "attraction"
                summary = tags.get("description") or tags.get("cuisine") or tags.get("operator") or tags.get("name:en") or ""
                results.append(
                    {
                        "name": name,
                        "type": place_type,
                        "summary": summary,
                        "source": "overpass",
                    }
                )
            return results
        except Exception as exc:
            logger.warning("Overpass search failed: %s", exc)
            return []

    def _search_opentripmap(self, lat: float, lon: float, timeout: int) -> List[Dict]:
        url = "https://api.opentripmap.com/0.1/en/places/radius"
        params = {
            "radius": 5000,
            "lon": lon,
            "lat": lat,
            "rate": 3,
            "format": "json",
            "apikey": settings.OPENTRIPMAP_API_KEY,
        }
        headers = {"User-Agent": "multi-agent-trip-planner/1.0", "Accept": "application/json"}
        try:
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
            return [
                {
                    "name": item.get("name"),
                    "type": "opentripmap",
                    "summary": item.get("kinds", ""),
                    "source": "opentripmap",
                }
                for item in response.json()[:10]
                if item.get("name")
            ]
        except Exception as exc:
            logger.warning("OpenTripMap search failed: %s", exc)
            return []

    def _rank_places(self, places: List[Dict], interests: List[str]) -> List[Dict]:
        interest_blob = " ".join(interests).lower()

        def score(place: Dict) -> int:
            blob = f"{place.get('name', '')} {place.get('type', '')} {place.get('summary', '')}".lower()
            return sum(1 for interest in interests if interest.lower() in blob or interest.lower() in interest_blob)

        return sorted(places, key=score, reverse=True)
