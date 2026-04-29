from datetime import datetime
import re
from typing import Dict, List

from src.state.schemas import TripPlannerState
from src.services.llm_service import SarvamLLMService


from typing import Optional


def run(state: TripPlannerState, llm_service: Optional[SarvamLLMService] = None) -> TripPlannerState:
    """Convert raw place, weather, transport, and hotel data into a realistic, coherent day plan."""

    trip_days = _trip_day_count(state.trip_preferences.get("start_date"), state.trip_preferences.get("end_date"))
    destination = str(state.trip_preferences.get("destination", "Destination"))
    interests = list(state.trip_preferences.get("places_of_interest", []) or [])

    # Use actual place data from web APIs, not synthetic interest-based titles
    real_places = _extract_real_places(
        state.places_data.get("places", []) if state.places_data else [],
        destination=destination,
    )

    weather_summary = _summarize_weather(state.weather_data)
    hotel_summary = _summarize_hotels(state.hotel_data)
    transport_summary = _summarize_transport(state.transport_data)

    # Build day plans using actual attractions
    itinerary_days: List[Dict] = []
    itinerary_notes: List[str] = []
    dining_options = _get_dining_suggestions(destination, interests)

    for day_index in range(trip_days):
        morning_idx = day_index % len(real_places) if real_places else 0
        afternoon_idx = (day_index + 1) % len(real_places) if len(real_places) > 1 else morning_idx
        
        morning_place = real_places[morning_idx] if real_places else {"name": f"Day {day_index + 1} in {destination}", "summary": "Explore highlights"}
        afternoon_place = real_places[afternoon_idx] if real_places else morning_place

        morning_name = morning_place.get("name", "").strip()
        afternoon_name = afternoon_place.get("name", "").strip()
        
        day_notes = []
        morning_summary = morning_place.get("summary", "").strip()
        morning_best_for = morning_place.get("best_for")
        if morning_summary and len(morning_summary) > 5:
            day_notes.append(f"Morning detail: {_shorten(morning_summary, 150)}")
        if morning_best_for:
            day_notes.append(f"Best for: {morning_best_for}")
        
        afternoon_summary = afternoon_place.get("summary", "").strip() if afternoon_place != morning_place else None
        if afternoon_summary and len(afternoon_summary) > 5:
            day_notes.append(f"Afternoon detail: {_shorten(afternoon_summary, 150)}")
        
        if weather_summary:
            day_notes.append(f"Weather: {weather_summary}")
        if hotel_summary:
            day_notes.append(f"Stay: {hotel_summary}")
        if day_index == 0 and transport_summary:
            day_notes.append(f"Transport: {transport_summary}")
        itinerary_notes.extend([f"Day {day_index + 1}: {note}" for note in day_notes if note])

        itinerary_days.append(
            {
                "day": day_index + 1,
                "title": morning_name or f"Day {day_index + 1}",
                "morning": morning_name or "Morning exploration",
                "afternoon": afternoon_name or "Afternoon activity",
                "evening": dining_options[day_index % len(dining_options)],
            }
        )

    state.itinerary = {
        "destination": destination,
        "trip_days": trip_days,
        "weather_summary": weather_summary,
        "hotel_summary": hotel_summary,
        "transport_summary": transport_summary,
        "days": itinerary_days,
        "notes": itinerary_notes,
    }

    reasoning = (
        f"Built a {trip_days}-day itinerary using {len(real_places)} real places (when available), "
        "and integrated weather/hotel/transport summaries as daily notes."
    )

    if llm_service is not None and getattr(llm_service, "enabled", False):
        try:
            llm_reason = llm_service.chat_text(
                system=(
                    "You are an itinerary planner. Provide a short rationale for the day-wise plan in 2 sentences."
                ),
                user=(
                    f"Prefs: {state.trip_preferences}\nWeather: {state.weather_data}\nHotels: {state.hotel_data}"
                    f"\nTransport: {state.transport_data}\nPlaces: {state.places_data}\nItinerary: {state.itinerary}"
                ),
                timeout=12,
            ).strip()
            if llm_reason:
                reasoning = llm_reason
        except Exception:
            pass

    state.agent_reasoning["itinerary_agent"] = reasoning
    return state


