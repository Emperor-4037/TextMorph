import os
import uuid
import time
import httpx
import structlog
from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from shared.config import settings
from shared.auth import verify_token
from shared.db import AsyncSessionLocal
from shared.models import AuditLog
from shared.schemas import (
    ParaphraseRequest, ParaphraseResponse,
    GrammarRequest, GrammarResponse,
    SimplifyRequest, SimplifyResponse,
    ToneRequest, ToneResponse,
    SummarizeRequest, SummarizeResponse,
)

# ── Config ────────────────────────────────────────────────────────────────────
_NLP_SERVICE_URL = os.environ.get("NLP_SERVICE_URL", "http://nlp-service:8001")

logger = structlog.get_logger("gateway")
http_client: httpx.AsyncClient = None  # initialized in lifespan


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    http_client = httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=10.0))
    # Create DB tables on startup (idempotent)
    try:
        from shared.db import engine, Base
        from shared.models import AuditLog  # noqa: F401 — ensure model is registered
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("database_tables_ready")
    except Exception as exc:
        logger.warning("db_init_skipped", error=str(exc))
    yield
    await http_client.aclose()


app = FastAPI(title="AI Platform Gateway", version="2.0.0", lifespan=lifespan)

# Allow the frontend container (and local dev) to call the gateway
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Middleware: trace ID + audit log ──────────────────────────────────────────
@app.middleware("http")
async def trace_and_audit(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-Id", str(uuid.uuid4()))
    request.state.trace_id = trace_id
    start = time.monotonic()

    response = await call_next(request)
    duration_ms = int((time.monotonic() - start) * 1000)
    response.headers["X-Trace-Id"] = trace_id
    response.headers["X-Duration-Ms"] = str(duration_ms)

    # Structured request log
    logger.info(
        "request_completed",
        trace_id=trace_id,
        method=request.method,
        path=str(request.url.path),
        status_code=response.status_code,
        latency_ms=duration_ms,
    )

    # Fire-and-forget audit log (skip health / metrics endpoints)
    if not request.url.path.startswith(("/health", "/readiness")):
        try:
            async with AsyncSessionLocal() as session:
                user_id = getattr(request.state, "user_id", None)
                log = AuditLog(
                    trace_id=trace_id,
                    user_id=user_id,
                    method=request.method,
                    path=str(request.url.path),
                    status_code=response.status_code,
                    duration_ms=duration_ms,
                )
                session.add(log)
                await session.commit()
        except Exception as exc:
            logger.warning("audit_log_failed", error=str(exc))

    return response


# ── Helpers ────────────────────────────────────────────────────────────────────
async def call_nlp_service(task: str, text: str, trace_id: str,
                           tone_target: str = None, max_length: int = None) -> dict:
    """Forward an NLP request to the unified nlp-service."""
    payload = {"task": task, "text": text}
    if tone_target:
        payload["tone_target"] = tone_target
    if max_length:
        payload["max_length"] = max_length

    headers = {"X-Trace-Id": trace_id, "Content-Type": "application/json"}
    try:
        resp = await http_client.post(
            f"{_NLP_SERVICE_URL}/infer", json=payload, headers=headers
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as e:
        logger.error("nlp_service_error", trace_id=trace_id, status=e.response.status_code)
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f"NLP service error: {e.response.text}"
        )
    except httpx.RequestError as e:
        logger.error("nlp_service_unreachable", trace_id=trace_id, error=str(e))
        raise HTTPException(status_code=503, detail="NLP service unavailable")


# ── Health & Readiness ────────────────────────────────────────────────────────
@app.get("/health")
async def health_check():
    return {"status": "ok", "service": "gateway"}


@app.get("/readiness")
async def readiness_check():
    """Check if the NLP service is reachable."""
    services = {"nlp": f"{_NLP_SERVICE_URL}/health"}
    results = {}
    all_ok = True
    for name, url in services.items():
        try:
            resp = await http_client.get(url, timeout=5.0)
            results[name] = {"status": "ok", "code": resp.status_code}
        except Exception as e:
            results[name] = {"status": "error", "error": str(e)}
            all_ok = False

    from fastapi.responses import JSONResponse
    return JSONResponse(
        content={"ready": all_ok, "services": results},
        status_code=200 if all_ok else 503,
    )


# ── NLP Routes ────────────────────────────────────────────────────────────────
@app.post("/api/grammar", response_model=GrammarResponse)
async def grammar(request: GrammarRequest, req: Request, user_id: str = Depends(verify_token)):
    req.state.user_id = user_id
    data = await call_nlp_service("grammar", request.text, req.state.trace_id)
    return GrammarResponse(success=True, corrected_text=data["result"])


@app.post("/api/paraphrase", response_model=ParaphraseResponse)
async def paraphrase(request: ParaphraseRequest, req: Request, user_id: str = Depends(verify_token)):
    req.state.user_id = user_id
    data = await call_nlp_service(
        "paraphrase", request.text, req.state.trace_id,
        tone_target=request.tone,
    )
    return ParaphraseResponse(success=True, paraphrased_text=data["result"])


@app.post("/api/simplify", response_model=SimplifyResponse)
async def simplify(request: SimplifyRequest, req: Request, user_id: str = Depends(verify_token)):
    req.state.user_id = user_id
    data = await call_nlp_service(
        "simplify", request.text, req.state.trace_id,
        tone_target=request.reading_level,
    )
    return SimplifyResponse(success=True, simplified_text=data["result"])


@app.post("/api/summarize", response_model=SummarizeResponse)
async def summarize(request: SummarizeRequest, req: Request, user_id: str = Depends(verify_token)):
    req.state.user_id = user_id
    data = await call_nlp_service(
        "summarize", request.text, req.state.trace_id,
        max_length=request.max_length,
    )
    return SummarizeResponse(success=True, summary=data["result"])


@app.post("/api/tone", response_model=ToneResponse)
async def tone(request: ToneRequest, req: Request, user_id: str = Depends(verify_token)):
    req.state.user_id = user_id
    data = await call_nlp_service(
        "tone", request.text, req.state.trace_id,
        tone_target=request.target_tone,
    )
    return ToneResponse(success=True, toned_text=data["result"])


# ── RAG Stub Routes (HTTP 501) ────────────────────────────────────────────────
@app.post("/api/rag/query")
async def rag_query_stub(req: Request, user_id: str = Depends(verify_token)):
    raise HTTPException(status_code=501, detail="RAG pipeline not available in this build")


@app.post("/api/rag/ingest")
async def rag_ingest_stub(req: Request, user_id: str = Depends(verify_token)):
    raise HTTPException(status_code=501, detail="RAG pipeline not available in this build")


@app.get("/api/rag/ingest/status/{task_id}")
async def rag_status_stub(task_id: str, req: Request, user_id: str = Depends(verify_token)):
    raise HTTPException(status_code=501, detail="RAG pipeline not available in this build")
