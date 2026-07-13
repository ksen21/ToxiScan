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
        max_length=20000,  # generous for even long labels, but bounds worst-case input
        description="Raw ingredient list pasted from a product label",
        json_schema_extra={"example": "Water, Sodium Lauryl Sulfate, Parabens, Fragrance"},
    )
    product_name: Optional[str] = Field(default=None, max_length=300)


class ProductNameScanRequest(BaseModel):
    """Search-by-product-name scan request — no ingredients text needed."""
    product_name: str = Field(
        ...,
        min_length=2,
        max_length=300,
        description="Product name to search the web for, e.g. 'CeraVe Moisturizing Cream'",
        json_schema_extra={"example": "Lakme 9to5 Hya Beach Edit Lipstick"},
    )


class IngredientResult(BaseModel):
    ingredient: str
    matched_chemical: Optional[str] = None   # name from DB
    severity: Optional[SeverityLevel] = None
    concerns: List[str] = []
    is_flagged: bool = False
    research_url: Optional[str] = None       # from DB, or temporary Tavily result (Phase 6)
    # Verification for NON-flagged ingredients only (see services/ingredient_verify.py).
    # None means "not verified" — frontend must treat this as uncertain, never as safe.
    verification_status: Optional[str] = None   # "verified_safe" | "uncertain" | None
    verification_note: Optional[str] = None


class ScanResponse(BaseModel):
    product_name: Optional[str] = None
    total_ingredients: int
    flagged_count: int
    safety_score: int = Field(..., ge=0, le=100)  # 100 = safest
    score_out_of_10: float                         # e.g. 6.6 — for "6.6/10" display
    star_rating: float                             # e.g. 3.3 — out of 5, for star widgets
    safety_label: str                              # "Safe", "Moderate", "Risky", "Dangerous"
    results: List[IngredientResult]
    scanned_at: datetime = Field(default_factory=datetime.utcnow)
    # Transparency note on WHERE the ingredients actually came from — most
    # relevant when a fallback path was used (e.g. a photo only showed the
    # product's front, so we searched the web using the name read off that
    # same photo instead of the ingredients panel). None for the plain,
    # direct paths (pasted text / OCR from a label photo).
    source_note: Optional[str] = None


# ─── Health Check ─────────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    environment: str
    db_connected: bool