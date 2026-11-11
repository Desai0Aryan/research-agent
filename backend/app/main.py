import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import documents, evaluation, feedback, health, research, search
from .config import get_settings
from .db import init_db
from .middleware import AccessLogMiddleware, GuardMiddleware

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(title="Enterprise AI Research Agent", version="1.0.0", lifespan=lifespan)
_s = get_settings()
# Order matters: the last one added is outermost. CORS wraps everything so 401/429 responses still carry CORS headers.
app.add_middleware(GuardMiddleware, api_keys=_s.api_key_list, rate_limit=_s.rate_limit_per_min, heavy_limit=_s.rate_limit_heavy_per_min)
app.add_middleware(AccessLogMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _s.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID", "Server-Timing", "Retry-After"],
)
app.include_router(health.router)
app.include_router(documents.router)
app.include_router(search.router)
app.include_router(research.router)
app.include_router(evaluation.router)
app.include_router(feedback.router)
