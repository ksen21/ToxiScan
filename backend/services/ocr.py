"""
OCR service — extracts ingredient list text from a product label photo
using Groq's vision-capable model (Llama 4 Scout).
"""

import base64
import logging
from groq import AsyncGroq

from services.config import settings

logger = logging.getLogger(__name__)

_client = AsyncGroq(api_key=settings.GROQ_API_KEY, timeout=30.0)

VISION_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

EXTRACTION_PROMPT = (
    "You are looking at a photo of a cosmetic/beauty product label. "
    "Extract ONLY the ingredients list text, exactly as printed, as a single "
    "comma-separated line. Do not add commentary, headers, or explanations. "
    "If no ingredients list is visible, respond with exactly: NO_INGREDIENTS_FOUND"
)


def _encode_image(image_bytes: bytes, content_type: str) -> str:
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:{content_type};base64,{b64}"


async def extract_ingredients_from_image(image_bytes: bytes, content_type: str) -> str:
    """
    Sends the image to Groq's vision model and returns the extracted
    ingredient text (raw, comma-separated). Raises ValueError if none found.
    """
    data_url = _encode_image(image_bytes, content_type)

    response = await _client.chat.completions.create(
        model=VISION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": EXTRACTION_PROMPT},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ],
            }
        ],
        temperature=0.1,
        max_tokens=1024,
    )

    text = (response.choices[0].message.content or "").strip()

    if not text or text == "NO_INGREDIENTS_FOUND":
        raise ValueError(
            "No ingredients list could be detected in this photo — it might show "
            "only the front of the product. Try a photo of the ingredients panel "
            "(usually on the back/side), or search by the product's name instead."
        )

    logger.info(f"OCR extracted {len(text)} chars from image.")
    return text


NAME_EXTRACTION_PROMPT = (
    "You are looking at a photo of a cosmetic/beauty product. There is no "
    "visible ingredients list in this photo. Instead, identify the product's "
    "brand and name as printed/shown (e.g. 'CeraVe Moisturizing Cream' or "
    "'Lakme 9to5 Hya Beach Edit Lipstick'). Respond with ONLY the brand + "
    "product name, nothing else — no commentary. If you cannot confidently "
    "identify a specific product, respond with exactly: NO_NAME_FOUND"
)


async def extract_product_name_from_image(image_bytes: bytes, content_type: str) -> str | None:
    """
    Fallback used when extract_ingredients_from_image() finds no ingredients
    panel (e.g. the user photographed the front of the box instead of the
    back/side label). Tries to read the product's brand/name off the same
    photo instead, so the caller can fall back to a web search for the real
    ingredients (services/product_lookup.py) rather than dead-ending.

    Returns None (never raises) if nothing confident could be read — this is
    a best-effort assist, not a hard requirement, so a failure here should
    just mean "no fallback available," not a new error path of its own.
    """
    try:
        data_url = _encode_image(image_bytes, content_type)
        response = await _client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": NAME_EXTRACTION_PROMPT},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                }
            ],
            temperature=0.1,
            max_tokens=100,
        )
        text = (response.choices[0].message.content or "").strip()
        if not text or text == "NO_NAME_FOUND":
            return None
        logger.info(f"OCR fallback detected product name from image: '{text}'")
        return text
    except Exception as e:
        logger.warning(f"Product-name fallback extraction failed: {e}")
        return None