def _trip_day_count(start_date: str | None, end_date: str | None) -> int:
    try:
        if not start_date or not end_date:
            return 3
        start = datetime.fromisoformat(str(start_date)).date()
        end = datetime.fromisoformat(str(end_date)).date()
        return max(1, min((end - start).days + 1, 7))
    except Exception:
        return 3


def _extract_real_places(raw_places: List[Dict], destination: str) -> List[Dict]:
    """Extract and clean real places from web APIs, avoiding generic/spam titles."""
    real_places: List[Dict] = []
    destination_lower = destination.lower().strip()

    for place in raw_places:
        name = str(place.get("name") or place.get("title") or "").strip()
        summary = _clean_text(str(place.get("summary") or place.get("description") or "").strip())
        place_type = place.get("type") or place.get("source") or "attraction"

        if not name or _is_spam_title(name):
            continue

        # Allow any place that doesn't have a name overlap issue
        real_places.append({
            "name": name,
            "summary": summary or f"Visit this {place_type} in {destination}",
            "type": place_type,
            "best_for": place.get("best_for", ""),
            "source": place.get("source", "local"),
        })

    return real_places


def _get_dining_suggestions(destination: str, interests: List[str]) -> List[str]:
    """Generate diverse dining suggestions for each day."""
    suggestions = [
        f"Local seafood dinner by the coast" if "beach" in destination.lower() else f"Local cuisine in {destination}",
        f"Street food and local eatery tour" if interests else f"Casual dining in {destination}",
        f"Beachside shack or waterfront dining" if "beach" in destination.lower() else f"Regional specialties in {destination}",
        f"Fine dining or hotel restaurant" if "nightlife" in interests else f"Upscale dining in {destination}",
        f"Night market or pub crawl" if "nightlife" in interests else f"Evening dining and relaxation",
    ]
    return suggestions


def _shorten(value: str, limit: int) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _is_spam_title(title: str) -> bool:
    """Detect and reject spam/generic Wikipedia list pages."""
    lower = title.lower().strip()
    # Reject only truly generic list pages and unrelated entries
    spam_patterns = [
        "list of ",
        "lists of ",
        "outline of",
        "category:",
    ]
    # These are spam if they appear
    if any(lower.startswith(pattern) for pattern in spam_patterns):
        return True
    
    # Reject specific unrelated results
    if lower in {"travel", "guide", "wikipedia", "attractions"}:
        return True
    
    # Reject results for other destinations
    if any(x in lower for x in ["philippines", "mangaluru", "karnataka"]):
        return True
    
    return False


def _clean_text(value: str) -> str:
    if not value:
        return ""
    # Remove HTML tags and entity references
    cleaned = re.sub(r"<[^>]+>", " ", value)
    cleaned = re.sub(r"&#?\w+;", " ", cleaned)  # HTML entities like &#039;
    cleaned = re.sub(r"\s+", " ", cleaned)  # Collapse whitespace
    return cleaned.strip()


def _summarize_weather(weather_data: Dict) -> str:
    source = weather_data.get("source")
    forecast = weather_data.get("forecast") or []
    if not source or not forecast:
        return "No live forecast available"
    first = forecast[0]
    temp = first.get("temp_c") or first.get("temp_max_c")
    desc = first.get("description") or first.get("weathercode")
    if temp or desc:
        return f"{source}: {temp}°C, {desc}"
    return f"{source} forecast available"


def _summarize_hotels(hotel_data: Dict) -> str:
    suggestions = hotel_data.get("suggestions") or hotel_data.get("hotels") or []
    if not suggestions:
        return "No hotel recommendation available"
    first = suggestions[0]
    name = first.get("name") or first.get("title")
    return f"Stay near {name}" if name else "Hotel recommendation available"


def _summarize_transport(transport_data: Dict) -> str:
    recommendations = transport_data.get("recommendations") or transport_data.get("options") or []
    if not recommendations:
        return "No transport recommendation available"
    first = recommendations[0]
    mode = first.get("mode")
    reason = first.get("reason") or first.get("rationale")
    if mode and reason:
        return f"{mode} - {reason}"
    if mode:
        return str(mode)
    return "Transport recommendation available"

