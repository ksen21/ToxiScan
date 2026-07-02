# implementation.md — ToxiScan Implementation Guide

> Detailed code structure, patterns, and step-by-step implementation for each service.
> Read build_plan.md for phase order. Read this for HOW to implement each piece.

---

## Directory Structure (Final)

```
toxiscan/
├── frontend/
│   ├── app/
│   │   ├── page.tsx                  ← Main UI (upload + results)
│   │   └── layout.tsx
│   ├── components/
│   │   ├── UploadForm.tsx
│   │   ├── ResultCard.tsx
│   │   ├── ChemicalCard.tsx
│   │   ├── ScoreGauge.tsx
│   │   └── Verdict.tsx
│   ├── types/
│   │   └── api.ts                    ← TypeScript types matching backend schemas
│   ├── .env.local                    ← NEXT_PUBLIC_API_URL (gitignored)
│   └── package.json
│
├── backend/
│   ├── main.py
│   ├── routers/
│   │   └── analyze.py
│   ├── services/
│   │   ├── db.py
│   │   ├── vision.py
│   │   ├── text_model.py
│   │   ├── scoring.py
│   │   └── search.py
│   ├── models/
│   │   └── schemas.py
│   ├── tests/
│   │   └── test_scoring.py
│   ├── .env                          ← All secrets (gitignored)
│   └── requirements.txt
│
├── .gitignore
└── README.md
```

---

## Backend Implementation

### requirements.txt

```
fastapi
uvicorn[standard]
motor
python-dotenv
pydantic
openai
rapidfuzz
tavily-python
python-multipart
```

---

### .env (backend)

```env
NARA_ROUTER_API_KEY=your_key_here
TAVILY_API_KEY=your_key_here
MONGODB_URI=mongodb+srv://user:pass@cluster.mongodb.net/toxiscan
VISION_MODEL=llava-v1.5-7b-4096-preview   # verify from /v1/models
TEXT_MODEL=deepseek-r1                     # verify from NaraRouter
```

---

### main.py

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import analyze
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="ToxiScan API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "https://your-app.vercel.app"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(analyze.router, prefix="/analyze", tags=["analyze"])

@app.get("/health")
async def health():
    return {"status": "ok"}
```

---

### models/schemas.py

```python
from pydantic import BaseModel
from typing import Optional

class TextAnalyzeRequest(BaseModel):
    ingredients: str

class ChemicalResult(BaseModel):
    name: str
    matched_db_name: str
    danger_type: list[str]
    description: str
    severity: str           # "High" | "Medium" | "Low"
    research_url: Optional[str] = None

class AnalyzeResponse(BaseModel):
    product_name: Optional[str] = None
    input_type: str                         # "text" | "image" | "both"
    extracted_ingredients: list[str]
    harmful_chemicals: list[ChemicalResult]
    safety_score: float
    verdict: str                            # "SAFE" | "CAUTION" | "AVOID"
```

---

### services/db.py

```python
import os
from motor.motor_asyncio import AsyncIOMotorClient

_client: AsyncIOMotorClient | None = None

def get_client() -> AsyncIOMotorClient:
    global _client
    if _client is None:
        uri = os.getenv("MONGODB_URI")
        _client = AsyncIOMotorClient(uri, maxPoolSize=10)
    return _client

def get_db():
    return get_client()["toxiscan"]

async def get_chemicals_collection():
    return get_db()["chemicals"]

async def get_logs_collection():
    return get_db()["scan_logs"]

async def query_all_chemicals() -> list[dict]:
    col = await get_chemicals_collection()
    return await col.find({}, {"_id": 0}).to_list(length=None)
```

---

### services/scoring.py

```python
def calculate_score(harmful_chemicals: list[dict]) -> float:
    score: float = 10.0
    deductions = {"High": 2.5, "Medium": 1.5, "Low": 0.5}

    for chemical in harmful_chemicals:
        severity = chemical.get("severity", "Low")
        score -= deductions.get(severity, 0.5)

    return max(0.0, round(score, 1))

