import logging
from typing import Dict, List, Optional
import re

import requests

from src.config.settings import settings
from src.services.duckduckgo_service import DuckDuckGoSearchService
from src.services.geocoding_service import GeocodingService

logger = logging.getLogger(__name__)


class PlacesService:
    """Finds attractions via Wikipedia and OpenStreetMap Overpass."""

    def __init__(self, geocoding_service: Optional[GeocodingService] = None):
        self.geocoding_service = geocoding_service or GeocodingService()
        self.duckduckgo = DuckDuckGoSearchService()

    def search_places(self, destination: str, interests: List[str], timeout: int = 12) -> Dict:
        places = []
        places.extend(self._search_duckduckgo(destination, interests, min(timeout, 6)))
        places.extend(self._search_wikipedia(destination, min(timeout, 6)))

        location = self.geocoding_service.geocode(destination)
        if location and len(places) < 8:
            places.extend(self._search_overpass_area(destination, min(timeout, 8)))
            places.extend(self._search_overpass(location.lat, location.lon, min(timeout, 8), destination=destination))

            if settings.OPENTRIPMAP_API_KEY:
                places.extend(self._search_opentripmap(location.lat, location.lon, min(timeout, 8)))

            if len(self._dedupe_places(places)) < 5:
                places.extend(self._search_wikipedia_geosearch(location.lat, location.lon, min(timeout, 6)))

        places = self._dedupe_places(places)
        api_places = [place for place in places if "fallback" not in str(place.get("source", ""))]
        if len(api_places) < 3:
            places.extend(self._destination_fallback_places(destination, interests))

        ranked = self._rank_places(places, interests)
        return {
            "source": "web",
            "location": destination,
            "requested_interests": interests,
            "places": self._dedupe_places(ranked)[:10],
        }

    def _search_duckduckgo(self, destination: str, interests: List[str], timeout: int) -> List[Dict]:
        interest_text = " ".join(interests or [])
        queries = [
            f"{destination} tourist attractions {interest_text}",
            f"{destination} best places to visit",
            f"{destination} beaches islands sightseeing",
        ]
        results: List[Dict] = []
        for query in queries:
            for item in self.duckduckgo.search(query.strip(), limit=6, timeout=timeout):
                if not self._is_candidate_place(destination, item.get("name"), item.get("summary"), require_destination=True):
                    continue
                results.append({**item, "type": "attraction", "source": item.get("source", "duckduckgo")})
        return self._dedupe_places(results)

    def _search_wikipedia(self, destination: str, timeout: int) -> List[Dict]:
        url = "https://en.wikipedia.org/w/api.php"
        headers = {"User-Agent": "multi-agent-trip-planner/1.0", "Accept": "application/json"}
        titles: List[str] = []
        for query in self._wikipedia_search_queries(destination):
            try:
                params = {
                    "action": "query",
                    "list": "search",
                    "srsearch": query,
                    "format": "json",
                    "srlimit": 8,
                }
                response = requests.get(url, params=params, headers=headers, timeout=timeout)
                response.raise_for_status()
                for item in response.json().get("query", {}).get("search", []):
                    title = str(item.get("title") or "").strip()
                    snippet = self._clean_text(item.get("snippet", ""))
                    if self._is_candidate_place(destination, title, snippet, require_destination=True):
                        titles.append(title)
            except Exception as exc:
                logger.warning("Wikipedia search query failed for %r: %s", query, exc)

        for category in self._wikipedia_categories(destination):
            titles.extend(self._search_wikipedia_category(category, timeout))

        return self._fetch_wikipedia_pages(titles, timeout, destination=destination)

    def _search_wikipedia_category(self, category: str, timeout: int) -> List[str]:
        url = "https://en.wikipedia.org/w/api.php"
        headers = {"User-Agent": "multi-agent-trip-planner/1.0", "Accept": "application/json"}
        params = {
            "action": "query",
            "list": "categorymembers",
            "cmtitle": category,
            "cmtype": "page",
            "cmlimit": 15,
            "format": "json",
        }
        try:
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            if response.status_code == 429:
                logger.info("Wikipedia geosearch rate-limited; skipping optional geosearch.")
                return []
            response.raise_for_status()
            return [
                item.get("title")
                for item in response.json().get("query", {}).get("categorymembers", [])
                if self._is_candidate_place("", item.get("title"), "")
            ]
        except Exception:
            return []

    def _search_wikipedia_geosearch(self, lat: float, lon: float, timeout: int) -> List[Dict]:
        url = "https://en.wikipedia.org/w/api.php"
        headers = {"User-Agent": "multi-agent-trip-planner/1.0", "Accept": "application/json"}
        params = {
            "action": "query",
            "list": "geosearch",
            "gscoord": f"{lat}|{lon}",
            "gsradius": 30000,
            "gslimit": 15,
            "format": "json",
        }
        try:
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
            titles = [
                item.get("title")
                for item in response.json().get("query", {}).get("geosearch", [])
                if self._is_candidate_place("", item.get("title"), "")
            ]
            return self._fetch_wikipedia_pages(titles, timeout)
        except Exception as exc:
            logger.info("Wikipedia geosearch unavailable; continuing with other place APIs: %s", exc)
            return []

    def _fetch_wikipedia_pages(self, titles: List[str], timeout: int, destination: str = "") -> List[Dict]:
        titles = [str(title or "").strip() for title in titles if title]
        titles = list(dict.fromkeys(titles))[:12]
        if not titles:
            return []

        url = "https://en.wikipedia.org/w/api.php"
        headers = {"User-Agent": "multi-agent-trip-planner/1.0", "Accept": "application/json"}
        params = {
            "action": "query",
            "prop": "extracts|coordinates|pageprops",
            "exintro": "1",
            "explaintext": "1",
            "titles": "|".join(titles),
            "format": "json",
        }
        try:
            response = requests.get(url, params=params, headers=headers, timeout=timeout)
            response.raise_for_status()
            pages = response.json().get("query", {}).get("pages", {})
            results = []
            for page in pages.values():
                title = page.get("title")
                summary = self._clean_text(page.get("extract", ""))
                if not self._is_candidate_place(destination, title, summary, require_destination=bool(destination)):
                    continue
                result = {
                    "name": title,
                    "type": self._infer_place_type(title, summary),
                    "summary": summary[:320],
                    "source": "wikipedia",
                }
                coords = page.get("coordinates") or []
                if coords:
                    result["lat"] = coords[0].get("lat")
                    result["lon"] = coords[0].get("lon")
                results.append(result)
            return results
        except Exception as exc:
            logger.warning("Wikipedia page enrichment failed: %s", exc)
            return []

    def _search_overpass(self, lat: float, lon: float, timeout: int, destination: str = "") -> List[Dict]:
        radius = 25000 if any(term in (destination or "").lower() for term in ["maldives", "island", "islands"]) else 8000
        query = f"""
        [out:json][timeout:20];
        (
          node(around:{radius},{lat},{lon})[tourism=attraction];
          node(around:{radius},{lat},{lon})[tourism=museum];
          node(around:{radius},{lat},{lon})[tourism=viewpoint];
          node(around:{radius},{lat},{lon})[historic];
          node(around:{radius},{lat},{lon})[leisure=park];
          node(around:{radius},{lat},{lon})[natural=beach];
          node(around:{radius},{lat},{lon})[place=island];
          way(around:{radius},{lat},{lon})[tourism=attraction];
          way(around:{radius},{lat},{lon})[tourism=museum];
          way(around:{radius},{lat},{lon})[tourism=viewpoint];
          way(around:{radius},{lat},{lon})[historic];
          way(around:{radius},{lat},{lon})[leisure=park];
          way(around:{radius},{lat},{lon})[natural=beach];
          way(around:{radius},{lat},{lon})[place=island];
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

    def _search_overpass_area(self, destination: str, timeout: int) -> List[Dict]:
        destination = str(destination or "").strip()
        if not destination:
            return []
        escaped = destination.replace('"', '\\"')
        query = f"""
        [out:json][timeout:20];
        area["name"="{escaped}"]["boundary"="administrative"]->.searchArea;
        (
          node(area.searchArea)[tourism~"attraction|museum|viewpoint"];
          node(area.searchArea)[historic];
          node(area.searchArea)[natural=beach];
          node(area.searchArea)[place=island];
          way(area.searchArea)[tourism~"attraction|museum|viewpoint"];
          way(area.searchArea)[historic];
          way(area.searchArea)[natural=beach];
          way(area.searchArea)[place=island];
        );
        out center tags 60;
        """
        headers = {"User-Agent": "multi-agent-trip-planner/1.0", "Accept": "application/json"}
        try:
            response = requests.post("https://overpass-api.de/api/interpreter", data={"data": query}, headers=headers, timeout=timeout)
            response.raise_for_status()
            results = []
            for element in response.json().get("elements", [])[:60]:
                tags = element.get("tags", {})
                name = tags.get("name") or tags.get("name:en")
                if not name or self._is_spam_title(str(name)):
                    continue
                place_type = tags.get("tourism") or tags.get("historic") or tags.get("natural") or tags.get("place") or "attraction"
                summary = tags.get("description") or tags.get("wikipedia") or f"{place_type} in {destination}"
                item = {
                    "name": name,
                    "type": place_type,
                    "summary": summary,
                    "source": "overpass",
                }
                center = element.get("center") or {}
                item["lat"] = element.get("lat") or center.get("lat")
                item["lon"] = element.get("lon") or center.get("lon")
                results.append(item)
            return results
        except Exception as exc:
            logger.warning("Overpass area search failed for %s: %s", destination, exc)
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
            value = sum(2 for interest in interests if interest.lower() in blob or interest.lower() in interest_blob)
            if place.get("lat") and place.get("lon"):
                value += 2
            if place.get("summary"):
                value += 1
            source = place.get("source")
            if source == "wikipedia":
                value += 4
            if source in {"overpass", "opentripmap"}:
                value += 1
            if "fallback" in str(source):
                value -= 5
            return value

        return sorted(places, key=score, reverse=True)

    def _dedupe_places(self, places: List[Dict]) -> List[Dict]:
        seen = set()
        unique = []
        for place in places:
            name = str(place.get("name") or "").strip()
            if not name:
                continue
            key = re.sub(r"\W+", "", name.lower())
            if key in seen:
                continue
            seen.add(key)
            unique.append(place)
        return unique

    def _destination_fallback_places(self, destination: str, interests: List[str]) -> List[Dict]:
        lower = (destination or "").lower()
        if "maldives" in lower:
            return [
                {
                    "name": "Maafushi Island",
                    "type": "local island beach",
                    "summary": "Budget-friendly local island with bikini beach, reef trips, sandbank tours, and evening cafes.",
                    "best_for": "beaches, budget stays, water activities",
                    "source": "curated-fallback",
                },
                {
                    "name": "Vaadhoo Island",
                    "type": "beach",
                    "summary": "Known for bioluminescent shoreline sightings after dark; best treated as weather- and season-dependent.",
                    "best_for": "night beach walk, photography",
                    "source": "curated-fallback",
                },
                {
                    "name": "Male Friday Mosque",
                    "type": "heritage",
                    "summary": "Historic coral-stone mosque in Male; dress modestly and pair it with the nearby old quarter.",
                    "best_for": "culture, sightseeing",
                    "source": "curated-fallback",
                },
                {
                    "name": "National Museum, Male",
                    "type": "museum",
                    "summary": "Compact museum covering Maldivian royal, Buddhist, and Islamic-era history; useful on a rainy day.",
                    "best_for": "culture, rain backup",
                    "source": "curated-fallback",
                },
                {
                    "name": "Hulhumale Beach",
                    "type": "beach",
                    "summary": "Accessible beach near Velana airport with cafes and simple sunset walks before or after island transfers.",
                    "best_for": "arrival day, beach walk",
                    "source": "curated-fallback",
                },
                {
                    "name": "Banana Reef",
                    "type": "reef",
                    "summary": "Classic North Male Atoll dive and snorkel area with coral formations and reef fish.",
                    "best_for": "snorkeling, diving",
                    "source": "curated-fallback",
                },
                {
                    "name": "Artificial Beach, Male",
                    "type": "beach",
                    "summary": "City beach option for a short Male stop, with casual food spots nearby.",
                    "best_for": "short city stop, evening walk",
                    "source": "curated-fallback",
                },
            ]

        interest_text = ", ".join([str(x) for x in interests if x]) or "sightseeing"
        return [
            {
                "name": f"{destination} historic center",
                "type": "sightseeing",
                "summary": f"Use this as a half-day walking area for architecture, local markets, and {interest_text}.",
                "best_for": "orientation walk",
                "source": "generic-fallback",
            },
            {
                "name": f"{destination} main market area",
                "type": "local market",
                "summary": "Good for local snacks, souvenirs, and a less scripted view of daily life.",
                "best_for": "food, shopping",
                "source": "generic-fallback",
            },
            {
                "name": f"{destination} waterfront or viewpoint",
                "type": "viewpoint",
                "summary": "Schedule around sunset and keep it flexible if weather changes.",
                "best_for": "photos, relaxed evening",
                "source": "generic-fallback",
            },
        ]

    def _is_spam_title(self, title: str) -> bool:
        lower = (title or "").lower().strip()
        spam_prefixes = [
            "list of ",
            "lists of ",
            "outline of",
            "category:",
        ]
        if any(lower.startswith(p) for p in spam_prefixes):
            return True
        if lower in {"travel", "guide", "wikipedia", "attractions", "tourist attractions"}:
            return True
        if lower in {"resort island", "wildlife of the maldives"}:
            return True
        if lower.startswith("tourism in "):
            return True
        spam_terms = [
            "tourism in india",
            "visa policy",
            "economy of",
            "history of",
            "outline of",
            "geography of",
            "demographics of",
            "transport in",
            "airport",
            "airlines",
        ]
        if any(term in lower for term in spam_terms):
            return True
        return False

    def _is_candidate_place(self, destination: str, name: str, summary: str, require_destination: bool = False) -> bool:
        name = str(name or "").strip()
        summary = str(summary or "").strip()
        if not name or self._is_spam_title(name):
            return False
        blob = f"{name} {summary}".lower()
        dest = (destination or "").lower().strip()
        if require_destination and dest and not self._has_destination_context(dest, name.lower(), summary.lower()):
            return False
        place_terms = [
            "island",
            "beach",
            "reef",
            "mosque",
            "museum",
            "park",
            "atoll",
            "resort",
            "temple",
            "fort",
            "palace",
            "market",
            "viewpoint",
            "lagoon",
            "national",
            "heritage",
        ]
        if any(term in blob for term in place_terms):
            return True
        if dest and dest in blob and len(name.split()) <= 6:
            return True
        if not dest and len(name.split()) <= 6:
            return True
        return False

    def _has_destination_context(self, dest: str, name: str, summary: str) -> bool:
        if dest in name:
            return True
        compact_dest = dest[4:] if dest.startswith("the ") else dest
        context_phrases = [
            f"in {dest}",
            f"in the {compact_dest}",
            f"of {dest}",
            f"of the {compact_dest}",
            f"{compact_dest} archipelago",
            f"republic of {compact_dest}",
            f"northern {compact_dest}",
            f"southern {compact_dest}",
        ]
        return any(phrase in summary for phrase in context_phrases)

    def _wikipedia_search_queries(self, destination: str) -> List[str]:
        return [
            f'"{destination}" tourist attractions',
            f'"{destination}" beaches islands reefs',
            f'"{destination}" museums mosques landmarks',
        ]

    def _wikipedia_categories(self, destination: str) -> List[str]:
        dest = (destination or "").strip()
        variants = [dest]
        article_variant = dest[4:] if dest.lower().startswith("the ") else f"the {dest}"
        categories = []
        for variant in [*variants, article_variant]:
            categories.append(f"Category:Tourist attractions in {variant}")
            categories.append(f"Category:Islands of {variant}")
            categories.append(f"Category:Beaches of {variant}")
        return categories

    def _infer_place_type(self, name: str, summary: str) -> str:
        blob = f"{name} {summary}".lower()
        for term in ["beach", "reef", "island", "museum", "mosque", "park", "market", "atoll", "viewpoint"]:
            if term in blob:
                return term
        if "historic" in blob or "heritage" in blob:
            return "heritage"
        return "attraction"

    def _is_relevant_wikipedia_result(self, destination: str, item: Dict) -> bool:
        title = str(item.get("title") or "").strip()
        snippet = self._clean_text(item.get("snippet", ""))
        if not self._is_candidate_place(destination, title, snippet, require_destination=True):
            return False
        return True

    def _clean_text(self, value: str) -> str:
        if not value:
            return ""
        cleaned = re.sub(r"<[^>]+>", " ", str(value))
        cleaned = re.sub(r"&#?\w+;", " ", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned)
        return cleaned.strip()
