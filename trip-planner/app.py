import os
import uuid
from datetime import date, datetime

import streamlit as st

from src.agents import pdf_agent
from src.agents.orchestrator import Orchestrator
from src.config.settings import settings
from src.services.embedding_service import OpenAIEmbeddingService
from src.services.llm_service import SarvamLLMService
from src.state.schemas import TripPlannerState


st.set_page_config(page_title="Trip Planner Studio", page_icon="✈️", layout="wide", initial_sidebar_state="expanded")


def _inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

        :root {
            --bg: #f4f7fb;
            --panel: rgba(255, 255, 255, 0.88);
            --panel-strong: #ffffff;
            --text: #112033;
            --muted: #5a6b7f;
            --accent: #0b5cab;
            --accent-2: #0f766e;
            --border: rgba(15, 32, 51, 0.10);
            --shadow: 0 18px 50px rgba(15, 32, 51, 0.10);
            --radius: 20px;
        }

        html, body, [class*="css"]  {
            font-family: 'Inter', sans-serif;
        }

        .stApp {
            background:
                radial-gradient(circle at top left, rgba(11, 92, 171, 0.13), transparent 32%),
                radial-gradient(circle at top right, rgba(15, 118, 110, 0.10), transparent 28%),
                linear-gradient(180deg, #f8fbff 0%, #eef4f9 100%);
            color: var(--text);
        }

        .block-container {
            padding-top: 2rem;
            padding-bottom: 2.5rem;
        }

        .hero {
            background: linear-gradient(135deg, rgba(11, 92, 171, 0.98), rgba(15, 118, 110, 0.95));
            color: white;
            border-radius: 28px;
            padding: 2rem 2rem 1.75rem 2rem;
            box-shadow: var(--shadow);
            border: 1px solid rgba(255, 255, 255, 0.12);
        }

        .hero h1 {
            font-size: 2.4rem;
            line-height: 1.05;
            margin: 0 0 0.5rem 0;
            font-weight: 800;
            letter-spacing: -0.04em;
        }

        .hero p {
            margin: 0;
            max-width: 60rem;
            color: rgba(255, 255, 255, 0.9);
            font-size: 0.98rem;
        }

        .hero-pill-row {
            display: flex;
            gap: 0.6rem;
            flex-wrap: wrap;
            margin-top: 1rem;
        }

        .hero-pill {
            background: rgba(255, 255, 255, 0.14);
            border: 1px solid rgba(255, 255, 255, 0.16);
            color: white;
            border-radius: 999px;
            padding: 0.42rem 0.8rem;
            font-size: 0.8rem;
            font-weight: 600;
        }

        .metric-card, .content-card, .sidebar-panel, .status-card {
            background: var(--panel);
            backdrop-filter: blur(16px);
            border: 1px solid var(--border);
            border-radius: var(--radius);
            box-shadow: var(--shadow);
        }

        .metric-card {
            padding: 1rem 1.1rem;
        }

        .metric-label {
            color: var(--muted);
            font-size: 0.8rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }

        .metric-value {
            color: var(--text);
            font-size: 1.4rem;
            font-weight: 800;
            margin-top: 0.25rem;
        }

        .metric-subtitle {
            color: var(--muted);
            font-size: 0.85rem;
            margin-top: 0.2rem;
        }

        .content-card {
            padding: 1.2rem 1.25rem;
        }

        .sidebar-panel {
            padding: 1rem;
        }

        .section-title {
            font-size: 1.1rem;
            font-weight: 800;
            margin: 0 0 0.25rem 0;
            color: var(--text);
        }

        .section-subtitle {
            color: var(--muted);
            font-size: 0.88rem;
            margin: 0 0 0.75rem 0;
        }

        .status-chip {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            padding: 0.35rem 0.7rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 700;
            border: 1px solid var(--border);
            background: rgba(255, 255, 255, 0.75);
            color: var(--text);
        }

        .status-chip.good { background: rgba(15, 118, 110, 0.12); color: #0f766e; }
        .status-chip.warn { background: rgba(217, 119, 6, 0.12); color: #b45309; }
        .status-chip.bad { background: rgba(185, 28, 28, 0.12); color: #b91c1c; }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0.4rem;
            background: rgba(255, 255, 255, 0.55);
            padding: 0.35rem;
            border-radius: 16px;
            border: 1px solid var(--border);
        }

        .stTabs [data-baseweb="tab"] {
            border-radius: 12px;
            padding: 0.5rem 0.9rem;
            font-weight: 700;
        }

        .stTabs [aria-selected="true"] {
            background: white;
            box-shadow: 0 8px 20px rgba(15, 32, 51, 0.08);
        }

        div[data-testid="stForm"] {
            border: none;
        }

        .stButton > button, .stDownloadButton > button {
            border-radius: 14px;
            border: none;
            font-weight: 700;
            padding: 0.65rem 1rem;
        }

        .stButton > button {
            background: linear-gradient(135deg, var(--accent), #1446a0);
            color: white;
        }

        .stDownloadButton > button {
            background: linear-gradient(135deg, var(--accent-2), #0b8a7a);
            color: white;
        }

        .soft-box {
            background: rgba(255, 255, 255, 0.72);
            border: 1px solid var(--border);
            border-radius: 18px;
            padding: 1rem;
            box-shadow: 0 8px 24px rgba(15, 32, 51, 0.06);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _format_currency(value) -> str:
    try:
        return f"INR {int(value):,}"
    except Exception:
        return str(value or "N/A")


def _format_date(value) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    try:
        return datetime.fromisoformat(str(value)).date().isoformat()
    except Exception:
        return str(value or "N/A")


def _split_interests(text: str):
    return [item.strip() for item in (text or "").split(",") if item.strip()]


def _chip(label: str, tone: str = "") -> str:
    tone_class = f" {tone}" if tone else ""
    return f'<span class="status-chip{tone_class}">{label}</span>'


def _metric_card(label: str, value: str, subtitle: str = "") -> str:
    return f"""
    <div class="metric-card">
        <div class="metric-label">{label}</div>
        <div class="metric-value">{value}</div>
        <div class="metric-subtitle">{subtitle}</div>
    </div>
    """


def _content_card(title: str, subtitle: str = ""):
    st.markdown(
        f"""
        <div class="content-card">
            <div class="section-title">{title}</div>
            <div class="section-subtitle">{subtitle}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _kv_grid(items):
    cols = st.columns(min(len(items), 3))
    for idx, (label, value) in enumerate(items):
        with cols[idx % len(cols)]:
            st.markdown(
                f"""
                <div class="soft-box">
                    <div class="metric-label">{label}</div>
                    <div class="metric-value" style="font-size:1.05rem;">{value}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def _render_list(title: str, items, empty_text: str):
    st.markdown(f"#### {title}")
    if not items:
        st.caption(empty_text)
        return
    for item in items:
        st.markdown(f"- {item}")


def _validation_message(source: str, destination: str, start_date, end_date, budget: int):
    if not destination.strip():
        st.error("Destination is required before planning a trip.")
        return False
    try:
        if start_date > end_date:
            st.error("End date must be on or after the start date.")
            return False
    except Exception:
        pass
    if budget <= 0:
        st.warning("Budget is set to zero. The planner will still run, but results may be limited.")
    if not source.strip():
        st.warning("Source location is empty. Transport planning may be less accurate.")
    return True


_inject_styles()

st.markdown(
    """
    <div class="hero">
        <h1>Trip Planner Studio</h1>
        <p>A polished multi-agent travel planning workspace for discovering routes, stays, attractions, and a downloadable report in one place.</p>
        <div class="hero-pill-row">
            <span class="hero-pill">AI orchestration</span>
            <span class="hero-pill">Route-aware planning</span>
            <span class="hero-pill">ReportLab PDF export</span>
            <span class="hero-pill">Memory personalization</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.write("")

left, right = st.columns([0.34, 0.66], gap="large")

with left:
    st.markdown(
        """
        <div class="sidebar-panel">
            <div class="section-title">Trip controls</div>
            <div class="section-subtitle">Group the inputs to keep the form easy to scan.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.form("trip_form", clear_on_submit=False):
        st.markdown("##### Basics")
        source = st.text_input("Source location", value=st.session_state.get("source", "Bangalore"), placeholder="City or airport")
        destination = st.text_input("Destination", value=st.session_state.get("destination", "Goa"), placeholder="Where are you going?")

        c1, c2 = st.columns(2)
        with c1:
            start_date = st.date_input("Start date", value=st.session_state.get("start_date", date.today()))
        with c2:
            end_date = st.date_input("End date", value=st.session_state.get("end_date", date.today()))

        c3, c4 = st.columns(2)
        with c3:
            budget = st.number_input("Budget (INR)", min_value=0, value=int(st.session_state.get("budget", 30000)))
        with c4:
            travelers = st.number_input("Travelers", min_value=1, value=int(st.session_state.get("travelers", 2)))

        travel_type = st.selectbox("Travel type", ["couple", "solo", "family", "business"], index=0)
        transport_pref = st.selectbox("Transport preference", ["flight", "train", "bus", "car"], index=0)

        st.markdown("##### Preferences")
        hotel_pref = st.text_input("Hotel preferences", value=st.session_state.get("hotel_pref", "beach resort"))
        food_pref = st.text_input("Food preferences", value=st.session_state.get("food_pref", "seafood"))
        places_of_interest = st.text_area("Places of interest", value=st.session_state.get("places_of_interest", "beaches, nightlife, sightseeing"), help="Comma separated values work best.")
        luxury = st.selectbox("Luxury level", ["budget", "luxury"], index=0)

        st.markdown("##### Advanced")
        use_memory = st.checkbox("Use memory personalization", value=st.session_state.get("use_memory", False))
        remember_preferences = st.checkbox("Save preferences for future trips", value=st.session_state.get("remember_preferences", False))
        debug = st.checkbox("Debug mode", value=st.session_state.get("debug", False), help="Show raw state for troubleshooting.")

        submitted = st.form_submit_button("Plan Trip")

if submitted:
    st.session_state["source"] = source
    st.session_state["destination"] = destination
    st.session_state["start_date"] = start_date
    st.session_state["end_date"] = end_date
    st.session_state["budget"] = budget
    st.session_state["travelers"] = travelers
    st.session_state["hotel_pref"] = hotel_pref
    st.session_state["food_pref"] = food_pref
    st.session_state["places_of_interest"] = places_of_interest
    st.session_state["use_memory"] = use_memory
    st.session_state["remember_preferences"] = remember_preferences
    st.session_state["debug"] = debug

    if _validation_message(source, destination, start_date, end_date, budget):
        session_id = str(uuid.uuid4())
        state = TripPlannerState(
            session_id=session_id,
            trip_preferences={
                "source": source,
                "destination": destination,
                "start_date": str(start_date),
                "end_date": str(end_date),
                "budget": budget,
                "travelers": int(travelers),
                "travel_type": travel_type,
                "hotel_pref": hotel_pref,
                "food_pref": food_pref,
                "transport_pref": transport_pref,
                "places_of_interest": _split_interests(places_of_interest),
                "luxury": luxury,
                "use_memory": use_memory,
                "remember_preferences": remember_preferences,
            },
        )

        st.info("Starting orchestration. The planner will combine weather, transport, hotels, and attractions.")

        llm = None
        embed = None

        if settings.SARVAM_API_KEY:
            llm = SarvamLLMService(api_key=settings.SARVAM_API_KEY, model=settings.SARVAM_MODEL)
        else:
            st.caption("Sarvam API key not configured. The planner will run in demo mode for LLM-backed steps.")

        if settings.OPENAI_API_KEY:
            embed = OpenAIEmbeddingService(api_key=settings.OPENAI_API_KEY, model=settings.OPENAI_EMBEDDING_MODEL)
        else:
            st.caption("OpenAI API key not configured. Memory lookup will be skipped.")

        orchestrator = Orchestrator(llm_service=llm, embedding_service=embed)

        progress = st.progress(0, text="Preparing trip state...")
        with st.spinner("Running planner..."):
            progress.progress(15, text="Normalizing inputs")
            result_state = orchestrator.run(state, debug=debug)
            progress.progress(100, text="Planning complete")

        st.session_state["last_result_state"] = result_state
        st.session_state["last_debug"] = debug
        st.success("Planning complete")

result_state = st.session_state.get("last_result_state")
debug = st.session_state.get("last_debug", False)

with right:
    if result_state:
        final = result_state.final_output or {}
        prefs = result_state.trip_preferences or {}
        transport_data = result_state.transport_data or {}
        hotel_data = result_state.hotel_data or {}
        places_data = result_state.places_data or {}
        itinerary = result_state.itinerary or {}

        st.markdown(
            f"""
            <div class="content-card">
                <div style="display:flex;justify-content:space-between;gap:1rem;align-items:flex-start;flex-wrap:wrap;">
                    <div>
                        <div class="section-title">{prefs.get('destination', 'Trip result')}</div>
                        <div class="section-subtitle">{final.get('summary', 'Trip details are ready.')}</div>
                    </div>
                    <div style="display:flex;gap:0.5rem;flex-wrap:wrap;align-items:center;">
                        {_chip('Approved', 'good') if getattr(result_state.review_status, 'approved', False) else _chip('Needs review', 'warn')}
                        {_chip('PDF ready', 'good') if getattr(result_state.pdf_status, 'generated', False) else _chip('PDF not generated', 'warn')}
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        top_a, top_b, top_c = st.columns(3)
        with top_a:
            st.markdown(_metric_card("Budget", _format_currency(prefs.get("budget")), f"Travelers: {prefs.get('travelers', 'N/A')}"), unsafe_allow_html=True)
        with top_b:
            st.markdown(_metric_card("Trip days", str(itinerary.get("trip_days", "N/A")), f"{_format_date(prefs.get('start_date'))} to {_format_date(prefs.get('end_date'))}"), unsafe_allow_html=True)
        with top_c:
            st.markdown(
                _metric_card(
                    "Places",
                    str(len((places_data.get('places') or []))),
                    f"Hotels: {len((hotel_data.get('suggestions') or hotel_data.get('hotels') or []))}",
                ),
                unsafe_allow_html=True,
            )


        tabs = st.tabs(["Overview", "Itinerary", "Results", "Report"])

        with tabs[0]:
            st.markdown("#### Executive summary")
            st.write(final.get("summary", "No summary generated."))

            overview_cols = st.columns(2)
            with overview_cols[0]:
                st.markdown("#### Trip snapshot")
                _kv_grid(
                    [
                        ("Route", f"{prefs.get('source', 'N/A')} → {prefs.get('destination', 'N/A')}") ,
                        ("Transport", prefs.get("transport_pref", "N/A")),
                        ("Hotel style", prefs.get("hotel_pref", "N/A")),
                    ]
                )
            with overview_cols[1]:
                st.markdown("#### Planning status")
                st.markdown(_chip("Memory on" if prefs.get("use_memory") else "Memory off", "good" if prefs.get("use_memory") else "warn"), unsafe_allow_html=True)
                st.markdown(_chip("Preferences saved" if prefs.get("remember_preferences") else "Preferences not saved", "good" if prefs.get("remember_preferences") else "warn"), unsafe_allow_html=True)
                if result_state.warnings:
                    st.warning(f"{len(result_state.warnings)} warning(s) returned by the planner.")
                if result_state.errors:
                    st.error(f"{len(result_state.errors)} error(s) returned by the planner.")

        with tabs[1]:
            st.markdown("#### Day-wise itinerary")
            if itinerary.get("days"):
                for day in itinerary.get("days", []):
                    with st.expander(f"Day {day.get('day', '?')} - {day.get('title', 'Plan')}", expanded=(day.get('day', 1) == 1)):
                        left_day, right_day = st.columns(2)
                        with left_day:
                            st.markdown("**Morning**")
                            st.write(day.get("morning", "N/A"))
                            st.markdown("**Afternoon**")
                            st.write(day.get("afternoon", "N/A"))
                        with right_day:
                            st.markdown("**Evening**")
                            st.write(day.get("evening", "N/A"))
            else:
                st.caption("No itinerary details were returned.")

        with tabs[2]:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("#### Flight details")
                st.write((transport_data.get("flight_details") or transport_data or {}).get("summary", "No transport summary available."))
                st.json(transport_data) if debug else st.caption("Transport details are summarized in the report tab.")
            with c2:
                st.markdown("#### Hotels")
                if hotel_data.get("suggestions") or hotel_data.get("hotels"):
                    st.json(hotel_data) if debug else st.write("Top hotel suggestions are included in the generated PDF.")
                else:
                    st.caption("No hotel suggestions available.")

            st.markdown("#### Tourist locations")
            if places_data.get("places"):
                st.json(places_data) if debug else st.write("Tourist locations are included in the generated PDF.")
            else:
                st.caption("No tourist locations available.")

            if debug:
                st.markdown("#### Raw state")
                st.json(result_state.model_dump())

        with tabs[3]:
            st.markdown("#### Export report")
            st.caption("Generate a polished PDF report that follows the structured section layout.")
            report_col1, report_col2 = st.columns([0.24, 0.76])
            with report_col1:
                if st.button("Generate PDF report"):
                    with st.spinner("Generating report..."):
                        result_state = pdf_agent.run(result_state)
                        st.session_state["last_result_state"] = result_state
                        st.session_state["last_debug"] = debug
            with report_col2:
                if result_state.pdf_status and result_state.pdf_status.generated:
                    pdf_path = result_state.pdf_status.pdf_path or result_state.pdf_status.path
                    if pdf_path and os.path.exists(pdf_path):
                        with open(pdf_path, "rb") as f:
                            st.download_button("Download PDF report", f, file_name=os.path.basename(pdf_path))
                else:
                    st.info("Generate the report to enable downloading.")
    else:
        st.markdown(
            """
            <div class="content-card">
                <div class="section-title">Ready when you are</div>
                <div class="section-subtitle">Fill in the trip form on the left to generate a full itinerary and PDF report.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
