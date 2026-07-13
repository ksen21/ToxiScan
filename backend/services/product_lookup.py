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
from openai import AsyncOpenAI
from tavily import TavilyClient

from services.config import settings

logger = logging.getLogger(__name__)

MAX_SEARCH_RESULTS = 4
MAX_CONTENT_CHARS = 12000  # per-source cap before handing to the LLM
INGREDIENT_WINDOW_CHARS = 6000  # chars kept before/after an "ingredient" keyword hit
TEXT_MODEL = "llama-3.3-70b-versatile"

# Large e-commerce pages (nav menus, "similar products" carousels, cookie/
# privacy notices, giant category-tag footers) can easily push the real
# ingredients section past a naive head-truncation cutoff. Instead of
# blindly keeping the first MAX_CONTENT_CHARS, look for a keyword that
# usually precedes an ingredients list and keep a window around the FIRST
# hit — falls back to head truncation if no such keyword is found at all.
_INGREDIENT_KEYWORD_RE = re.compile(r"ingredient", re.IGNORECASE)


def _cap_content(content: str, limit: int = MAX_CONTENT_CHARS) -> str:
    """Keep the most relevant slice of `content` within `limit` chars."""
    if len(content) <= limit:
        return content
    match = _INGREDIENT_KEYWORD_RE.search(content)
    if not match:
        # No keyword hit anywhere — nothing smarter to do than head-truncate.
        return content[:limit]
    center = match.start()
    half = min(INGREDIENT_WINDOW_CHARS, limit // 2)
    start = max(0, center - half)
    end = min(len(content), start + limit)
    start = max(0, end - limit)  # re-clamp in case we hit the end of the string
    return content[start:end]

# Curated ingredient databases to check first for plain product-name input —
# these list ingredients plainly with far less noise than brand/retailer
# pages, so a hit here is higher-confidence than a general web search.
PREFERRED_INGREDIENT_DOMAINS = ["incidecoder.com"]

_groq_client = AsyncGroq(api_key=settings.GROQ_API_KEY, timeout=30.0)
_nara_client: Optional[AsyncOpenAI] = None
_nara_checked = False


def _get_nara_client() -> Optional[AsyncOpenAI]:
    """
    Lazily creates the NaraRouter client (OpenAI-compatible SDK, custom
    base_url). Returns None — logged once — if NARA_ROUTER_API_KEY or
    NARA_TEXT_MODEL isn't configured, so the caller can fall back to Groq
    without this being treated as an error.
    """
    global _nara_client, _nara_checked
    if _nara_client is not None:
        return _nara_client
    if not settings.NARA_ROUTER_API_KEY or not settings.NARA_TEXT_MODEL:
        if not _nara_checked:
            logger.info(
                "NARA_ROUTER_API_KEY or NARA_TEXT_MODEL not set — product-name "
                "extraction will use Groq directly instead of NaraRouter."
            )
            _nara_checked = True
        return None
    _nara_client = AsyncOpenAI(
        api_key=settings.NARA_ROUTER_API_KEY,
        base_url=settings.NARA_ROUTER_BASE_URL,
        timeout=30.0,
    )
    return _nara_client
_tavily_client: Optional[TavilyClient] = None
_tavily_checked = False

URL_PATTERN = re.compile(r"^https?://", re.IGNORECASE)

# Common separators between a product's core name and shade/variant/size
# details, e.g. "Lakme 9to5 Lipstick - Coral Pink, 3.6g" -> "Lakme 9to5 Lipstick"
_VARIANT_SEPARATOR_RE = re.compile(r"[-|–—(]")


def _simplify_query(query: str) -> str:
    """Strips trailing shade/variant/size details for the simplified-query retry."""
    core = _VARIANT_SEPARATOR_RE.split(query, maxsplit=1)[0].strip()
    words = core.split()
    return " ".join(words[:6]) if len(words) > 6 else core

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
        return _cap_content(content)
    except Exception as e:
        logger.warning(f"Tavily extract failed for '{url}': {e}")
        return ""


def _direct_fetch_sync(url: str) -> str:
    """
    Plain HTTP GET + HTML-to-text fallback for when Tavily's extract() comes
    back without an "ingredient" keyword anywhere — usually means Tavily's
    static-HTML crawl missed content that's actually present in the raw
    server response (e.g. a tab panel that's in the HTML but visually
    hidden/toggled by JS, which some crawlers strip differently than others).
    Best-effort only: no JS execution here either, just a second, independent
    read of the same URL. Returns "" on any failure.
    """
    try:
        import httpx
        from html.parser import HTMLParser

        class _TextExtractor(HTMLParser):
            def __init__(self):
                super().__init__()
                self.chunks: list[str] = []
                self._skip = False

            def handle_starttag(self, tag, attrs):
                if tag in ("script", "style", "noscript"):
                    self._skip = True

            def handle_endtag(self, tag):
                if tag in ("script", "style", "noscript"):
                    self._skip = False

            def handle_data(self, data):
                if not self._skip:
                    stripped = data.strip()
                    if stripped:
                        self.chunks.append(stripped)

        resp = httpx.get(
            url,
            timeout=10.0,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ToxiScanBot/1.0)"},
        )
        resp.raise_for_status()
        parser = _TextExtractor()
        parser.feed(resp.text)
        return _cap_content(" ".join(parser.chunks), limit=MAX_CONTENT_CHARS)
    except Exception as e:
        logger.warning(f"Direct fetch fallback failed for '{url}': {e}")
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
                chunks.append(f"Source: {title}\n{_cap_content(content)}")
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
                chunks.append(f"Source: {title}\n{_cap_content(content)}")
        return "\n\n".join(chunks)
    except Exception as e:
        logger.warning(f"Tavily product search failed for '{product_name}': {e}")
        return ""


