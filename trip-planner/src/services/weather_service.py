import logging
from typing import Dict, Optional

import requests

from src.config.settings import settings
from src.services.geocoding_service import GeocodingService, Location

logger = logging.getLogger(__name__)


class WeatherService:
    """Fetches weather from OpenWeatherMap or Open-Meteo fallback."""

    def __init__(self, geocoding_service: Optional[GeocodingService] = None):
        self.geocoding_service = geocoding_service or GeocodingService()

    def fetch_weather(self, destination: str, timeout: int = 20) -> Dict:
        location = self.geocoding_service.geocode(destination)
        if not location:
            return {"source": "fallback", "summary": f"Could not geocode {destination}", "forecast": []}

        if settings.OPENWEATHERMAP_API_KEY:
            return self._fetch_openweathermap(location, timeout)

        return self._fetch_open_meteo(location, timeout)

    def _fetch_openweathermap(self, location: Location, timeout: int) -> Dict:
        url = "https://api.openweathermap.org/data/2.5/forecast"
        params = {
            "lat": location.lat,
            "lon": location.lon,
            "appid": settings.OPENWEATHERMAP_API_KEY,
            "units": "metric",
        }
        try:
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            items = data.get("list", [])[:5]
            forecast = [
                {
                    "time": item.get("dt_txt"),
                    "temp_c": item.get("main", {}).get("temp"),
                    "description": item.get("weather", [{}])[0].get("description"),
                }
                for item in items
            ]
            return {"source": "openweathermap", "location": location.display_name, "forecast": forecast}
        except Exception as exc:
            logger.warning("OpenWeatherMap fetch failed: %s", exc)
            return self._fetch_open_meteo(location, timeout)

    def _fetch_open_meteo(self, location: Location, timeout: int) -> Dict:
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": location.lat,
            "longitude": location.lon,
            "daily": "temperature_2m_max,temperature_2m_min,weathercode",
            "timezone": "auto",
        }
        try:
            response = requests.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            daily = data.get("daily", {})
            forecast = []
            for index, date in enumerate(daily.get("time", [])[:5]):
                forecast.append(
                    {
                        "date": date,
                        "temp_max_c": daily.get("temperature_2m_max", [None])[index],
                        "temp_min_c": daily.get("temperature_2m_min", [None])[index],
                        "weathercode": daily.get("weathercode", [None])[index],
                    }
                )
            return {"source": "open-meteo", "location": location.display_name, "forecast": forecast}
        except Exception as exc:
            logger.warning("Open-Meteo fetch failed: %s", exc)
            return {"source": "fallback", "location": location.display_name, "forecast": []}
