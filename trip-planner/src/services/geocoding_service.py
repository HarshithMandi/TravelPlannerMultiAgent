import logging
from dataclasses import dataclass
from typing import Dict, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Location:
    query: str
    lat: float
    lon: float
    display_name: str
    source: str = "nominatim"


class GeocodingService:
    """Geocodes location names using OpenStreetMap's Nominatim endpoint."""

    def __init__(self, user_agent: str = "multi-agent-trip-planner/1.0"):
        self.user_agent = user_agent

    def geocode(self, query: str, timeout: int = 20) -> Optional[Location]:
        if not query:
            return None

        url = "https://nominatim.openstreetmap.org/search"
        params = {"q": query, "format": "jsonv2", "limit": 1}
        headers = {"User-Agent": self.user_agent}

        try:
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            if not data:
                return None
            item = data[0]
            return Location(
                query=query,
                lat=float(item["lat"]),
                lon=float(item["lon"]),
                display_name=item.get("display_name", query),
            )
        except Exception as exc:
            logger.warning("Geocoding failed for %s: %s", query, exc)
            return None