def get_verdict(score: float) -> str:
    if score >= 8.0:
        return "SAFE"
    elif score >= 5.0:
        return "CAUTION"
    else:
        return "AVOID"
```

---

### services/text_model.py

```python
import os
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key=os.getenv("NARA_ROUTER_API_KEY"),
    base_url="https://router.bynara.id/v1",
)

PARSE_PROMPT = """
You are an expert in cosmetic ingredients. Extract and normalize the ingredient list from the following text.
Return ONLY a JSON array of normalized ingredient names (strings). No other text.
Normalize INCI names to common names where possible (e.g., "aqua" → "water", "parfum" → "fragrance").
"""

async def extract_ingredients_from_text(raw_text: str) -> list[str]:
    response = await client.chat.completions.create(
        model=os.getenv("TEXT_MODEL", "deepseek-r1"),
        messages=[
            {"role": "system", "content": PARSE_PROMPT},
            {"role": "user", "content": raw_text},
        ],
        max_tokens=500,
    )
    import json
    content = response.choices[0].message.content.strip()
    # Strip markdown fences if present
    content = content.replace("```json", "").replace("```", "").strip()
    return json.loads(content)
```

---

### services/vision.py

```python
import os
import base64
from openai import AsyncOpenAI

client = AsyncOpenAI(
    api_key=os.getenv("NARA_ROUTER_API_KEY"),
    base_url="https://router.bynara.id/v1",
)

VISION_PROMPT = """
You are analyzing a cosmetic product label image. Extract:
1. Product name (if visible)
2. Brand name (if visible)
3. Full ingredient list

Return ONLY a JSON object:
{
  "product_name": "string or null",
  "brand": "string or null",
  "ingredients": ["ingredient1", "ingredient2", ...]
}
No other text.
"""

async def extract_from_image(image_bytes: bytes, media_type: str = "image/jpeg") -> dict:
    b64 = base64.b64encode(image_bytes).decode("utf-8")

    response = await client.chat.completions.create(
        model=os.getenv("VISION_MODEL"),
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{media_type};base64,{b64}"},
                    },
                    {"type": "text", "text": VISION_PROMPT},
                ],
            }
        ],
        max_tokens=800,
    )

    import json
    content = response.choices[0].message.content.strip()
    content = content.replace("```json", "").replace("```", "").strip()
    result = json.loads(content)

    # Validate structure
    if not result.get("ingredients"):
        raise ValueError("Could not read ingredients from image. Please try text input.")

    return result
```

---

### services/search.py

```python
import os
from tavily import TavilyClient

client = TavilyClient(api_key=os.getenv("TAVILY_API_KEY"))

MAX_TAVILY_CALLS = 5

async def fetch_research_urls(chemicals_missing_url: list[str]) -> dict[str, str | None]:
    results: dict[str, str | None] = {}
    call_count = 0

    for chemical_name in chemicals_missing_url:
        if call_count >= MAX_TAVILY_CALLS:
            results[chemical_name] = None
            continue

        try:
            query = f"{chemical_name} cancer carcinogen cosmetic research study"
            response = client.search(query=query, max_results=1)
            urls = [r.get("url") for r in response.get("results", []) if r.get("url")]
            results[chemical_name] = urls[0] if urls else None
            call_count += 1
            print(f"[Tavily] call #{call_count} for: {chemical_name}")
        except Exception as e:
            print(f"[Tavily] error for {chemical_name}: {e}")
            results[chemical_name] = None

    return results
```

---

### routers/analyze.py (core logic)

```python
from fastapi import APIRouter, UploadFile, File, BackgroundTasks, HTTPException
from models.schemas import TextAnalyzeRequest, AnalyzeResponse, ChemicalResult
from services import db, text_model, vision, scoring, search
from rapidfuzz import fuzz
from datetime import datetime

router = APIRouter()

FUZZY_THRESHOLD = 85

