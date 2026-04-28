from pydantic import BaseSettings, Field, ValidationError
from dotenv import load_dotenv
import os

load_dotenv()


class Settings(BaseSettings):
    SARVAM_API_KEY: str = Field(..., env="SARVAM_API_KEY")
    SARVAM_MODEL: str = Field("sarvam-m", env="SARVAM_MODEL")
    OPENAI_API_KEY: str = Field(..., env="OPENAI_API_KEY")
    OPENAI_EMBEDDING_MODEL: str = Field("text-embedding-3-small", env="OPENAI_EMBEDDING_MODEL")
    OPENWEATHERMAP_API_KEY: str = Field(None, env="OPENWEATHERMAP_API_KEY")
    OPENTRIPMAP_API_KEY: str = Field(None, env="OPENTRIPMAP_API_KEY")
    OPENROUTESERVICE_API_KEY: str = Field(None, env="OPENROUTESERVICE_API_KEY")
    REDIS_URL: str = Field(None, env="REDIS_URL")
    CHROMA_PERSIST_DIR: str = Field("./data/chroma", env="CHROMA_PERSIST_DIR")
    DEFAULT_CURRENCY: str = Field("INR", env="DEFAULT_CURRENCY")
    DEFAULT_COUNTRY: str = Field("IN", env="DEFAULT_COUNTRY")
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")

    class Config:
        case_sensitive = True


try:
    settings = Settings()
except ValidationError as e:
    # Fail loudly if critical vars missing
    raise RuntimeError(f"Missing required environment variables: {e}")
