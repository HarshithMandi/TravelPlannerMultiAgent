import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    SARVAM_API_KEY: str = ""
    SARVAM_MODEL: str = "sarvam-m"
    OPENAI_API_KEY: str = ""
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENWEATHERMAP_API_KEY: str = ""
    OPENTRIPMAP_API_KEY: str = ""
    OPENROUTESERVICE_API_KEY: str = ""
    REDIS_URL: str = ""
    CHROMA_PERSIST_DIR: str = "./data/chroma"
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
    REDIS_URL=os.getenv("REDIS_URL", ""),
    CHROMA_PERSIST_DIR=os.getenv("CHROMA_PERSIST_DIR", "./data/chroma"),
    DEFAULT_CURRENCY=os.getenv("DEFAULT_CURRENCY", "INR"),
    DEFAULT_COUNTRY=os.getenv("DEFAULT_COUNTRY", "IN"),
    LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),
)
