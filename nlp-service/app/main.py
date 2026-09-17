import os
import time
import logging
from contextlib import asynccontextmanager
from typing import Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

logger = logging.getLogger("nlp-service")
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')

_model = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _model
    model_path = os.environ.get("MODEL_PATH", "/models/model.gguf")
    logger.info(f"Loading model from {model_path}...")
    start = time.time()
    try:
        from llama_cpp import Llama
        _model = Llama(
            model_path=model_path,
            n_gpu_layers=-1,
            n_ctx=4096,
            n_threads=4,
            verbose=False,
            use_mmap=True,
        )
        elapsed = time.time() - start
        logger.info(f"Model loaded in {elapsed:.1f}s")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        _model = None
    yield
    _model = None

app = FastAPI(title="NLP Service", version="2.0.0", lifespan=lifespan)

class InferRequest(BaseModel):
    task: str
    text: str
    tone_target: Optional[str] = None
    max_length: Optional[int] = None

class InferResponse(BaseModel):
    result: str
    cached: bool = False
    latency_ms: int = 0

@app.post("/infer", response_model=InferResponse)
async def infer(request: InferRequest):
    if _model is None:
        raise HTTPException(status_code=503, detail="Model not loaded")

    from .cache import get_cache_key, get_cached, set_cached
    from .inference import run_inference

    cache_key = get_cache_key(request.task, request.text, request.tone_target, request.max_length)
    cached_result = get_cached(cache_key)
    if cached_result is not None:
        return InferResponse(result=cached_result, cached=True, latency_ms=0)

    start = time.time()
    try:
        max_tokens = request.max_length or 1024
        result = run_inference(
            _model,
            task=request.task,
            text=request.text,
            tone_target=request.tone_target,
            max_tokens=max_tokens,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Inference error: {e}")
        raise HTTPException(status_code=500, detail="Inference failed")

    latency_ms = int((time.time() - start) * 1000)
    set_cached(cache_key, result)
    return InferResponse(result=result, cached=False, latency_ms=latency_ms)

@app.get("/health")
async def health():
    return {"status": "ok", "model_loaded": _model is not None}
