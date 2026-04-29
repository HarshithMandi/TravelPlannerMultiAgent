from src.services.hotel_service import HotelService
from src.services.places_service import PlacesService
from src.services.transport_service import TransportService


class _NoSearch:
    def search(self, *args, **kwargs):
        return []


class _NoGeocode:
    def geocode(self, *args, **kwargs):
        return None


class _NoRoute:
    def route(self, source, destination):
        return {"source": "fallback", "distance_km": None, "duration_min": None}


def test_place_candidate_filter_prefers_actual_places():
    service = PlacesService(geocoding_service=_NoGeocode())

    assert service._is_candidate_place("Maldives", "Banana Reef", "reef in North Male Atoll")
    assert service._is_candidate_place("Maldives", "National Museum (Maldives)", "museum in Male")
    assert not service._is_candidate_place("Maldives", "Tourism in India", "mentions Maldives visa rules")
    assert not service._is_candidate_place("Maldives", "Visa policy of the Maldives", "")


def test_wikipedia_categories_cover_destination_place_types():
    service = PlacesService(geocoding_service=_NoGeocode())

    categories = service._wikipedia_categories("Maldives")

    assert "Category:Tourist attractions in Maldives" in categories
    assert "Category:Islands of Maldives" in categories
    assert "Category:Beaches of Maldives" in categories


def test_maldives_hotels_use_local_island_guidance():
    service = HotelService(geocoding_service=_NoGeocode())
    service.duckduckgo = _NoSearch()

    result = service.search_hotels("Maldives", 30000, "budget", "beach resort", timeout=1)
    names = [hotel["name"] for hotel in result["hotels"]]

    assert "Maafushi local-island guesthouses" in names
    assert "Hulhumale airport-area hotels" in names


def test_maldives_transport_avoids_train_recommendation():
    result = TransportService(routing_service=_NoRoute()).recommend("Bangalore", "Maldives", "flight", 30000)
    modes = [item["mode"] for item in result["recommendations"]]

    assert "flight" in modes
    assert "speedboat/ferry" in modes
    assert "train" not in modes