async def match_chemicals(
    ingredient_list: list[str],
    chemicals_db: list[dict]
) -> list[ChemicalResult]:
    matched = []
    for ingredient in ingredient_list:
        for chemical in chemicals_db:
            # Check name + all aliases
            candidates = [chemical["name"]] + chemical.get("aliases", [])
            for candidate in candidates:
                ratio = fuzz.token_sort_ratio(ingredient.lower(), candidate.lower())
                if ratio >= FUZZY_THRESHOLD:
                    matched.append(ChemicalResult(
                        name=ingredient,
                        matched_db_name=chemical["name"],
                        danger_type=chemical["danger_type"],
                        description=chemical["description"],
                        severity=chemical["severity"],
                        research_url=chemical.get("research_url"),
                    ))
                    break
    return matched

async def write_scan_log(bg: BackgroundTasks, data: dict):
    async def _write():
        col = await db.get_logs_collection()
        await col.insert_one({**data, "timestamp": datetime.utcnow()})
    bg.add_task(_write)

@router.post("/text", response_model=AnalyzeResponse)
async def analyze_text(req: TextAnalyzeRequest, background_tasks: BackgroundTasks):
    # 1. Extract ingredients via text model
    ingredients = await text_model.extract_ingredients_from_text(req.ingredients)

    # 2. Load chemicals from MongoDB
    chemicals_db = await db.query_all_chemicals()

    # 3. Fuzzy match
    harmful = await match_chemicals(ingredients, chemicals_db)

    # 4. Tavily for missing research URLs
    missing_urls = [c.matched_db_name for c in harmful if not c.research_url]
    if missing_urls:
        url_map = await search.fetch_research_urls(missing_urls)
        for c in harmful:
            if not c.research_url and c.matched_db_name in url_map:
                c.research_url = url_map[c.matched_db_name]

    # 5. Score
    score = scoring.calculate_score([c.dict() for c in harmful])
    verdict = scoring.get_verdict(score)

    # 6. Async log (fire-and-forget)
    await write_scan_log(background_tasks, {
        "input_type": "text",
        "chemicals_found": [c.matched_db_name for c in harmful],
        "safety_score": score,
        "verdict": verdict,
    })

    return AnalyzeResponse(
        product_name=None,
        input_type="text",
        extracted_ingredients=ingredients,
        harmful_chemicals=harmful,
        safety_score=score,
        verdict=verdict,
    )

