"""
Quick local test for Phase 10 ingredient verification — run this on your
own machine where GROQ_API_KEY is set (backend/.env), to check:
  1. Real Groq call returns valid, plausible classifications
  2. Latency of a single batched call with a realistic ingredient count

Usage (from the backend/ folder, with venv active):
    python test_verify_live.py
"""
import asyncio
import time
import sys
sys.path.insert(0, ".")

from models.schemas import IngredientResult
from services.ingredient_verify import verify_unflagged_ingredients

# Mix of well-known-safe, obscure/rare, and made-up ingredients to see how
# the model handles each bucket.
TEST_INGREDIENTS = [
    "Water", "Glycerin", "Titanium Dioxide", "Niacinamide", "Squalane",
    "Sodium Hyaluronate", "Panthenol", "Tocopherol", "Xanthan Gum",
    "Caprylic/Capric Triglyceride", "Cetearyl Alcohol", "Phenoxyethanol",
    "Some Totally Made Up Extract 12345", "Zzyzx-Compound-9",
    "Rosa Multiflora Fruit Extract", "Disteardimonium Hectorite",
] * 3  # x3 to simulate a ~48-ingredient label and measure realistic latency


async def main():
    results = [IngredientResult(ingredient=n) for n in TEST_INGREDIENTS]
    print(f"Testing with {len(results)} unflagged ingredients...\n")

    start = time.monotonic()
    out = await verify_unflagged_ingredients(results)
    elapsed = time.monotonic() - start

    for r in out[:16]:  # only show the unique first 16, rest are repeats
        print(f"{r.ingredient:40} -> {r.verification_status!s:15} | {r.verification_note}")

    verified = sum(1 for r in out if r.verification_status == "verified_safe")
    uncertain = sum(1 for r in out if r.verification_status != "verified_safe")
    print(f"\n{verified} verified_safe, {uncertain} uncertain/unclassified")
    print(f"Elapsed: {elapsed:.2f}s for {len(results)} ingredients in one batched call")

if __name__ == "__main__":
    asyncio.run(main())
