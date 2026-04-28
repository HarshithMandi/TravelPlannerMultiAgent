import os
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm
from src.state.schemas import TripPlannerState


def generate_pdf_report(state: TripPlannerState) -> str:
    out_dir = os.path.join(os.getcwd(), "trip-planner", "output")
    os.makedirs(out_dir, exist_ok=True)
    filename = f"trip_{state.session_id}.pdf"
    path = os.path.join(out_dir, filename)

    c = canvas.Canvas(path, pagesize=A4)
    width, height = A4

    c.setFont("Helvetica-Bold", 20)
    c.drawCentredString(width / 2, height - 3 * cm, "Trip Planner Report")

    # Trip Summary
    c.setFont("Helvetica", 12)
    y = height - 4 * cm
    c.drawString(2 * cm, y, f"Session: {state.session_id}")
    y -= 1 * cm
    prefs = state.trip_preferences
    c.drawString(2 * cm, y, f"From: {prefs.get('source')}  To: {prefs.get('destination')}")
    y -= 1 * cm
    c.drawString(2 * cm, y, f"Dates: {prefs.get('start_date')} - {prefs.get('end_date')}")
    y -= 1 * cm

    # Itinerary
    c.setFont("Helvetica-Bold", 14)
    c.drawString(2 * cm, y, "Itinerary:")
    y -= 0.8 * cm
    c.setFont("Helvetica", 11)
    for day in state.itinerary.get("days", []):
        if y < 3 * cm:
            c.showPage()
            y = height - 3 * cm
        c.drawString(2 * cm, y, f"Day {day.get('day')}: {day.get('activity')} - {day.get('notes')}")
        y -= 0.8 * cm

    c.showPage()
    c.save()
    return path
