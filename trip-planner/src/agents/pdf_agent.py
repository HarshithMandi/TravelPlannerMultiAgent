from src.state.schemas import TripPlannerState
from src.tools.pdf_tools import generate_reports


def run(state: TripPlannerState) -> TripPlannerState:
    paths = generate_reports(state)
    pdf_path = paths.get("pdf_path")
    state.pdf_status.path = pdf_path
    state.pdf_status.pdf_path = pdf_path
    state.pdf_status.generated = True
    state.agent_reasoning["pdf_agent"] = f"Generated downloadable PDF report: {pdf_path}"
    return state
