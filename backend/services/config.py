"""
App settings — loaded from .env file via pydantic-settings.
"""

from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # MongoDB
    MONGODB_URI: str

    # AI APIs
    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    # Web Search
    TAVILY_API_KEY: str = ""

    # App
    APP_ENV: str = "development"
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    @property
    def origins_list(self) -> List[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


# mypy sees this as a missing required argument since MONGODB_URI has no
# default — but pydantic-settings populates it from the environment/.env
# file at runtime, which mypy has no way to verify statically. Known,
# expected false positive for BaseSettings subclasses.
settings = Settings()  # type: ignore[call-arg]