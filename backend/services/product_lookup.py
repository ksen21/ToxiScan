"""
services/product_lookup.py — Phase: Search-by-product-name.

Given only a product name (or a direct product-page URL), finds that
product's real ingredient list, so it can be fed into the same
scan_ingredients() pipeline as /scan/text.

Three paths, tried in order for plain product-name input:
1. URL given directly (user pastes a product page link) — use Tavily's
   `extract()` API to pull the FULL raw page content for that exact URL.
   This is far more reliable than search: no guessing which result is
   right, no short snippet that might miss the ingredients section.
2. INCIDecoder-scoped search (product name only, no URL) — Tavily search
   restricted to `incidecoder.com` via `include_domains`. INCIDecoder is a
   curated skincare-ingredient database with a consistent, noise-free
   layout (ingredients are listed plainly, not buried in marketing copy),
   so when a match exists there it's the highest-confidence source for
   skincare/cosmetic products specifically.
3. General web search fallback — Tavily search across the open web with
   `include_raw_content=True` so each result returns full page content
   (not just a short snippet), for products INCIDecoder doesn't cover.

Whichever path succeeds, the (possibly large/noisy) page content is then
handed to a Groq text model to pull out ONLY the ingredients list — same
"extract, don't narrate" contract as ocr.py's image-extraction prompt.

Degrades with a clear ValueError (never a silent empty scan) when:
- TAVILY_API_KEY isn't configured
- No search/extract results come back from any path
- The LLM can't find a real ingredient list in what it was given
"""

import asyncio
import logging
import re
from typing import Optional

from groq import AsyncGroq
from tavily import TavilyClient

from services.config import settings

logger = logging.getLogger(__name__)

MAX_SEARCH_RESULTS = 4
MAX_CONTENT_CHARS = 12000  # per-source cap before handing to the LLM
TEXT_MODEL = "llama-3.3-70b-versatile"

# Curated ingredient databases to check first for plain product-name input —
# these list ingredients plainly with far less noise than brand/retailer
# pages, so a hit here is higher-confidence than a general web search.
PREFERRED_INGREDIENT_DOMAINS = ["incidecoder.com"]

_groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY)
_tavily_client: Optional[TavilyClient] = None
_tavily_checked = False

URL_PATTERN = re.compile(r"^https?://", re.IGNORECASE)

EXTRACTION_PROMPT = (
    "You are given raw web content about a cosmetic/beauty product — it may "
    "include a lot of unrelated page content (navigation, other products, "
    "policies, etc.) alongside the real product details. Find the product's "
    "actual ingredients list (INCI list) somewhere in this content and "
    "return ONLY that list, as a single comma-separated line, exactly as it "
    "would appear on the product label. Do not add commentary, headers, "
    "explanations, or markdown. If the ingredients list is not clearly "
    "present in the content below, respond with exactly: NO_INGREDIENTS_FOUND"
)


def _get_tavily_client() -> Optional[TavilyClient]:
    global _tavily_client, _tavily_checked
    if _tavily_client is not None:
        return _tavily_client
    if not settings.TAVILY_API_KEY:
        if not _tavily_checked:
            logger.info("TAVILY_API_KEY not set — search-by-product-name disabled.")
            _tavily_checked = True
        return None
    _tavily_client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    return _tavily_client


def _extract_url_sync(url: str) -> str:
    """
    Fetches the FULL raw content of a specific product-page URL via
    Tavily's extract API. Used when the user gives us a direct link
    instead of just a product name — much more reliable than search
    since we already know exactly which page to read.
    """
    client = _get_tavily_client()
    if client is None:
        return ""
    try:
        response = client.extract(urls=[url])
        results = response.get("results") or []
        if not results:
            failed = response.get("failed_results") or []
            if failed:
                logger.warning(f"Tavily extract failed for '{url}': {failed}")
            return ""
        content = results[0].get("raw_content", "") or ""
        return content[:MAX_CONTENT_CHARS]
    except Exception as e:
        logger.warning(f"Tavily extract failed for '{url}': {e}")
        return ""