@router.post("/image", response_model=AnalyzeResponse)
async def analyze_image(background_tasks: BackgroundTasks, image: UploadFile = File(...)):
    image_bytes = await image.read()  # read into memory only, never save to disk

    try:
        extracted = await vision.extract_from_image(
            image_bytes, media_type=image.content_type or "image/jpeg"
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    ingredients = extracted.get("ingredients", [])
    product_name = extracted.get("product_name")

    chemicals_db = await db.query_all_chemicals()
    harmful = await match_chemicals(ingredients, chemicals_db)

    missing_urls = [c.matched_db_name for c in harmful if not c.research_url]
    if missing_urls:
        url_map = await search.fetch_research_urls(missing_urls)
        for c in harmful:
            if not c.research_url and c.matched_db_name in url_map:
                c.research_url = url_map[c.matched_db_name]

    score = scoring.calculate_score([c.dict() for c in harmful])
    verdict = scoring.get_verdict(score)

    await write_scan_log(background_tasks, {
        "input_type": "image",
        "chemicals_found": [c.matched_db_name for c in harmful],
        "safety_score": score,
        "verdict": verdict,
    })

    return AnalyzeResponse(
        product_name=product_name,
        input_type="image",
        extracted_ingredients=ingredients,
        harmful_chemicals=harmful,
        safety_score=score,
        verdict=verdict,
    )
```

---

## Frontend Implementation

### types/api.ts

```typescript
export interface ChemicalResult {
  name: string;
  matched_db_name: string;
  danger_type: string[];
  description: string;
  severity: "High" | "Medium" | "Low";
  research_url: string | null;
}

export interface AnalyzeResponse {
  product_name: string | null;
  input_type: "text" | "image" | "both";
  extracted_ingredients: string[];
  harmful_chemicals: ChemicalResult[];
  safety_score: number;
  verdict: "SAFE" | "CAUTION" | "AVOID";
}
```

---

### app/page.tsx (structure)

```typescript
"use client";
import { useState } from "react";
import UploadForm from "@/components/UploadForm";
import ResultCard from "@/components/ResultCard";
import type { AnalyzeResponse } from "@/types/api";

type State = "idle" | "loading" | "cold_start" | "error" | "success";

export default function Home() {
  const [state, setState] = useState<State>("idle");
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string>("");

  const handleSubmit = async (formData: FormData | { ingredients: string }) => {
    setState("loading");
    const timer = setTimeout(() => setState("cold_start"), 5000);

    try {
      const API = process.env.NEXT_PUBLIC_API_URL;
      let res: Response;

      if (formData instanceof FormData) {
        res = await fetch(`${API}/analyze/image`, { method: "POST", body: formData });
      } else {
        res = await fetch(`${API}/analyze/text`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(formData),
        });
      }

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Analysis failed");
      }

      const data: AnalyzeResponse = await res.json();
      setResult(data);
      setState("success");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Something went wrong");
      setState("error");
    } finally {
      clearTimeout(timer);
    }
  };

  const reset = () => { setState("idle"); setResult(null); setError(""); };

  if (state === "success" && result) {
    return <ResultCard result={result} onReset={reset} />;
  }

  return (
    <main className="min-h-screen bg-gray-50 p-4">
      <h1 className="text-3xl font-bold text-center mb-8">ToxiScan</h1>
      {state === "loading" && <p>Analyzing...</p>}
      {state === "cold_start" && <p>Waking up server... (first request may take 30s)</p>}
      {state === "error" && <p className="text-red-500">{error}</p>}
      <UploadForm onSubmit={handleSubmit} loading={state === "loading" || state === "cold_start"} />
    </main>
  );
}
```

---

## MongoDB — Sample Seed Data

```javascript
// Run in MongoDB Atlas Shell or Compass
db.chemicals.insertMany([
  {
    name: "Formaldehyde",
    aliases: ["formalin", "methanal", "formic aldehyde", "methanol"],
    danger_type: ["Carcinogen", "Irritant"],
    severity: "High",
    description: "Known human carcinogen. Causes skin irritation, allergic reactions, and is linked to leukemia.",
    research_url: "https://www.iarc.who.int/",
    added_date: new Date(), last_updated: new Date()
  },
  {
    name: "Sodium Lauryl Sulfate",
    aliases: ["SLS", "sodium dodecyl sulfate", "sulfuric acid monododecyl ester"],
    danger_type: ["Irritant", "Sensitive Skin Issue"],
    severity: "Medium",
    description: "Strong surfactant that strips natural oils. Causes skin and eye irritation, especially with prolonged use.",
    research_url: null,
    added_date: new Date(), last_updated: new Date()
  },
  {
    name: "Methylparaben",
    aliases: ["methyl 4-hydroxybenzoate", "methyl paraben", "methylparaben"],
    danger_type: ["Carcinogen", "Sensitive Skin Issue"],
    severity: "High",
    description: "Preservative linked to hormone disruption. Found in breast tissue samples; possible endocrine disruptor.",
    research_url: "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC1280330/",
    added_date: new Date(), last_updated: new Date()
  },
  {
    name: "Fragrance",
    aliases: ["parfum", "aroma", "fragrance mix"],
    danger_type: ["Irritant", "Sensitive Skin Issue"],
    severity: "Medium",
    description: "Catch-all term hiding 100s of undisclosed chemicals. Common allergen and trigger for asthma.",
    research_url: null,
    added_date: new Date(), last_updated: new Date()
  },
  {
    name: "Phthalates",
    aliases: ["DBP", "DEHP", "dibutyl phthalate", "diethylhexyl phthalate"],
    danger_type: ["Carcinogen"],
    severity: "High",
    description: "Endocrine disruptors linked to reproductive harm and cancer. Often hidden under 'fragrance'.",
    research_url: "https://www.ewg.org/skindeep/",
    added_date: new Date(), last_updated: new Date()
  },
  {
    name: "Triclosan",
    aliases: ["5-chloro-2-(2,4-dichlorophenoxy)phenol", "irgasan"],
    danger_type: ["Carcinogen", "Irritant"],
    severity: "High",
    description: "Antibacterial agent linked to thyroid disruption and antibiotic resistance.",
    research_url: null,
    added_date: new Date(), last_updated: new Date()
  },
  {
    name: "Talc",
    aliases: ["talcum", "magnesium silicate", "talcum powder"],
    danger_type: ["Carcinogen"],
    severity: "Medium",
    description: "Linked to ovarian cancer risk in genital use. Talc mines often contaminated with asbestos.",
    research_url: null,
    added_date: new Date(), last_updated: new Date()
  },
  {
    name: "Benzophenone",
    aliases: ["oxybenzone", "BP-3", "benzophenone-3"],
    danger_type: ["Carcinogen", "Sensitive Skin Issue"],
    severity: "High",
    description: "UV filter that penetrates skin. Linked to hormone disruption and accumulates in the body.",
    research_url: "https://www.ewg.org/sunscreen/",
    added_date: new Date(), last_updated: new Date()
  },
  {
    name: "Coal Tar",
    aliases: ["coal tar dye", "p-phenylenediamine", "aminophenol"],
    danger_type: ["Carcinogen"],
    severity: "High",
    description: "Coal tar and its derivatives are known carcinogens. Common in hair dyes and anti-dandruff shampoos.",
    research_url: null,
    added_date: new Date(), last_updated: new Date()
  },
  {
    name: "Hydroquinone",
    aliases: ["1,4-dihydroxybenzene", "quinol", "benzene-1,4-diol"],
    danger_type: ["Carcinogen", "Irritant"],
    severity: "High",
    description: "Skin lightening agent. Linked to ochronosis (skin darkening) and classified as a possible carcinogen.",
    research_url: null,
    added_date: new Date(), last_updated: new Date()
  },
  {
    name: "Polyethylene Glycol",
    aliases: ["PEG", "propylene glycol", "polyethylene glycol"],
    danger_type: ["Sensitive Skin Issue"],
    severity: "Low",
    description: "Can be contaminated with carcinogenic byproducts (ethylene oxide, 1,4-dioxane) during manufacturing.",
    research_url: null,
    added_date: new Date(), last_updated: new Date()
  },
  {
    name: "Resorcinol",
    aliases: ["1,3-dihydroxybenzene", "m-dihydroxybenzene"],
    danger_type: ["Irritant", "Sensitive Skin Issue"],
    severity: "Medium",
    description: "Hair dye component and antiseptic. Can disrupt thyroid function with prolonged use.",
    research_url: null,
    added_date: new Date(), last_updated: new Date()
  },
]);
```

---

## Tests — test_scoring.py

```python
from services.scoring import calculate_score, get_verdict

def test_perfect_score():
    assert calculate_score([]) == 10.0

def test_single_high():
    assert calculate_score([{"severity": "High"}]) == 7.5

def test_single_medium():
    assert calculate_score([{"severity": "Medium"}]) == 8.5

def test_single_low():
    assert calculate_score([{"severity": "Low"}]) == 9.5

def test_five_high_capped_at_zero():
    chems = [{"severity": "High"}] * 5  # 10 - 12.5 = should be 0
    assert calculate_score(chems) == 0.0

def test_mix():
    chems = [{"severity": "High"}, {"severity": "Medium"}]
    assert calculate_score(chems) == 6.0

def test_verdict_safe():
    assert get_verdict(9.0) == "SAFE"
    assert get_verdict(8.0) == "SAFE"

def test_verdict_caution():
    assert get_verdict(7.9) == "CAUTION"
    assert get_verdict(5.0) == "CAUTION"

def test_verdict_avoid():
    assert get_verdict(4.9) == "AVOID"
    assert get_verdict(0.0) == "AVOID"
```