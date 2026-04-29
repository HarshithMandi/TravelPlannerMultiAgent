# Multi-Agent Trip Planner

This project is a portfolio-grade Multi-Agent Trip Planner using Python, Streamlit, LangGraph orchestration, Sarvam for LLM generation, and OpenAI for embeddings.

Overview
- Orchestrator-driven multi-agent workflow with a shared typed state
- SarvamLLMService for chat completions and reasoning
- OpenAIEmbeddingService for vector memory
- Streamlit UI for input, status, results, and PDF download

Architecture
- `Orchestrator` inspects shared state and routes to specialized agents
- Agents write to a shared Pydantic state object
- Memory layer supports long-term and session memory via pluggable providers

Run locally
1. Copy `.env.example` to `.env` and fill API keys.
2. Create a virtualenv and install requirements:

```bash
python -m venv .venv
source .venv/bin/activate    # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
```

3. Run Streamlit app:

```bash
streamlit run trip-planner/app.py
```

Notes
- Sarvam is used for all LLM generation and reasoning tasks.
- OpenAI is used exclusively for embeddings/vectorization.
- Travel data integrations use free APIs when keys are provided, otherwise fallback mocks are used.

Limitations & Next Steps
- This initial scaffold provides full architecture and core modules. Add more robust provider implementations and more detailed prompts as needed.