def _search_preferred_domains_sync(product_name: str) -> str:
    """
    Tavily search scoped to curated ingredient databases (currently just
    INCIDecoder) via `include_domains`. Tried first for plain product-name
    input, since these sites list ingredients cleanly with far less noise
    than a brand/retailer page — a hit here is the highest-confidence
    result available for skincare/cosmetic products.

    Returns "" (not an error) if nothing is found here — caller falls
    back to a general web search in that case.
    """
    client = _get_tavily_client()
    if client is None:
        return ""
    try:
        response = client.search(
            query=product_name,
            max_results=2,
            search_depth="advanced",
            include_raw_content=True,
            include_domains=PREFERRED_INGREDIENT_DOMAINS,
        )
        results = response.get("results") or []
        chunks = []
        for r in results:
            title = r.get("title", "")
            content = r.get("raw_content") or r.get("content", "")
            if content:
                chunks.append(f"Source: {title}\n{content[:MAX_CONTENT_CHARS]}")
        return "\n\n".join(chunks)
    except Exception as e:
        logger.warning(f"Tavily preferred-domain search failed for '{product_name}': {e}")
        return ""


def _search_sync(product_name: str) -> str:
    """
    Blocking Tavily call — run through asyncio.to_thread. Returns concatenated
    FULL page content (raw_content) from top results, not just short
    snippets, or "" if search failed / found nothing.
    """
    client = _get_tavily_client()
    if client is None:
        return ""
    try:
        response = client.search(
            query=f"{product_name} ingredients list INCI",
            max_results=MAX_SEARCH_RESULTS,
            search_depth="advanced",
            include_raw_content=True,
        )
        results = response.get("results") or []
        chunks = []
        for r in results:
            title = r.get("title", "")
            # Prefer full raw_content; fall back to the short snippet
            # if raw_content wasn't available for that particular result.
            content = r.get("raw_content") or r.get("content", "")
            if content:
                chunks.append(f"Source: {title}\n{content[:MAX_CONTENT_CHARS]}")
        return "\n\n".join(chunks)
    except Exception as e:
        logger.warning(f"Tavily product search failed for '{product_name}': {e}")
        return ""


async def find_ingredients_by_product_name(product_name_or_url: str) -> str:
    """
    Looks up `product_name_or_url` and returns a comma-separated
    ingredients string, ready to be passed into scan_ingredients().

    If the input looks like a URL, fetches that exact page directly
    (Tavily extract) instead of doing a generic web search — the user
    already told us exactly where to look.

    Raises ValueError (with a user-facing message) if search/extract is
    unavailable or no ingredients list could be found — caller should
    surface this as a 422/400 and suggest pasting ingredients manually.
    """
    query = (product_name_or_url or "").strip()
    if not query:
        raise ValueError("Product name is required to search for ingredients.")

    is_url = bool(URL_PATTERN.match(query))

    if is_url:
        web_content = await asyncio.to_thread(_extract_url_sync, query)
        source_note = "direct URL"
        if not web_content:
            raise ValueError(
                "Couldn't read that product page right now. "
                "Try pasting the ingredients list or uploading a label photo instead."
            )
    else:
        web_content = await asyncio.to_thread(_search_preferred_domains_sync, query)
        source_note = "curated ingredient database"
        if not web_content:
            web_content = await asyncio.to_thread(_search_sync, query)
            source_note = "general web search"
        if not web_content:
            raise ValueError(
                "Couldn't search the web for this product right now. "
                "Try pasting the ingredients list or uploading a label photo instead."
            )

    response = await _groq_client.chat.completions.create(
        model=TEXT_MODEL,
        messages=[
            {
                "role": "user",
                "content": (
                    f"{EXTRACTION_PROMPT}\n\n"
                    f"Product: {query}\n\n"
                    f"Web content:\n{web_content[:MAX_CONTENT_CHARS]}"
                ),
            }
        ],
        temperature=0.1,
        max_tokens=1024,
    )

    text = (response.choices[0].message.content or "").strip()

    if not text or text == "NO_INGREDIENTS_FOUND":
        raise ValueError(
            f"Couldn't find a reliable ingredients list for '{query}' online. "
            "Try pasting the ingredients list, uploading a label photo, or "
            "pasting a direct product page link instead."
        )

    logger.info(
        f"Product lookup extracted {len(text)} chars for '{query}' "
        f"(url={is_url}, source={source_note})."
    )
    return text