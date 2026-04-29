import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


def _truthy_env(name: str) -> bool:
    val = (os.getenv(name, "") or "").strip().lower()
    return val in {"1", "true", "yes", "y", "on"}


def _configure_langsmith_env() -> None:
    """Normalize LangSmith/LangChain tracing env vars.

    Users often set different variable names (e.g. LANGSMITH_APIKEY). This helper
    maps them to the standard env vars consumed by langchain/langgraph tracing.
    """

    # Accept several common key names.
    api_key = (
        os.getenv("LANGSMITH_API_KEY")
        or os.getenv("LANGCHAIN_API_KEY")
        or os.getenv("LANGSMITH_APIKEY")
        or os.getenv("LANGSMITH_API_KEY_V2")
        or ""
    ).strip()

    if not api_key:
        return

    project = (os.getenv("LANGSMITH_PROJECT") or os.getenv("LANGCHAIN_PROJECT") or "trip-planner").strip() or "trip-planner"
    endpoint = (
        os.getenv("LANGSMITH_ENDPOINT")
        or os.getenv("LANGCHAIN_ENDPOINT")
        or "https://api.smith.langchain.com"
    ).strip()

    # Prefer explicit user-provided flags; otherwise enable when key is present.
    tracing_enabled = (
        _truthy_env("LANGSMITH_TRACING")
        or _truthy_env("LANGCHAIN_TRACING_V2")
        or _truthy_env("LANGCHAIN_TRACING")
        or True
    )

    os.environ.setdefault("LANGSMITH_API_KEY", api_key)
    os.environ.setdefault("LANGCHAIN_API_KEY", api_key)
    os.environ.setdefault("LANGSMITH_PROJECT", project)
    os.environ.setdefault("LANGCHAIN_PROJECT", project)
    os.environ.setdefault("LANGSMITH_ENDPOINT", endpoint)
    os.environ.setdefault("LANGCHAIN_ENDPOINT", endpoint)

    if tracing_enabled:
        os.environ.setdefault("LANGSMITH_TRACING", "true")
        os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")


_configure_langsmith_env()


@dataclass(frozen=True)
class Settings:
    SARVAM_API_KEY: str = ""
    SARVAM_MODEL: str = "sarvam-m"
    OPENAI_API_KEY: str = ""
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENWEATHERMAP_API_KEY: str = ""
    OPENTRIPMAP_API_KEY: str = ""
    OPENROUTESERVICE_API_KEY: str = ""
    GEOAPIFY_API_KEY: str = ""
    REDIS_URL: str = ""
    CHROMA_PERSIST_DIR: str = "./data/chroma"
    MEMORY_MAX_ENTRIES: int = 200
    MEMORY_ENABLED: bool = False
    MEMORY_UPDATE_ENABLED: bool = False
    MEMORY_TOP_K: int = 1
    LANGSMITH_API_KEY: str = ""
    LANGSMITH_PROJECT: str = "trip-planner"
    LANGSMITH_TRACING: bool = False
    WORKER_LLM_ENABLED: bool = False
    AGENT_REASONING_LLM_ENABLED: bool = False
    DEFAULT_CURRENCY: str = "INR"
    DEFAULT_COUNTRY: str = "IN"
    LOG_LEVEL: str = "INFO"


settings = Settings(
    SARVAM_API_KEY=os.getenv("SARVAM_API_KEY", "").strip(),
    SARVAM_MODEL=os.getenv("SARVAM_MODEL", "sarvam-m"),
    OPENAI_API_KEY=os.getenv("OPENAI_API_KEY", "").strip(),
    OPENAI_EMBEDDING_MODEL=os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
    OPENWEATHERMAP_API_KEY=os.getenv("OPENWEATHERMAP_API_KEY", ""),
    OPENTRIPMAP_API_KEY=os.getenv("OPENTRIPMAP_API_KEY", ""),
    OPENROUTESERVICE_API_KEY=os.getenv("OPENROUTESERVICE_API_KEY", ""),
    GEOAPIFY_API_KEY=(
        os.getenv("GEOAPIFY_API_KEY")
        or os.getenv("GEOAPIFY_KEY")
        or os.getenv("GEOAPIFY_APIKEY")
        or ""
    ).strip(),
    REDIS_URL=os.getenv("REDIS_URL", ""),
    CHROMA_PERSIST_DIR=os.getenv("CHROMA_PERSIST_DIR", "./data/chroma"),
    MEMORY_MAX_ENTRIES=int(os.getenv("MEMORY_MAX_ENTRIES", "200")),
    MEMORY_ENABLED=_truthy_env("MEMORY_ENABLED"),
    MEMORY_UPDATE_ENABLED=_truthy_env("MEMORY_UPDATE_ENABLED"),
    MEMORY_TOP_K=max(1, int(os.getenv("MEMORY_TOP_K", "1"))),
    LANGSMITH_API_KEY=os.getenv("LANGSMITH_API_KEY", os.getenv("LANGCHAIN_API_KEY", "")).strip(),
    LANGSMITH_PROJECT=os.getenv("LANGSMITH_PROJECT", os.getenv("LANGCHAIN_PROJECT", "trip-planner")).strip() or "trip-planner",
    LANGSMITH_TRACING=_truthy_env("LANGSMITH_TRACING") or _truthy_env("LANGCHAIN_TRACING_V2") or _truthy_env("LANGCHAIN_TRACING"),
    WORKER_LLM_ENABLED=_truthy_env("WORKER_LLM_ENABLED"),
    AGENT_REASONING_LLM_ENABLED=_truthy_env("AGENT_REASONING_LLM_ENABLED"),
    DEFAULT_CURRENCY=os.getenv("DEFAULT_CURRENCY", "INR"),
    DEFAULT_COUNTRY=os.getenv("DEFAULT_COUNTRY", "IN"),
    LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),
)
