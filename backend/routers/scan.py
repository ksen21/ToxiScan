"""
Scan endpoints — text-based, image-based, and product-name-based ingredient scanning.

Error-handling contract for every route below (so the frontend can always
show the user *something* useful instead of a raw crash):
- 400: caller's fault, message explains exactly what to fix (bad input,
  too many ingredients, unsupported file type/size, nothing parseable).
- 422: we understood the request but couldn't find a real answer for it
  (OCR found no ingredients, web lookup found no ingredients) — always
  paired with a suggestion of another input method to try instead.
- 502: an external dependency (Groq/Tavily) failed — not the user's fault.
- 503: our own database is unreachable right now.
- 500: truly unexpected — caught here with logging, then re-raised so
  main.py's global handler turns it into a generic safe message (never
  leaks internals to the client either way).
"""

import logging
from pymongo.errors import PyMongoError
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from motor.motor_asyncio import AsyncIOMotorDatabase

from services.db import get_db
from services.scanner import scan_ingredients, calculate_safety_score, derive_display_scores
from services.ocr import extract_ingredients_from_image, extract_product_name_from_image
from services.search import enrich_with_research_urls
from services.ingredient_verify import verify_unflagged_ingredients
from services.product_lookup import find_ingredients_by_product_name
from services.rate_limit import limiter
from models.schemas import ScanRequest, ScanResponse, ProductNameScanRequest

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scan", tags=["Scan"])

MAX_IMAGE_SIZE_MB = 8
MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


async def _finish_scan(
    db: AsyncIOMotorDatabase,
    ingredients_text: str,
    product_name,
    source_note: str | None = None,
):
    """
    Shared tail end of all three routes: match against DB, enrich with
    research URLs, verify unflagged ingredients, score, and build the
    response. Centralized so every caller gets identical error handling
    (previously duplicated 3x, which meant a fix in one place could easily
    be missed in the others).

    Raises HTTPException directly — callers should let it propagate.
    """
    try:
        results = await scan_ingredients(db, ingredients_text)
    except ValueError as e:
        # e.g. too many ingredients (services/scanner.py's MAX_INGREDIENTS_PER_SCAN)
        raise HTTPException(status_code=400, detail=str(e))
    except PyMongoError as e:
        logger.error(f"MongoDB error during scan_ingredients: {e}")
        raise HTTPException(
            status_code=503,
            detail="Our database is temporarily unavailable. Please try again in a moment.",
        )

    if not results:
        raise HTTPException(status_code=400, detail="No ingredients could be parsed from input")

    try:
        results = await enrich_with_research_urls(results)
    except Exception as e:
        # Non-fatal by design (services/search.py already degrades internally),
        # but guard here too in case of an unexpected exception shape — a
        # missing research link should never block the whole scan result.
        logger.warning(f"enrich_with_research_urls raised unexpectedly, continuing without it: {e}")

    try:
        results = await verify_unflagged_ingredients(results)
    except Exception as e:
        # Same reasoning — "Good ingredients" verification is informational
        # only and must never be able to take down the whole scan.
        logger.warning(f"verify_unflagged_ingredients raised unexpectedly, continuing without it: {e}")

    score, label = calculate_safety_score(results)
    score_out_of_10, star_rating = derive_display_scores(score)
    flagged_count = sum(1 for r in results if r.is_flagged)

    logger.info(
        f"Scan complete — product={product_name!r}, {len(results)} ingredients, "
        f"{flagged_count} flagged, score={score}"
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
        source_note=source_note,
    )