TAVILY_CALL_TIMEOUT_S = 20.0


async def _call_with_timeout(func, *args) -> str:
    """
    Runs a blocking Tavily/httpx call in a thread with a hard timeout.
    These SDKs don't reliably expose their own timeout knobs from here, so
    without this a hung network call could block the request indefinitely
    instead of degrading the way every other failure in this file already
    does (returns "" and falls through to the next fallback / a clear
    ValueError). Timeout is treated identically to any other failure.
    """
    try:
        return await asyncio.wait_for(asyncio.to_thread(func, *args), timeout=TAVILY_CALL_TIMEOUT_S)
    except asyncio.TimeoutError:
        logger.warning(f"{func.__name__} timed out after {TAVILY_CALL_TIMEOUT_S}s for args={args}")
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
        web_content = await _call_with_timeout(_extract_url_sync, query)
        source_note = "direct URL"
        if not web_content:
            raise ValueError(
                "Couldn't read that product page right now. "
                "Try pasting the ingredients list or uploading a label photo instead."
            )
        logger.info(
            f"Tavily extract for '{query}': {len(web_content)} chars, "
            f"'ingredient' keyword present={bool(_INGREDIENT_KEYWORD_RE.search(web_content))}"
        )
        if not _INGREDIENT_KEYWORD_RE.search(web_content):
            # Tavily's extractor is static-HTML based — some storefronts load
            # tab content (Ingredients/Info/Details) via client-side JS after
            # page load, which Tavily's extract() never sees. Fall back to a
            # direct HTTP fetch of the same URL as a second attempt before
            # giving up — a plain requests/httpx GET sometimes picks up
            # server-rendered content that differs from what Tavily crawled.
            direct = await _call_with_timeout(_direct_fetch_sync, query)
            if direct and _INGREDIENT_KEYWORD_RE.search(direct):
                logger.info(f"Direct fetch fallback succeeded for '{query}' ({len(direct)} chars).")
                web_content = direct
                source_note = "direct URL (httpx fallback)"
    else:
        web_content = await _call_with_timeout(_search_preferred_domains_sync, query)
        source_note = "curated ingredient database"
        if not web_content:
            web_content = await _call_with_timeout(_search_sync, query)
            source_note = "general web search"
        if not web_content:
            # Case: an overly-specific product name (e.g. including a shade,
            # variant, or size that doesn't appear verbatim anywhere online)
            # can make an otherwise-findable product fail. Try once more with
            # a simplified query — the brand + first few words — before
            # giving up. This is still a REAL web search, never a guess: if
            # this also finds nothing, we raise exactly like before rather
            # than fabricating an ingredients list (project_rule.md: "Safety
            # scoring NEVER done by AI" — that principle extends to never
            # inventing the underlying ingredient data either).
            simplified = _simplify_query(query)
            if simplified and simplified != query:
                logger.info(f"No results for '{query}', retrying with simplified query '{simplified}'")
                web_content = await _call_with_timeout(_search_sync, simplified)
                source_note = "general web search (simplified query)"
        if not web_content:
            raise ValueError(
                "Couldn't search the web for this product right now. "
                "Try pasting the ingredients list or uploading a label photo instead."
            )

    text = await _extract_ingredients_text(query, web_content)

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


async def _extract_ingredients_text(query: str, web_content: str) -> str:
    """
    Runs the "extract just the ingredients list" prompt against the raw web
    content — via NaraRouter (text-only gateway) if configured, otherwise
    Groq directly. Text product-name lookups (typed OR read off a photo via
    services/ocr.py's fallback) both funnel through here, so both paths get
    NaraRouter when it's available — NaraRouter itself is never used for the
    image/vision step, since it doesn't support image input.

    Resilience: if NaraRouter IS configured but the call fails for any
    reason (outage, auth error, timeout), falls back to Groq automatically
    rather than failing the whole lookup — the user still gets a real
    result either way (per user's explicit choice: availability over
    strict routing).
    """
    prompt_content = (
        f"{EXTRACTION_PROMPT}\n\nProduct: {query}\n\nWeb content:\n{_cap_content(web_content)}"
    )

    nara_client = _get_nara_client()
    if nara_client is not None:
        try:
            response = await nara_client.chat.completions.create(
                model=settings.NARA_TEXT_MODEL,
                messages=[{"role": "user", "content": prompt_content}],
                temperature=0.1,
                max_tokens=1024,
            )
            text = (response.choices[0].message.content or "").strip()
            logger.info(f"Ingredient extraction via NaraRouter ({settings.NARA_TEXT_MODEL}) succeeded.")
            return text
        except Exception as e:
            logger.warning(f"NaraRouter extraction failed, falling back to Groq: {e}")
            # falls through to the Groq path below

    try:
        response = await _groq_client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[{"role": "user", "content": prompt_content}],
            temperature=0.1,
            max_tokens=1024,
        )
        return (response.choices[0].message.content or "").strip()
    except Exception as e:
        # Case: Groq itself failed here too (auth/rate-limit/outage/timeout) —
        # distinct from "we searched fine but found nothing", so it should
        # surface as a 502 (service failure) not a 422 (not found).
        # Re-raised as-is; routers/scan.py's generic `except Exception`
        # around this call already maps it to a 502 with a friendly message.
        logger.error(f"Groq extraction call failed for '{query}': {e}")
        raise