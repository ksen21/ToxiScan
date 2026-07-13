"""
services/ingredient_verify.py — "Good ingredients" verification.

Problem this fixes: previously, ANY ingredient not matched against our
curated `chemicals` DB was displayed to the user as "Good" — but "not in
our ~67-chemical DB" is not the same claim as "verified safe". Our DB only
covers a curated set of known-harmful chemicals; it says nothing about the
other ingredients one way or the other.

What this does: for ingredients that did NOT match the harmful-chemicals
DB, makes ONE batched Groq call asking the model to classify each based on
its trained knowledge of cosmetic ingredient science, as either:
  - "verified_safe"  — well-established in cosmetic science as safe at
                        typical use levels (e.g. Water, Glycerin, Titanium
                        Dioxide as a pigment)
  - "uncertain"       — the model isn't confident there's a clear safety
                        consensus (limited data, mixed evidence, or the
                        model simply doesn't recognize the ingredient)

Deliberately conservative: the prompt instructs the model to default to
"uncertain" whenever it isn't confident, since overclaiming safety is worse
than under-claiming it. This is informational only — it does NOT feed into
`safety_score`, which stays pure Python math per project_rule.md ("Safety
scoring NEVER done by AI").

Scope decision (per user): trained-knowledge only, no Tavily/web search
here — one fast batched call, not N calls or a slower research pass.
"""

import json
import logging
from typing import List

from groq import AsyncGroq

from services.config import settings
from models.schemas import IngredientResult

logger = logging.getLogger(__name__)

TEXT_MODEL = "llama-3.3-70b-versatile"

# Keep the batch bounded — a product label rarely has more than ~60
# ingredients, and this keeps the prompt/response small and fast.
MAX_INGREDIENTS_PER_CALL = 60

VERIFY_PROMPT = """You are a cosmetic ingredient safety reference. You will \
be given a list of ingredient names found on a personal care product label. \
These ingredients were NOT found in a separate curated database of known-\
harmful chemicals — your job is to judge, from your own trained knowledge \
of cosmetic science and toxicology, whether each one is well-established as \
safe at typical cosmetic-use levels, or whether there's real uncertainty.

For EACH ingredient, classify it as exactly one of:
- "verified_safe": well-established in cosmetic science / regulatory \
consensus (e.g. FDA, EU CosIng, CIR) as safe at typical use levels. Use \
this ONLY when you are genuinely confident.
- "uncertain": limited or mixed safety data, you don't clearly recognize \
the ingredient, or there is a plausible reason for caution that a curated \
harmful-chemicals database might not capture. If you are not confident, \
choose this — do NOT guess "verified_safe".

For every ingredient, also give a one-sentence, plain-language reason (max \
~20 words).

Respond with ONLY a JSON object, no other text, no markdown fences, in \
exactly this shape:
{"Ingredient Name": {"status": "verified_safe", "note": "short reason"}, ...}

Ingredients to classify:
"""

_client = AsyncGroq(api_key=settings.GROQ_API_KEY, timeout=30.0)


async def verify_unflagged_ingredients(results: List[IngredientResult]) -> List[IngredientResult]:
    """
    For ingredients that did NOT match the harmful-chemicals DB
    (`is_flagged == False`), classifies each via a single batched Groq call
    as "verified_safe" or "uncertain" — mutates and returns the same list.

    Never touches flagged ingredients, and never affects safety_score.
    Degrades silently (leaves verification_status=None) on any failure —
    the frontend must treat None the same as "uncertain", never as "good"
    by default, so a failed verification can't misrepresent an ingredient
    as safe.
    """
    unflagged = [r for r in results if not r.is_flagged]
    if not unflagged:
        return results

    batch = unflagged[:MAX_INGREDIENTS_PER_CALL]
    if len(unflagged) > MAX_INGREDIENTS_PER_CALL:
        logger.info(
            f"verify_unflagged_ingredients: {len(unflagged)} unflagged ingredients, "
            f"only verifying first {MAX_INGREDIENTS_PER_CALL} (rest left as uncertain)."
        )

    names = [r.ingredient for r in batch]

    try:
        response = await _client.chat.completions.create(
            model=TEXT_MODEL,
            messages=[
                {"role": "user", "content": VERIFY_PROMPT + "\n".join(f"- {n}" for n in names)}
            ],
            temperature=0.1,
            max_tokens=2048,
        )
        raw = (response.choices[0].message.content or "").strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        classification = json.loads(raw)
    except Exception as e:
        logger.warning(f"Ingredient verification failed, leaving all as uncertain: {e}")
        return results

    # Case-insensitive lookup since the model may not echo names back with
    # identical casing/whitespace.
    lookup = {k.strip().lower(): v for k, v in classification.items() if isinstance(v, dict)}

    verified_count = 0
    for result in batch:
        entry = lookup.get(result.ingredient.strip().lower())
        if not entry:
            continue
        status = entry.get("status")
        if status not in ("verified_safe", "uncertain"):
            continue
        result.verification_status = status
        result.verification_note = (entry.get("note") or "")[:200] or None
        if status == "verified_safe":
            verified_count += 1

    logger.info(
        f"Ingredient verification — {len(batch)} checked, {verified_count} verified_safe, "
        f"{len(batch) - verified_count} uncertain."
    )
    return results
