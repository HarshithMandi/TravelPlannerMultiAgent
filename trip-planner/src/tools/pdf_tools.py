import os
import json
import logging
from typing import Any, Dict, Iterable, List, Sequence, Tuple
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from src.config.settings import settings
from src.services.llm_service import SarvamLLMService
from src.state.schemas import TripPlannerState

logger = logging.getLogger(__name__)


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _compact_text(value: Any) -> str:
    text = _safe_str(value)
    replacements = {
        "\r": " ",
        "\n": " ",
        "\t": " ",
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
    return " ".join(text.split())


def _format_number(value: Any) -> str:
    try:
        if value is None or value == "":
            return "N/A"
        if isinstance(value, bool):
            return "Yes" if value else "No"
        if isinstance(value, (int, float)):
            if isinstance(value, float) and value.is_integer():
                value = int(value)
            return f"{value:,}"
    except Exception:
        pass
    return _compact_text(value) or "N/A"


def _format_money(value: Any) -> str:
    if value is None or value == "":
        return "N/A"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and value.is_integer():
            value = int(value)
        return f"INR {value:,}"
    return _compact_text(value)


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value
    if value in (None, ""):
        return []
    return [value]


def _styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#17324d"),
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportSubtitle",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#4b5563"),
            spaceAfter=10,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionHeading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=13,
            leading=16,
            textColor=colors.HexColor("#0f3b57"),
            spaceBefore=6,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionNote",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#4b5563"),
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableHeader",
            parent=styles["BodyText"],
            fontName="Helvetica-Bold",
            fontSize=9,
            leading=11,
            textColor=colors.white,
        )
    )
    styles.add(
        ParagraphStyle(
            name="TableBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=10.5,
            textColor=colors.black,
        )
    )
    styles.add(
        ParagraphStyle(
            name="BulletBody",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8.5,
            leading=11,
            leftIndent=10,
            firstLineIndent=-6,
            spaceAfter=2,
        )
    )
    return styles


def _section_heading(title: str, styles) -> List[Any]:
    return [Paragraph(title, styles["SectionHeading"]), Spacer(1, 3)]


def _table(rows: Sequence[Sequence[Any]], styles, col_widths: Sequence[float], header_rows: int = 1) -> Table:
    data: List[List[Any]] = []
    for row_index, row in enumerate(rows):
        style_name = "TableHeader" if row_index < header_rows else "TableBody"
        data.append([Paragraph(escape(_compact_text(cell) or "N/A"), styles[style_name]) for cell in row])

    table = Table(data, colWidths=list(col_widths), repeatRows=header_rows)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#17324d")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.5),
                ("LEADING", (0, 0), (-1, -1), 10.5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.HexColor("#eef3f7")]),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#b6c2cf")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]
        )
    )
    return table


def _kv_rows(pairs: Iterable[Tuple[str, Any]]) -> List[List[Any]]:
    return [[key, value] for key, value in pairs]


