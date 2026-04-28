Trip Planner scaffold created. Caveman speak summary below.

Me build Multi-Agent Trip Planner. Many small helpers inside.
App take where from, where to, dates, budget, people, tastes.
Big brain (Orchestrator) talk to little workers:
- User Input Agent: tidy user words
- Memory Agent: look for old likes
- Weather, Transport, Hotel, Places: fetch facts or mock
- Budget Agent: add numbers and check wallet
- Itinerary Agent: make day plans
- Final Review Agent: check problems
- PDF Agent: make pretty paper

Me use Sarvam for thinking (LLM) and OpenAI for remembering (embeddings).
Me use Streamlit for UI and ReportLab for PDF.
When done, user get download.

- 