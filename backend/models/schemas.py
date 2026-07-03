"""
Pydantic v2 models for ToxiScan request/response shapes.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum
from datetime import datetime


# ─── Enums ────────────────────────────────────────────────────────────────────

class SeverityLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class ChemicalCategory(str, Enum):
    PRESERVATIVE = "preservative"
    SURFACTANT = "surfactant"
    FRAGRANCE = "fragrance"
    COLORANT = "colorant"
    SUNSCREEN = "sunscreen"
    PARABEN = "paraben"
    SILICONE = "silicone"
    ALCOHOL = "alcohol"
    OTHER = "other"


# ─── Chemical Models ──────────────────────────────────────────────────────────

class ChemicalBase(BaseModel):
    name: str
    aliases: List[str] = []
    category: ChemicalCategory
    severity: SeverityLevel
    concerns: List[str] = []          # e.g. ["carcinogen", "skin irritant"]
    description: str = ""
    safe_limit: Optional[str] = None  # e.g. "< 0.1%"
    sources: List[str] = []           # reference links


class ChemicalOut(ChemicalBase):
    id: str = Field(alias="_id")

    class Config:
        populate_by_name = True


# ─── Scan Models ──────────────────────────────────────────────────────────────

class ScanRequest(BaseModel):
    """Text-based ingredient scan request."""
    ingredients_text: str = Field(
        ...,
        min_length=3,
        description="Raw ingredient list pasted from a product label",
        example="Water, Sodium Lauryl Sulfate, Parabens, Fragrance"
    )
    product_name: Optional[str] = None


class IngredientResult(BaseModel):
    ingredient: str
    matched_chemical: Optional[str] = None   # name from DB
    severity: Optional[SeverityLevel] = None
    concerns: List[str] = []
    is_flagged: bool = False
    research_url: Optional[str] = None       # from DB, or temporary Tavily result (Phase 6)


class ScanResponse(BaseModel):
    product_name: Optional[str] = None
    total_ingredients: int
    flagged_count: int
    safety_score: int = Field(..., ge=0, le=100)  # 100 = safest
    safety_label: str                              # "Safe", "Moderate", "Risky", "Dangerous"
    results: List[IngredientResult]
    scanned_at: datetime = Field(default_factory=datetime.utcnow)


# ─── Health Check ─────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    environment: str
    db_connected: bool