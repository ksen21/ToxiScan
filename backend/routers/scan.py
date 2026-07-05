"""
Scan endpoints — text-based and image-based ingredient scanning.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from motor.motor_asyncio import AsyncIOMotorDatabase

from services.db import get_db
from services.scanner import scan_ingredients, calculate_safety_score, derive_display_scores
from services.ocr import extract_ingredients_from_image
from services.search import enrich_with_research_urls
from models.schemas import ScanRequest, ScanResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scan", tags=["Scan"])

MAX_IMAGE_SIZE_MB = 8
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


@router.post("/text", response_model=ScanResponse)
async def scan_text(
    payload: ScanRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Accepts a raw ingredient list (comma-separated text) and returns
    a safety score + flagged ingredients.
    """
    if not payload.ingredients_text.strip():
        raise HTTPException(status_code=400, detail="ingredients_text cannot be empty")

    results = await scan_ingredients(db, payload.ingredients_text)

    if not results:
        raise HTTPException(status_code=400, detail="No ingredients could be parsed from input")

    results = await enrich_with_research_urls(results)

    score, label = calculate_safety_score(results)
    score_out_of_10, star_rating = derive_display_scores(score)
    flagged_count = sum(1 for r in results if r.is_flagged)

    logger.info(
        f"Scan complete — {len(results)} ingredients, {flagged_count} flagged, score={score}"
    )

    return ScanResponse(
        product_name=payload.product_name,
        total_ingredients=len(results),
        flagged_count=flagged_count,
        safety_score=score,
        score_out_of_10=score_out_of_10,
        star_rating=star_rating,
        safety_label=label,
        results=results,
    )


@router.post("/image", response_model=ScanResponse)
async def scan_image(
    file: UploadFile = File(...),
    product_name: str = Form(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Accepts a product label photo, runs OCR (Groq Vision) to extract the
    ingredients list, then scans it the same way as /scan/text.
    """
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported image type '{file.content_type}'. Use JPEG, PNG, or WebP.",
        )

    image_bytes = await file.read()
    size_mb = len(image_bytes) / (1024 * 1024)
    if size_mb > MAX_IMAGE_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"Image too large ({size_mb:.1f}MB). Max size is {MAX_IMAGE_SIZE_MB}MB.",
        )

    try:
        ingredients_text = await extract_ingredients_from_image(image_bytes, file.content_type)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"OCR extraction failed: {e}")
        raise HTTPException(status_code=502, detail="OCR service failed. Please try again.")

    results = await scan_ingredients(db, ingredients_text)

    if not results:
        raise HTTPException(status_code=400, detail="No ingredients could be parsed from image text")

    results = await enrich_with_research_urls(results)

    score, label = calculate_safety_score(results)
    score_out_of_10, star_rating = derive_display_scores(score)
    flagged_count = sum(1 for r in results if r.is_flagged)

    logger.info(
        f"Image scan complete — {len(results)} ingredients, {flagged_count} flagged, score={score}"
    )

    return ScanResponse(
        product_name=product_name,
        total_ingredients=len(results),
        flagged_count=flagged_count,
        safety_score=score,
        score_out_of_10=score_out_of_10,
        star_rating=star_rating,
        safety_label=label,
        results=results,
    )