@router.post("/text", response_model=ScanResponse)
@limiter.limit("20/minute")
async def scan_text(
    request: Request,
    payload: ScanRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Accepts a raw ingredient list (comma-separated text) and returns
    a safety score + flagged ingredients.
    """
    # Case: whitespace-only input (e.g. "   ") passes Pydantic's min_length=3
    # check (it counts raw characters, spaces included) but is meaningless —
    # catch it explicitly with a clearer message than the generic "no
    # ingredients parsed" one below.
    if not payload.ingredients_text.strip():
        raise HTTPException(status_code=400, detail="ingredients_text cannot be empty")

    return await _finish_scan(db, payload.ingredients_text, payload.product_name)


@router.post("/product-name", response_model=ScanResponse)
@limiter.limit("10/minute")
async def scan_product_name(
    request: Request,
    payload: ProductNameScanRequest,
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Accepts only a product name (or a direct product-page URL) — searches
    the web for that product's real ingredients list, then scans it the
    same way as /scan/text.
    """
    # Case: whitespace-only product name — same reasoning as /scan/text above.
    if not payload.product_name.strip():
        raise HTTPException(status_code=400, detail="product_name cannot be empty")

    try:
        ingredients_text = await find_ingredients_by_product_name(payload.product_name)
    except ValueError as e:
        # Case: nothing found anywhere (no TAVILY_API_KEY, no search hits,
        # or the LLM couldn't find a real ingredients list in what it got).
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        # Case: Tavily/Groq itself errored (auth failure, outage, malformed
        # response) rather than just "found nothing" — different from the
        # ValueError case above, so it gets a distinct 502 instead of 422.
        logger.error(f"Product-name lookup failed: {e}")
        raise HTTPException(status_code=502, detail="Search service failed. Please try again.")

    return await _finish_scan(db, ingredients_text, payload.product_name)


@router.post("/image", response_model=ScanResponse)
@limiter.limit("15/minute")
async def scan_image(
    request: Request,
    file: UploadFile = File(...),
    product_name: str = Form(None),
    db: AsyncIOMotorDatabase = Depends(get_db),
):
    """
    Accepts a product label photo, runs OCR (Groq Vision) to extract the
    ingredients list, then scans it the same way as /scan/text.
    """
    # Case: no filename / empty upload field — UploadFile always exists once
    # FastAPI's File(...) validation passes, but a browser can still submit
    # an empty file input as a zero-byte file with an empty filename.
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file was uploaded.")

    # Case: wrong/unsupported file type (also covers HEIC/HEIC from iPhones,
    # which report a content_type our OCR model can't read reliably) —
    # checked BEFORE reading the file into memory, so a bad request never
    # even needs the bytes.
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unsupported image type '{file.content_type}'. Use JPEG, PNG, or WebP "
                "(iPhone photos are often HEIC by default — switch your camera format, "
                "or choose 'Actual Size' / export as JPEG when picking the photo)."
            ),
        )

    # Case: attacker/mistake uploads a multi-hundred-MB file. Read in bounded
    # chunks and bail out the moment we cross the limit, instead of loading
    # the entire file into memory first and rejecting only afterward — the
    # old code did `image_bytes = await file.read()` unconditionally, which
    # meant a 2GB "image" would fully buffer in RAM before ever checking size.
    chunk_size = 1024 * 1024  # 1MB
    chunks = []
    total_bytes = 0
    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > MAX_IMAGE_SIZE_BYTES:
            raise HTTPException(
                status_code=400,
                detail=f"Image too large. Max size is {MAX_IMAGE_SIZE_MB}MB.",
            )
        chunks.append(chunk)
    image_bytes = b"".join(chunks)

    # Case: file type header said "image/jpeg" etc. but the body is empty
    # or truncated (0 bytes) — e.g. a flaky upload connection.
    if not image_bytes:
        raise HTTPException(status_code=400, detail="The uploaded image appears to be empty.")

    try:
        ingredients_text = await extract_ingredients_from_image(image_bytes, file.content_type)
    except ValueError as ocr_error:
        # Case: no ingredients panel visible in the photo (e.g. user
        # photographed the front of the box). Instead of dead-ending here,
        # try reading the product's brand/name off the SAME photo and fall
        # back to a real web search for its ingredients — still genuine
        # sourced data, never a guess (see product_lookup.py's
        # _simplify_query comment on why we don't fabricate instead).
        detected_name = await extract_product_name_from_image(image_bytes, file.content_type)
        if not detected_name:
            # No ingredients AND no readable product name — nothing left to
            # try automatically. Surface the original, specific OCR message.
            raise HTTPException(status_code=422, detail=str(ocr_error))

        try:
            ingredients_text = await find_ingredients_by_product_name(detected_name)
        except ValueError:
            # Detected a name, but couldn't find ITS ingredients online either.
            raise HTTPException(
                status_code=422,
                detail=(
                    f"No ingredients panel was visible in the photo, and we couldn't find "
                    f"ingredients for '{detected_name}' (read from the photo) online either. "
                    "Try a photo of the ingredients panel, or paste the ingredients directly."
                ),
            )
        except Exception as e:
            logger.error(f"Product-name fallback lookup failed for '{detected_name}': {e}")
            raise HTTPException(status_code=502, detail="Search service failed. Please try again.")

        # Fallback succeeded — use the photo-detected name unless the user
        # already typed one in the form themselves (their explicit input wins).
        product_name = product_name or detected_name
        return await _finish_scan(
            db,
            ingredients_text,
            product_name,
            source_note=(
                f"No ingredients panel was visible in this photo — these ingredients are from "
                f"a web search for '{detected_name}', the product name read off the photo."
            ),
        )
    except Exception as e:
        # Case: Groq itself errored (rate limit, outage, malformed response).
        logger.error(f"OCR extraction failed: {e}")
        raise HTTPException(status_code=502, detail="OCR service failed. Please try again.")

    return await _finish_scan(db, ingredients_text, product_name)
