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

    # NaraRouter — OpenAI-compatible text-model gateway, used for the
    # product-name -> ingredients extraction step in services/product_lookup.py
    # ONLY (text, not vision — NaraRouter doesn't support image input, so OCR
    # in services/ocr.py stays on Groq directly). If NARA_ROUTER_API_KEY or
    # NARA_TEXT_MODEL is left blank, that step transparently falls back to
    # the existing Groq text client instead — never a hard requirement.
    NARA_ROUTER_API_KEY: str = ""
    NARA_ROUTER_BASE_URL: str = "https://router.bynara.id/v1"
    NARA_TEXT_MODEL: str = ""  # e.g. "deepseek-3.2" — check NaraRouter's /v1/models for the exact alias

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