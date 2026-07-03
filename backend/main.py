"""
ToxiScan — FastAPI Backend
Phase 2: App skeleton with MongoDB connection + health check
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from services.config import settings
from services.db import connect_db, close_db
from routers import health, scan

# ─── Logging ──────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s — %(message)s",
)
logger = logging.getLogger(__name__)


# ─── Lifespan (startup + shutdown) ────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_db()
    logger.info("🚀 ToxiScan API started.")
    yield
    # Shutdown
    await close_db()
    logger.info("ToxiScan API shut down.")


# ─── App ──────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="ToxiScan API",
    description="Scan cosmetic/beauty product ingredients for harmful chemicals.",
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)


# ─── CORS ─────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Routers ──────────────────────────────────────────────────────────────────

app.include_router(health.router)
app.include_router(scan.router)


# ─── Root ─────────────────────────────────────────────────────────────────────

@app.get("/", tags=["Root"])
async def root():
    return {"message": "ToxiScan API is running 🧪", "docs": "/docs"}
