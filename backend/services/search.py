"""
services/search.py — Phase 6: Tavily web search integration.

Fallback for flagged chemicals that have no `research_url` in MongoDB.
Called ONLY when a matched chemical's research_url is null — never for
every request (SPEC.md, CLAUDE.md, project_rule.md).

Rules enforced here:
- Max 5 Tavily calls per single user request (free tier: 1,000/month).
- Results are returned as a TEMPORARY value on the response only —
  never written back to MongoDB. Adding a permanent research_url is a
  manual admin decision (Atlas UI), per decisions.md.
- Tavily failures/empty results degrade to `research_url = None` —
  never surfaced as an error to the user.
"""

import asyncio
import logging
from typing import List, Optional

from tavily import TavilyClient

from services.config import settings
from models.schemas import IngredientResult

logger = logging.getLogger(__name__)

MAX_TAVILY_CALLS_PER_REQUEST = 5
SEARCH_QUERY_SUFFIX = "cancer carcinogen cosmetic research study"

_client: Optional[TavilyClient] = None
_client_checked = False


def _get_client() -> Optional[TavilyClient]:
    """
    Lazily creates the Tavily client. Returns None (and logs once) if
    TAVILY_API_KEY isn't configured, so the feature degrades gracefully
    instead of crashing every scan.
    """
    global _client, _client_checked
    if _client is not None:
        return _client
    if not settings.TAVILY_API_KEY:
        if not _client_checked:
            logger.info("TAVILY_API_KEY not set — research URL enrichment disabled.")
            _client_checked = True
        return None
    _client = TavilyClient(api_key=settings.TAVILY_API_KEY)
    return _client


def _search_sync(chemical_name: str) -> Optional[str]:
    """
    Blocking Tavily call (tavily-python has no native async client) —
    always run through asyncio.to_thread so it doesn't block the event loop.
    """
    client = _get_client()
    if client is None:
        return None
    try:
        response = client.search(
            query=f"{chemical_name} {SEARCH_QUERY_SUFFIX}",
            max_results=1,
        )
        results = response.get("results") or []
        if results:
            return results[0].get("url")
        return None
    except Exception as e:
        # Tavily failure must never surface to the user — log and move on.
        logger.warning(f"Tavily search failed for '{chemical_name}': {e}")
        return None


async def enrich_with_research_urls(results: List[IngredientResult]) -> List[IngredientResult]:
    """
    For flagged ingredients whose matched chemical has no research_url,
    fetches a temporary one from Tavily — mutates and returns the same list.

    Hard-caps at MAX_TAVILY_CALLS_PER_REQUEST regardless of how many
    chemicals are missing a URL, per SPEC.md / CLAUDE.md / project_rule.md.
    """
    if _get_client() is None:
        return results

    calls_made = 0
    for result in results:
        if calls_made >= MAX_TAVILY_CALLS_PER_REQUEST:
            break
        if not result.is_flagged or not result.matched_chemical or result.research_url:
            continue

        url = await asyncio.to_thread(_search_sync, result.matched_chemical)
        calls_made += 1
        if url:
            result.research_url = url

    if calls_made:
        logger.info(f"Tavily usage — {calls_made} call(s) this request (max {MAX_TAVILY_CALLS_PER_REQUEST}).")

    return results