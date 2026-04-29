import os
import textwrap
from typing import Dict, List, Tuple

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from src.state.schemas import TripPlannerState


def _safe_str(value) -> str:
    if value is None:
        return ""
    return str(value)


def _lines_from_kv(title: str, items: List[Tuple[str, str]]) -> List[str]:
    lines: List[str] = [title, "-" * 60]
    for key, value in items:
        text = _safe_str(value).strip()
        if text:
            lines.append(f"{key}: {text}")
    lines.append("")
    return lines


def _food_suggestions(destination: str, food_pref: str) -> Dict:
    dest = (destination or "").strip()
    pref = (food_pref or "").strip()
    suggestions = []
    if pref:
        suggestions.append(f"Try local spots known for: {pref}")
    suggestions.extend(
        [
            f"Ask locals for a popular meal set in {dest}" if dest else "Ask locals for a popular meal set",
            "Prefer busy stalls for fresher street food",
            "Carry electrolytes if trying spicy food",
        ]
    )
    return {"destination": dest, "suggestions": suggestions}


def _emergency_tips(destination: str, transport_pref: str, weather_data: Dict) -> Dict:
    dest = (destination or "").strip()
    mode = (transport_pref or "").strip()
    forecast = (weather_data or {}).get("forecast") or []
    first = forecast[0] if forecast else {}
    desc = _safe_str(first.get("description") or first.get("weathercode") or "").lower()
    rain_hint = any(word in desc for word in ["rain", "storm", "thunder"])

    tips = [
        "Save offline maps and your accommodation address",
        "Keep digital and paper copies of ID and tickets",
        "Use travel insurance if the trip is high-value",
        "Share your live location with a trusted contact",
    ]
    if mode in {"car", "bus"}:
        tips.append("Keep a basic first-aid kit and phone charger or power bank")
    if rain_hint:
        tips.append("Pack a rain jacket and waterproof bag for electronics")
    if dest:
        tips.append(f"Know the nearest hospital or clinic to your stay in {dest}")
    return {"destination": dest, "tips": tips}


def _travel_recommendations(prefs: Dict, itinerary: Dict) -> Dict:
    interests = prefs.get("places_of_interest") or []
    travel_type = _safe_str(prefs.get("travel_type") or "").strip()
    recs = [
        "Start days early to avoid crowds",
        "Keep one flexible slot daily for rest or delays",
        "Prefer pre-booking for popular attractions",
    ]
    if travel_type:
        recs.append(f"Plan pacing appropriate for: {travel_type}")
    if interests:
        recs.append(f"Prioritize attractions matching: {', '.join([_safe_str(x) for x in interests if x])}")
    if itinerary and itinerary.get("trip_days"):
        recs.append(f"Avoid overpacking activities across {itinerary.get('trip_days')} days")
    return {"recommendations": recs}


def _render_hotels(hotel_data: Dict) -> List[str]:
    hotels = (hotel_data or {}).get("suggestions") or (hotel_data or {}).get("hotels") or []
    lines = ["HOTEL(S) OF STAY", "-" * 60]
    if not hotels:
        lines.append("No hotel recommendations available")
        lines.append("")
        return lines

    for hotel in hotels[:10]:
        name = hotel.get("name") or "Hotel"
        summary = hotel.get("summary") or ""
        rating_hint = hotel.get("rating_hint") or hotel.get("stars") or ""
        hotel_type = hotel.get("type") or ""
        source = hotel.get("source") or ""
        suffix = f" ({rating_hint})" if rating_hint else ""
        lines.append(f"- {name}{suffix}")
        if hotel_type or source:
            lines.append(f"  Type/source: {hotel_type or 'stay'} / {source or 'web'}")
        if summary:
            lines.append(f"  {summary}")
    lines.append("")
    return lines


def _render_transport(transport_data: Dict) -> List[str]:
    route = (transport_data or {}).get("route") or {}
    recs = (transport_data or {}).get("recommendations") or []
    summary = (transport_data or {}).get("summary") or ""
    lines = ["FLIGHT INFORMATION TO AND FRO", "-" * 60]
    if summary:
        lines.append(f"Summary: {summary}")
    if route:
        lines.append(f"Route data source: {route.get('source', 'routing')}")
        if "road distance is not meaningful" not in summary.lower():
            lines.append(f"Distance (km): {route.get('distance_km')}")
            lines.append(f"Duration (min): {route.get('duration_min')}")
    else:
        lines.append("Route estimate unavailable")

    if recs:
        lines.append("Outbound options:")
        for rec in recs[:8]:
            mode = rec.get("mode") or ""
            reason = rec.get("reason") or ""
            lines.append(f"- {mode}: {reason}".strip(" :"))
        lines.append("Return options:")
        for rec in recs[:8]:
            mode = rec.get("mode") or ""
            reason = rec.get("reason") or ""
            lines.append(f"- {mode}: Same route in reverse; {reason}".strip(" :"))
    else:
        lines.append("No flight/transport suggestions available")
    lines.append("")
    return lines


def _render_places(places_data: Dict) -> List[str]:
    places = (places_data or {}).get("places") or []
    lines = ["PLACES TO VISIT IN THE AREA", "-" * 60]
    if not places:
        lines.append("No attractions found")
        lines.append("")
        return lines

    for place in places[:12]:
        name = place.get("name") or "Attraction"
        details = []
        if place.get("type"):
            details.append(place.get("type"))
        if place.get("best_for"):
            details.append(f"best for {place.get('best_for')}")
        if place.get("source"):
            details.append(f"source: {place.get('source')}")

        lines.append(f"- {name}")
        if details:
            lines.append(f"  {'; '.join(details)}")
        if place.get("summary"):
            lines.append(f"  {place.get('summary')}")
        if place.get("url"):
            lines.append(f"  {place.get('url')}")
    lines.append("")
    return lines


