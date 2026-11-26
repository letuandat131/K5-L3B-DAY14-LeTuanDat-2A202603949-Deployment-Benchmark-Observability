"""
Production AI Agent — Part 6 Final Project (bản khung)

Hoàn thành các TODO để đạt đủ 12 tiêu chí trong README.md, rồi kiểm tra:
    python check_production_ready.py

Bản khung này chạy được (uvicorn app.main:app) nhưng chưa đạt tiêu chí nào.
"""
"""
Production AI Agent — Part 6 Final Project
"""
import json
import logging
import signal
import sys
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Request
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import redis_healthy
from utils.mock_llm import ask as llm_ask


class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "ts": self.formatTime(record, self.datefmt),
            "lvl": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if hasattr(record, "props") and isinstance(record.props, dict):
            log_obj.update(record.props)
        return json.dumps(log_obj)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
logger = logging.getLogger("app")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Graceful shutdown handler for SIGTERM
    logger.info("Application starting up", extra={"props": {"event": "startup"}})
    yield
    logger.info("Application shutting down", extra={"props": {"event": "shutdown"}})


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = None


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.environment}


@app.get("/ready")
def ready():
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis connection failed")
    return {"ready": True, "environment": settings.environment}


@app.post("/ask")
def ask(
    request: Request,
    body: AskRequest | None = None,
    question: str | None = None,
    api_key: str = Depends(verify_api_key),
):
    q = None
    if body and body.question:
        q = body.question
    elif question:
        q = question
    else:
        # Check query param directly
        q = request.query_params.get("question")

    if not q:
        raise HTTPException(status_code=400, detail="Missing question")

    check_rate_limit(api_key)
    check_budget()

    start = time.time()
    answer = llm_ask(q)
    duration_ms = (time.time() - start) * 1000

    in_tokens = max(1, len(q.split()) * 2)
    out_tokens = max(1, len(answer.split()) * 2)
    cost = record_cost(in_tokens, out_tokens)

    logger.info(
        "Processed ask request",
        extra={
            "props": {
                "event": "ask",
                "status": 200,
                "ms": round(duration_ms, 2),
                "cost_usd": cost,
            }
        },
    )
    return {"question": q, "answer": answer}