def _page_decorations(canvas, doc):
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(colors.HexColor("#d0d7de"))
    canvas.setLineWidth(0.6)
    canvas.line(doc.leftMargin, height - 18 * mm, width - doc.rightMargin, height - 18 * mm)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#6b7280"))
    canvas.drawString(doc.leftMargin, 10 * mm, "Trip Planner Report")
    canvas.drawRightString(width - doc.rightMargin, 10 * mm, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


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


def _generate_plaintext_report(state: TripPlannerState) -> str:
    """Generate a comprehensive plaintext report from the trip state."""
    prefs = state.trip_preferences or {}
    transport_data = state.transport_data or {}
    flight_details = transport_data.get("flight_details") or {}
    hotels = (state.hotel_data or {}).get("suggestions") or (state.hotel_data or {}).get("hotels") or []
    places = (state.places_data or {}).get("places") or []
    itinerary = state.itinerary or {}
    weather = state.weather_data or {}
    budget = state.budget_summary or {}

    lines = []

    # Trip Overview
    lines.append("=" * 80)
    lines.append("TRIP PLANNER REPORT")
    lines.append("=" * 80)
    lines.append("")
    
    lines.append("TRIP OVERVIEW")
    lines.append("-" * 40)
    lines.append(f"From: {prefs.get('source') or 'N/A'}")
    lines.append(f"To: {prefs.get('destination') or 'N/A'}")
    lines.append(f"Start Date: {prefs.get('start_date') or 'N/A'}")
    lines.append(f"End Date: {prefs.get('end_date') or 'N/A'}")
    lines.append(f"Budget: INR {prefs.get('budget') or 'N/A'}")
    lines.append(f"Number of Travelers: {prefs.get('travelers') or 'N/A'}")
    lines.append(f"Travel Type: {prefs.get('travel_type') or 'N/A'}")
    lines.append(f"Hotel Preference: {prefs.get('hotel_pref') or 'N/A'}")
    lines.append(f"Food Preference: {prefs.get('food_pref') or 'N/A'}")
    lines.append(f"Transport Preference: {prefs.get('transport_pref') or 'N/A'}")
    interests_str = ", ".join(_as_list(prefs.get("places_of_interest"))) or "N/A"
    lines.append(f"Interests: {interests_str}")
    lines.append("")

    # Flight Details
    lines.append("FLIGHT & TRANSPORTATION")
    lines.append("-" * 40)
    lines.append(f"Recommended Mode: {flight_details.get('recommended_mode') or 'N/A'}")
    lines.append(f"Reason: {flight_details.get('reason') or 'N/A'}")
    lines.append(f"Summary: {flight_details.get('summary') or transport_data.get('summary') or 'N/A'}")
    lines.append("")
    
    flight_recs = flight_details.get("flight_recommendations") or []
    if flight_recs:
        lines.append("Flight Recommendations:")
        for i, flight in enumerate(flight_recs[:6], 1):
            lines.append(f"  Option {i}: {flight.get('airline', 'N/A')} - Flight {flight.get('flight_number', 'N/A')}")
            lines.append(f"    Route: {flight.get('from', 'N/A')} → {flight.get('to', 'N/A')}")
            lines.append(f"    Departure: {flight.get('departure_time', 'N/A')}, Arrival: {flight.get('arrival_time', 'N/A')}")
            lines.append(f"    Duration: {flight.get('duration_min', 'N/A')} minutes")
            lines.append("")

    # Hotels
    lines.append("ACCOMMODATION OPTIONS")
    lines.append("-" * 40)
    if hotels:
        for i, hotel in enumerate(hotels[:10], 1):
            lines.append(f"{i}. {hotel.get('name', 'N/A')}")
            lines.append(f"   Type: {hotel.get('type', 'N/A')}")
            lines.append(f"   Rating: {hotel.get('rating_hint', 'N/A')}")
            lines.append(f"   Details: {hotel.get('summary', 'N/A')}")
            lines.append("")
    else:
        lines.append("No hotel recommendations available.")
        lines.append("")

    # Tourist Attractions
    lines.append("MUST-VISIT ATTRACTIONS & PLACES")
    lines.append("-" * 40)
    if places:
        for i, place in enumerate(places[:15], 1):
            lines.append(f"{i}. {place.get('name', 'N/A')}")
            lines.append(f"   Type: {place.get('type', 'N/A')}")
            lines.append(f"   Best For: {place.get('best_for', 'N/A')}")
            lines.append(f"   Description: {place.get('summary', 'N/A')}")
            lines.append("")
    else:
        lines.append("No tourist attractions found.")
        lines.append("")

    # Itinerary
    lines.append("SUGGESTED ITINERARY")
    lines.append("-" * 40)
    itinerary_text = itinerary.get("itinerary") or itinerary.get("plan") or ""
    if itinerary_text:
        lines.append(str(itinerary_text))
        lines.append("")
    else:
        lines.append("No detailed itinerary available.")
        lines.append("")

    # Weather
    if weather:
        lines.append("WEATHER FORECAST")
        lines.append("-" * 40)
        forecast = weather.get("forecast") or []
        if forecast:
            for entry in forecast[:5]:
                lines.append(f"Date: {entry.get('date', 'N/A')}")
                lines.append(f"Condition: {entry.get('description', entry.get('weathercode', 'N/A'))}")
                lines.append(f"Temp: {entry.get('max_temp')}°C - {entry.get('min_temp')}°C")
                lines.append("")

    # Budget
    if budget:
        lines.append("BUDGET BREAKDOWN")
        lines.append("-" * 40)
        lines.append(f"Total Budget: INR {budget.get('total_budget', 'N/A')}")
        lines.append(f"Estimated Flight: INR {budget.get('flight_cost', 'N/A')}")
        lines.append(f"Estimated Hotel (per night): INR {budget.get('hotel_per_night', 'N/A')}")
        lines.append(f"Estimated Food (per day): INR {budget.get('food_per_day', 'N/A')}")
        lines.append(f"Remaining for Activities: INR {budget.get('activity_budget', 'N/A')}")
        lines.append("")

    # Emergency Tips
    emergency = state.emergency_tips or {}
    if emergency:
        lines.append("TRAVEL SAFETY & EMERGENCY TIPS")
        lines.append("-" * 40)
        tips = emergency.get("tips") or []
        for tip in tips:
            lines.append(f"• {tip}")
        lines.append("")

    # Food Recommendations
    food_rec = state.food_recommendations or {}
    if food_rec:
        lines.append("FOOD & DINING RECOMMENDATIONS")
        lines.append("-" * 40)
        suggestions = food_rec.get("suggestions") or []
        for suggestion in suggestions:
            lines.append(f"• {suggestion}")
        lines.append("")

    # Approval Status
    lines.append("APPROVAL STATUS")
    lines.append("-" * 40)
    lines.append(f"Approved: {'Yes' if state.review_status.approved else 'No'}")
    if state.review_status.reasons:
        lines.append("Reasons:")
        for reason in state.review_status.reasons:
            lines.append(f"  • {reason}")
    lines.append("")
    lines.append("=" * 80)

    return "\n".join(lines)


def _enhance_report_with_llm(plaintext_report: str) -> str:
    """Send plaintext report to LLM for enhancement and formatting."""
    if not settings.SARVAM_API_KEY:
        logger.info("No SARVAM_API_KEY configured, skipping LLM enhancement")
        return ""

    llm = SarvamLLMService(api_key=settings.SARVAM_API_KEY, model=settings.SARVAM_MODEL)
    if not getattr(llm, "enabled", False):
        logger.info("LLM service not enabled, skipping enhancement")
        return ""

    system = (
        "You are a professional travel report writer and editor. You will receive a plaintext trip report and your job is to:\n"
        "1. Expand and enhance the report with vivid descriptions\n"
        "2. Make it more verbose and detailed\n"
        "3. Improve grammar and flow\n"
        "4. Add travel tips and insights based on the provided information\n"
        "5. Format it nicely with proper sections and structure\n"
        "6. Keep all factual information intact\n"
        "Return ONLY the enhanced report text, nothing else."
    )
    user = f"Please enhance and improve this trip report:\n\n{plaintext_report}"

    try:
        enhanced = llm.chat_text(system=system, user=user, timeout=60)
        if enhanced:
            enhanced = enhanced.strip() if isinstance(enhanced, str) else ""
            if enhanced:
                logger.info("Successfully enhanced report with LLM")
                return enhanced
    except Exception as exc:
        logger.warning("LLM report enhancement failed: %s", exc)
    
    return ""


def _build_trip_basic_details(state: TripPlannerState, styles) -> List[Any]:
    prefs = state.trip_preferences or {}
    rows = _kv_rows(
        [
            ("Session ID", state.session_id),
            ("From", f"{prefs.get('source') or 'N/A'} -> {prefs.get('destination') or 'N/A'}"),
            ("Dates", f"{prefs.get('start_date') or 'N/A'} to {prefs.get('end_date') or 'N/A'}"),
            ("Budget", _format_money(prefs.get('budget'))),
            ("Travelers", _format_number(prefs.get('travelers'))),
            ("Travel type", prefs.get('travel_type')),
            ("Hotel preference", prefs.get('hotel_pref')),
            ("Food preference", prefs.get('food_pref')),
            ("Transport preference", prefs.get('transport_pref')),
            ("Interests", ", ".join([_compact_text(item) for item in _as_list(prefs.get('places_of_interest')) if _compact_text(item)])),
            ("Luxury level", prefs.get('luxury')),
            ("Use memory", "Yes" if prefs.get('use_memory') else "No"),
            ("Save preferences", "Yes" if prefs.get('remember_preferences') else "No"),
            ("Review status", "Approved" if state.review_status.approved else "Needs attention"),
        ]
    )
    return [*_section_heading("Trip Basic Details", styles), _table([["Field", "Value"], *rows], styles, col_widths=[48 * mm, 122 * mm]), Spacer(1, 6)]


def _build_flight_details(state: TripPlannerState, styles) -> List[Any]:
    prefs = state.trip_preferences or {}
    transport_data = state.transport_data or {}
    route = transport_data.get("route") or {}
    recommendations = transport_data.get("recommendations") or []
    flight_details = transport_data.get("flight_details") or {}
    top = flight_details if flight_details else (recommendations[0] if recommendations else {})

    rows = _kv_rows(
        [
            ("Recommended mode", flight_details.get("recommended_mode") or top.get("mode") or prefs.get("transport_pref") or "N/A"),
            ("Reason", flight_details.get("reason") or top.get("reason") or transport_data.get("summary") or "N/A"),
            ("Route source", route.get("source") or transport_data.get("source") or "routing"),
            ("Distance (km)", route.get("distance_km")),
            ("Duration (min)", route.get("duration_min")),
            ("Budget signal", transport_data.get("budget_signal")),
            ("Summary", flight_details.get("summary") or transport_data.get("summary") or "N/A"),
        ]
    )

    content: List[Any] = [
        *_section_heading("Flight Details from Agent", styles),
        Paragraph(
            "This section reflects the transport agent output. If live flight inventory is unavailable, it summarizes the recommended travel mode and route estimate instead of inventing ticket-level data.",
            styles["SectionNote"],
        ),
        _table([["Field", "Value"], *rows], styles, col_widths=[48 * mm, 122 * mm]),
        Spacer(1, 4),
    ]

    option_rows: List[List[Any]] = [["Mode", "Reason"]]
    for rec in recommendations[:6]:
        option_rows.append([rec.get("mode") or "N/A", rec.get("reason") or "N/A"])

    if len(option_rows) > 1:
        content.extend([Paragraph("Transport options", styles["SectionNote"]), _table(option_rows, styles, col_widths=[42 * mm, 128 * mm])])
    else:
        content.append(Paragraph("No transport options were returned by the agent.", styles["SectionNote"]))

    flight_rows: List[List[Any]] = [["Airline", "Flight", "Departure", "Arrival", "Duration (min)"]]
    for rec in (flight_details.get("flight_recommendations") or [])[:6]:
        flight_rows.append(
            [
                rec.get("airline") or "N/A",
                rec.get("flight_number") or "N/A",
                rec.get("departure_time") or "N/A",
                rec.get("arrival_time") or "N/A",
                rec.get("duration_min") or "N/A",
            ]
        )
    if len(flight_rows) > 1:
        content.extend([Paragraph("Flight recommendations", styles["SectionNote"]), _table(flight_rows, styles, col_widths=[42 * mm, 36 * mm, 30 * mm, 30 * mm, 32 * mm])])

    content.append(Spacer(1, 6))
    return content


def _build_hotel_details(state: TripPlannerState, styles) -> List[Any]:
    hotel_data = state.hotel_data or {}
    hotels = hotel_data.get("suggestions") or hotel_data.get("hotels") or []

    content: List[Any] = [
        *_section_heading("Hotel Details", styles),
        _table(
            [["Field", "Value"], ["Location", hotel_data.get("location") or "N/A"], ["Source", hotel_data.get("source") or "N/A"], ["Count", len(hotels)]],
            styles,
            col_widths=[48 * mm, 122 * mm],
        ),
        Spacer(1, 4),
    ]

    if not hotels:
        content.append(Paragraph("No hotel suggestions were returned by the agent.", styles["SectionNote"]))
        content.append(Spacer(1, 6))
        return content

    hotel_rows: List[List[Any]] = [["Name", "Type / Rating", "Summary"]]
    for hotel in hotels[:8]:
        type_bits = [hotel.get("type"), hotel.get("rating_hint"), hotel.get("source")]
        type_text = " | ".join([_compact_text(bit) for bit in type_bits if _compact_text(bit)]) or "N/A"
        hotel_rows.append([hotel.get("name") or "N/A", type_text, hotel.get("summary") or "N/A"])

    content.append(_table(hotel_rows, styles, col_widths=[48 * mm, 44 * mm, 78 * mm]))
    content.append(Spacer(1, 6))
    return content


def _build_tourist_locations(state: TripPlannerState, styles) -> List[Any]:
    places_data = state.places_data or {}
    places = places_data.get("places") or []

    content: List[Any] = [
        *_section_heading("Tourist Locations", styles),
        _table(
            [["Field", "Value"], ["Location", places_data.get("location") or "N/A"], ["Requested interests", ", ".join([_compact_text(item) for item in _as_list(places_data.get("requested_interests")) if _compact_text(item)]) or "N/A"], ["Source", places_data.get("source") or "N/A"], ["Count", len(places)]],
            styles,
            col_widths=[48 * mm, 122 * mm],
        ),
        Spacer(1, 4),
    ]

    if not places:
        content.append(Paragraph("No tourist locations were returned by the agent.", styles["SectionNote"]))
        content.append(Spacer(1, 6))
        return content

    place_rows: List[List[Any]] = [["Name", "Type / Best for", "Summary / Source"]]
    for place in places[:10]:
        best_for = _compact_text(place.get("best_for"))
        meta_bits = [place.get("type"), best_for]
        meta_text = " | ".join([_compact_text(bit) for bit in meta_bits if _compact_text(bit)]) or "N/A"
        source_bits = [place.get("source")]
        if place.get("lat") is not None and place.get("lon") is not None:
            source_bits.append(f"{place.get('lat')}, {place.get('lon')}")
        summary_bits = [place.get("summary")]
        place_rows.append([
            place.get("name") or "N/A",
            meta_text,
            " | ".join([_compact_text(bit) for bit in source_bits + summary_bits if _compact_text(bit)]) or "N/A",
        ])

    content.append(_table(place_rows, styles, col_widths=[48 * mm, 44 * mm, 78 * mm]))
    content.append(Spacer(1, 6))
    return content


def _build_notes_and_facts(state: TripPlannerState, styles) -> List[Any]:
    prefs = state.trip_preferences or {}
    itinerary = state.itinerary or {}
    weather_data = state.weather_data or {}
    budget_summary = state.budget_summary or {}
    food = state.food_recommendations or {}
    emergency = state.emergency_tips or {}

    notes: List[str] = []
    notes.extend([_compact_text(item) for item in _as_list(itinerary.get("notes")) if _compact_text(item)])
    notes.extend([_compact_text(item) for item in _as_list((food or {}).get("suggestions")) if _compact_text(item)])
    notes.extend([_compact_text(item) for item in _as_list((emergency or {}).get("tips")) if _compact_text(item)])
    notes.extend([_compact_text(item) for item in _as_list(state.warnings) if _compact_text(item)])
    notes.extend([_compact_text(item) for item in _as_list(state.errors) if _compact_text(item)])

    forecast = _as_list(weather_data.get("forecast"))
    if forecast:
        first = forecast[0] or {}
        date = _compact_text(first.get("date") or first.get("time"))
        temp = first.get("temp_c") or first.get("temp_max_c") or first.get("temp")
        desc = _compact_text(first.get("description") or first.get("weathercode") or first.get("summary"))
        notes.append(f"Weather snapshot: {date} {temp}C {desc}".strip())
    elif weather_data.get("summary"):
        notes.append(f"Weather snapshot: {_compact_text(weather_data.get('summary'))}")

    estimated_total = budget_summary.get("estimated_total")
    budget_limit = prefs.get("budget")
    if estimated_total is not None or budget_limit is not None:
        notes.append(
            f"Budget fact: estimated total {_format_money(estimated_total)} against limit {_format_money(budget_limit)}. Keep a 10-15% buffer for local transport and incidentals."
        )

    notes.append(f"Review verdict: {'approved' if state.review_status.approved else 'not approved'}")
    if state.final_output.get("summary"):
        notes.append(f"Final summary: {_compact_text(state.final_output.get('summary'))}")

    unique_notes: List[str] = []
    seen = set()
    for note in notes:
        if note and note not in seen:
            seen.add(note)
            unique_notes.append(note)

    content: List[Any] = [
        *_section_heading("Notes & Facts", styles),
        _table(
            [["Field", "Value"], ["Trip days", itinerary.get("trip_days") or "N/A"], ["Destination", prefs.get("destination") or "N/A"], ["Weather source", weather_data.get("source") or "N/A"], ["Budget estimate", _format_money(budget_summary.get("estimated_total"))], ["Approved", "Yes" if state.review_status.approved else "No"]],
            styles,
            col_widths=[48 * mm, 122 * mm],
        ),
        Spacer(1, 4),
    ]

    if unique_notes:
        for note in unique_notes[:30]:
            content.append(Paragraph(f"- {escape(note)}", styles["BulletBody"]))
    else:
        content.append(Paragraph("No additional notes available.", styles["SectionNote"]))

    content.append(Spacer(1, 6))
    return content


def _build_document_story(state: TripPlannerState, styles) -> List[Any]:
    prefs = state.trip_preferences or {}
    destination = _compact_text(prefs.get("destination") or "Destination")
    summary = _compact_text(state.final_output.get("summary") or "")
    if not summary:
        summary = "Your trip has been professionally planned and reviewed."

    story: List[Any] = [
        Spacer(1, 4),
        Paragraph("Trip Planner Report", styles["ReportTitle"]),
        Paragraph(destination, styles["ReportTitle"]),
        Paragraph(summary, styles["ReportSubtitle"]),
        Spacer(1, 6),
    ]

    # Display enhanced report if available
    enhanced_report = (state.final_output or {}).get("enhanced_report")
    if enhanced_report:
        # Split the enhanced report into paragraphs and add them
        paragraphs = enhanced_report.split("\n")
        for para_text in paragraphs:
            para_text = para_text.strip()
            if not para_text:
                story.append(Spacer(1, 3))
            elif para_text.startswith("=" * 10):
                # Section divider - skip
                story.append(Spacer(1, 6))
            elif para_text.startswith("-" * 10):
                # Sub-section divider - skip
                story.append(Spacer(1, 4))
            elif para_text.isupper() and len(para_text) < 60:
                # Section heading
                story.append(Paragraph(escape(para_text), styles["SectionHeading"]))
                story.append(Spacer(1, 3))
            elif para_text.startswith("•") or para_text.startswith("-"):
                # Bullet point
                story.append(Paragraph(escape(para_text), styles["BulletBody"]))
            elif ":" in para_text and len(para_text) < 100:
                # Key-value pair (like "From: Bangalore")
                story.append(Paragraph(escape(para_text), styles["TableBody"]))
            else:
                # Regular paragraph
                story.append(Paragraph(escape(para_text), styles["SectionNote"]))
        story.append(Spacer(1, 6))
    else:
        # Fallback to plaintext report if LLM enhancement not available
        plaintext_report = (state.final_output or {}).get("plaintext_report")
        if plaintext_report:
            story.append(Paragraph("Report Details", styles["SectionHeading"]))
            story.append(Spacer(1, 3))
            paragraphs = plaintext_report.split("\n")
            for para_text in paragraphs:
                para_text = para_text.strip()
                if not para_text or para_text.startswith("=" * 10) or para_text.startswith("-" * 10):
                    continue
                if para_text.isupper() and len(para_text) < 60:
                    story.append(Paragraph(escape(para_text), styles["SectionHeading"]))
                    story.append(Spacer(1, 2))
                elif para_text.startswith("•") or para_text.startswith("-"):
                    story.append(Paragraph(escape(para_text), styles["BulletBody"]))
                else:
                    story.append(Paragraph(escape(para_text), styles["SectionNote"]))
            story.append(Spacer(1, 6))

    # Add traditional sections as well for completeness
    story.extend(_build_trip_basic_details(state, styles))
    story.extend(_build_flight_details(state, styles))
    story.extend(_build_hotel_details(state, styles))
    story.extend(_build_tourist_locations(state, styles))
    story.extend(_build_notes_and_facts(state, styles))
    return story


def generate_reports(state: TripPlannerState) -> Dict[str, str]:
    out_dir = os.path.join(os.getcwd(), "output")
    os.makedirs(out_dir, exist_ok=True)

    pdf_path = os.path.join(out_dir, f"trip_{state.session_id}.pdf")

    prefs = state.trip_preferences or {}
    destination = _compact_text(prefs.get("destination") or "")
    transport_pref = _compact_text(prefs.get("transport_pref") or "")
    food_pref = _compact_text(prefs.get("food_pref") or "")

    itinerary = state.itinerary or {}
    food = state.food_recommendations or _food_suggestions(destination, food_pref)
    emergency = state.emergency_tips or _emergency_tips(destination, transport_pref, state.weather_data or {})
    travel_recs = _travel_recommendations(prefs, itinerary)

    state.food_recommendations = food
    state.emergency_tips = emergency

    # Generate plaintext report and enhance with LLM
    plaintext_report = _generate_plaintext_report(state)
    enhanced_report = _enhance_report_with_llm(plaintext_report)

    state.final_output = state.final_output or {}
    
    # Use enhanced report if available, otherwise keep plaintext
    if enhanced_report:
        state.final_output["enhanced_report"] = enhanced_report
        state.final_output["summary"] = "Your trip has been professionally planned and reviewed."
    else:
        state.final_output["plaintext_report"] = plaintext_report
        state.final_output["summary"] = "Trip planned and approved." if state.review_status.approved else "Trip planned with review warnings."

    if travel_recs.get("recommendations"):
        state.final_output["travel_recommendations"] = travel_recs["recommendations"]

    styles = _styles()
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=20 * mm,
        bottomMargin=18 * mm,
        title=f"Trip Planner Report - {destination or state.session_id}",
        author="Trip Planner Multi-Agent",
    )
    doc.build(_build_document_story(state, styles), onFirstPage=_page_decorations, onLaterPages=_page_decorations)
    return {"pdf_path": pdf_path}


def generate_pdf_report(state: TripPlannerState) -> str:
    return generate_reports(state)["pdf_path"]
