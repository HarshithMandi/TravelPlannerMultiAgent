import os
from src.state.schemas import TripPlannerState


def generate_pdf_report(state: TripPlannerState) -> str:
    """Generate a text report file (renamed from PDF for flexibility)."""
    out_dir = os.path.join(os.getcwd(), "output")
    os.makedirs(out_dir, exist_ok=True)
    filename = f"trip_{state.session_id}.txt"
    path = os.path.join(out_dir, filename)

    prefs = state.trip_preferences
    lines = [
        "=" * 60,
        "TRIP PLANNER REPORT",
        "=" * 60,
        f"Session ID: {state.session_id}",
        "",
        "TRIP DETAILS",
        "-" * 60,
        f"From: {prefs.get('source')} → To: {prefs.get('destination')}",
        f"Dates: {prefs.get('start_date')} to {prefs.get('end_date')}",
        f"Budget: ₹{prefs.get('budget'):,}",
        f"Travelers: {prefs.get('travelers')}",
        f"Travel Type: {prefs.get('travel_type')}",
        f"Hotel Preference: {prefs.get('hotel_pref')}",
        f"Food Preference: {prefs.get('food_pref')}",
        f"Transport: {prefs.get('transport_pref')}",
        f"Interests: {', '.join(prefs.get('places_of_interest', []))}",
        f"Luxury Level: {prefs.get('luxury')}",
        "",
        "ITINERARY SUMMARY",
        "-" * 60,
    ]
    
    itinerary = state.itinerary or {}
    lines.append(f"Destination: {itinerary.get('destination', 'N/A')}")
    lines.append(f"Trip Duration: {itinerary.get('trip_days', 'N/A')} days")
    lines.append(f"Weather: {itinerary.get('weather_summary', 'N/A')}")
    lines.append(f"Hotel: {itinerary.get('hotel_summary', 'N/A')}")
    lines.append(f"Transport: {itinerary.get('transport_summary', 'N/A')}")
    lines.append("")
    
    lines.append("DAY-BY-DAY PLAN")
    lines.append("-" * 60)
    
    for day in itinerary.get("days", []):
        lines.append(f"\nDay {day.get('day')}: {day.get('title', 'Planned Activity')}")
        lines.append(f"  Morning: {day.get('morning', 'N/A')}")
        lines.append(f"  Afternoon: {day.get('afternoon', 'N/A')}")
        lines.append(f"  Evening: {day.get('evening', 'N/A')}")
        
        notes = day.get('notes', [])
        if notes:
            lines.append(f"  Notes:")
            if isinstance(notes, list):
                for note in notes:
                    if note:
                        lines.append(f"    • {note}")
            else:
                lines.append(f"    • {notes}")
    
    lines.append("\n" + "=" * 60)
    lines.append("END OF REPORT")
    lines.append("=" * 60)
    
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    
    return path

