from src.state.schemas import TripPlannerState
from src.tools.pdf_tools import generate_pdf_report


def run(state: TripPlannerState) -> TripPlannerState:
    path = generate_pdf_report(state)
    state.pdf_status.path = path
    state.pdf_status.generated = True
    return state
