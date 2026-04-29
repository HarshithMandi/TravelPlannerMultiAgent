import streamlit as st
from src.config.settings import settings
from src.services.llm_service import SarvamLLMService
from src.services.embedding_service import OpenAIEmbeddingService
from src.agents.orchestrator import Orchestrator
from src.state.schemas import TripPlannerState
import uuid
import os

st.set_page_config(page_title="Multi-Agent Trip Planner", layout="wide")

st.title("Multi-Agent Trip Planner")
st.sidebar.title("Trip Input")

with st.sidebar.form("trip_form"):
    source = st.text_input("Source location", value="Bangalore")
    destination = st.text_input("Destination", value="Goa")
    start_date = st.date_input("Start date")
    end_date = st.date_input("End date")
    budget = st.number_input("Budget (INR)", min_value=0, value=30000)
    travelers = st.number_input("Number of travelers", min_value=1, value=2)
    travel_type = st.selectbox("Travel type", ["couple","solo","family","business"]) 
    hotel_pref = st.text_input("Hotel preferences", value="beach resort")
    food_pref = st.text_input("Food preferences", value="seafood")
    transport_pref = st.selectbox("Transport preference", ["flight","train","bus","car"], index=0)
    places_of_interest = st.text_area("Places of interest (comma separated)", value="beaches, nightlife, sightseeing")
    luxury = st.selectbox("Luxury vs Budget", ["budget","luxury"], index=0)
    debug = st.checkbox("Debug mode (show graph state)")
    submitted = st.form_submit_button("Plan Trip")

if submitted:
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
            "places_of_interest": [p.strip() for p in places_of_interest.split(',') if p.strip()],
            "luxury": luxury,
        }
    )

    st.info("Starting orchestration — Orchestrator will drive agents now")

    # Initialize services (optional: app can run in demo mode without keys)
    llm = None
    embed = None

    if settings.SARVAM_API_KEY:
        llm = SarvamLLMService(api_key=settings.SARVAM_API_KEY, model=settings.SARVAM_MODEL)
    else:
        st.warning("SARVAM_API_KEY is not set — running without LLM calls (demo mode).")

    if settings.OPENAI_API_KEY:
        embed = OpenAIEmbeddingService(api_key=settings.OPENAI_API_KEY, model=settings.OPENAI_EMBEDDING_MODEL)
    else:
        st.warning("OPENAI_API_KEY is not set — running without vector memory (demo mode).")

    orchestrator = Orchestrator(llm_service=llm, embedding_service=embed)

    with st.spinner("Running planner..."):
        result_state = orchestrator.run(state, debug=debug)

    st.success("Planning complete")

    if debug:
        st.subheader("Graph State (raw)")
        st.json(result_state.model_dump())

    st.subheader("Final Summary")
    final = result_state.final_output or {}
    st.write(final.get("summary", "No summary generated"))

    st.subheader("Itinerary")
    st.write(result_state.itinerary or {})

    if result_state.pdf_status and result_state.pdf_status.path:
        txt_path = result_state.pdf_status.path
        with open(txt_path, "r", encoding="utf-8") as f:
            st.download_button("Download TXT Report", f, file_name=os.path.basename(txt_path))