def _render_notes(
    itinerary: Dict,
    food: Dict,
    emergency: Dict,
    travel_recs: Dict,
    weather_data: Dict,
    budget_summary: Dict,
    prefs: Dict,
) -> List[str]:
    lines = ["NOTES", "-" * 60]
    notes = []
    notes.extend((itinerary or {}).get("notes") or [])
    notes.extend((travel_recs or {}).get("recommendations") or [])
    notes.extend((food or {}).get("suggestions") or [])
    notes.extend((emergency or {}).get("tips") or [])

    forecast = (weather_data or {}).get("forecast") or []
    if forecast:
        first = forecast[0]
        date = first.get("date") or first.get("time") or ""
        temp = first.get("temp_c") or first.get("temp_max_c") or ""
        desc = first.get("description") or first.get("weathercode") or ""
        notes.append(f"Weather snapshot: {date} {temp}C {desc}".strip())

    est = (budget_summary or {}).get("estimated_total")
    limit = prefs.get("budget")
    if est is not None or limit is not None:
        notes.append(f"Budget: estimated total {est}; limit {limit}. Keep a 10-15% buffer for food, transfers, and local transport.")

    seen = set()
    unique_notes = []
    for note in notes:
        text = _safe_str(note).strip()
        if text and text not in seen:
            seen.add(text)
            unique_notes.append(text)

    if not unique_notes:
        lines.append("No additional notes available")
    else:
        for note in unique_notes[:30]:
            lines.append(f"- {note}")
    lines.append("")
    return lines


def _write_pdf(path: str, lines: List[str]) -> None:
    pdf = canvas.Canvas(path, pagesize=A4)
    _, page_height = A4
    x = 40
    y = page_height - 50
    line_height = 14

    pdf.setFont("Helvetica", 10)
    for line in _wrap_lines(lines):
        if y < 50:
            pdf.showPage()
            pdf.setFont("Helvetica", 10)
            y = page_height - 50
        pdf.drawString(x, y, _pdf_safe_text(line))
        y -= line_height
    pdf.save()


def _wrap_lines(lines: List[str], width: int = 92) -> List[str]:
    wrapped: List[str] = []
    for line in lines:
        text = _safe_str(line)
        if not text:
            wrapped.append("")
            continue
        wrapped.extend(textwrap.wrap(text, width=width) or [""])
    return wrapped


def _pdf_safe_text(value) -> str:
    text = _safe_str(value)
    replacements = {
        "₹": "INR ",
        "→": "->",
        "°": " deg",
        "–": "-",
        "—": "-",
        "’": "'",
        "“": '"',
        "”": '"',
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def generate_reports(state: TripPlannerState) -> Dict[str, str]:
    out_dir = os.path.join(os.getcwd(), "output")
    os.makedirs(out_dir, exist_ok=True)

    pdf_path = os.path.join(out_dir, f"trip_{state.session_id}.pdf")

    prefs = state.trip_preferences or {}
    destination = _safe_str(prefs.get("destination") or "")
    transport_pref = _safe_str(prefs.get("transport_pref") or "")
    food_pref = _safe_str(prefs.get("food_pref") or "")

    itinerary = state.itinerary or {}
    food = state.food_recommendations or _food_suggestions(destination, food_pref)
    emergency = state.emergency_tips or _emergency_tips(destination, transport_pref, state.weather_data or {})
    travel_recs = _travel_recommendations(prefs, itinerary)

    state.food_recommendations = food
    state.emergency_tips = emergency

    lines: List[str] = []
    lines.extend(["=" * 60, "TRIP PLANNER REPORT", "=" * 60])
    lines.append(f"Session ID: {state.session_id}")
    lines.append("")
    lines.extend(
        _lines_from_kv(
            "TRIP INFORMATION",
            [
                ("From", f"{prefs.get('source')} -> {prefs.get('destination')}"),
                ("Dates", f"{prefs.get('start_date')} to {prefs.get('end_date')}"),
                ("Budget", f"INR {prefs.get('budget'):,}" if isinstance(prefs.get("budget"), (int, float)) else _safe_str(prefs.get("budget"))),
                ("Travelers", _safe_str(prefs.get("travelers"))),
                ("Travel Type", _safe_str(prefs.get("travel_type"))),
                ("Hotel Preference", _safe_str(prefs.get("hotel_pref"))),
                ("Food Preference", _safe_str(prefs.get("food_pref"))),
                ("Transport Preference", _safe_str(prefs.get("transport_pref"))),
                ("Interests", ", ".join([_safe_str(x) for x in (prefs.get("places_of_interest") or []) if x])),
                ("Luxury Level", _safe_str(prefs.get("luxury"))),
            ],
        )
    )
    lines.extend(_render_hotels(state.hotel_data or {}))
    lines.extend(_render_transport(state.transport_data or {}))
    lines.extend(_render_places(state.places_data or {}))
    lines.extend(_render_notes(itinerary, food, emergency, travel_recs, state.weather_data or {}, state.budget_summary or {}, prefs))
    lines.extend(["=" * 60, "END OF REPORT", "=" * 60])

    _write_pdf(pdf_path, lines)
    return {"pdf_path": pdf_path}


def generate_pdf_report(state: TripPlannerState) -> str:
    return generate_reports(state)["pdf_path"]
