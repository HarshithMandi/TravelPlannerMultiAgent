from pathlib import Path

from src.state.schemas import TripPlannerState
from src.tools.pdf_tools import generate_reports


def test_generate_reports_creates_pdf(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    state = TripPlannerState(
        session_id="pdf-test",
        trip_preferences={
            "source": "Bangalore",
            "destination": "Goa",
            "start_date": "2026-06-01",
            "end_date": "2026-06-05",
            "budget": 50000,
            "travelers": 2,
            "travel_type": "couple",
            "hotel_pref": "beach resort",
            "food_pref": "seafood",
            "transport_pref": "flight",
            "places_of_interest": ["beaches", "nightlife"],
            "luxury": "budget",
        },
        transport_data={
            "source": "routing",
            "summary": "Route estimate available",
            "budget_signal": "normal",
            "flight_details": {
                "recommended_mode": "flight",
                "reason": "Long route",
                "summary": "Use flight for the main leg",
                "route": {"source": "routing", "distance_km": 560, "duration_min": 95},
                "options": [{"mode": "flight", "reason": "Long route"}],
            },
            "route": {"source": "routing", "distance_km": 560, "duration_min": 95},
            "recommendations": [{"mode": "flight", "reason": "Long route"}],
        },
        hotel_data={
            "source": "web",
            "location": "Goa",
            "suggestions": [
                {"name": "Beach Stay", "type": "hotel", "rating_hint": "web", "summary": "Near the beach", "source": "duckduckgo"}
            ],
        },
        places_data={
            "source": "web",
            "location": "Goa",
            "requested_interests": ["beaches", "nightlife"],
            "places": [
                {"name": "Calangute Beach", "type": "beach", "best_for": "sunset", "summary": "Popular beach", "source": "wikipedia"}
            ],
        },
        itinerary={"trip_days": 3, "notes": ["Day 1: beach walk"]},
        weather_data={"source": "demo", "forecast": [{"date": "2026-06-01", "temp_c": 29, "description": "clear"}]},
        budget_summary={"estimated_total": 42000},
    )

    result = generate_reports(state)
    pdf_path = Path(result["pdf_path"])

    assert pdf_path.exists()
    assert pdf_path.suffix == ".pdf"