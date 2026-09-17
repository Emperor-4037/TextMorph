# TextMorph — System Architecture

This document details the microservices architecture, data flow, inference pipeline, caching strategy, and infrastructure of the **TextMorph** platform.

---

## 1. Architectural Overview

TextMorph is built on a **lean, 5-container architecture** designed for production reliability, fast iteration, and high-efficiency local LLM inference.

Previously, the platform relied on 13 separate microservices (5 individual T5 model services, a Celery-based RAG worker, Qdrant vector database, Prometheus, Grafana, and OpenTelemetry). That topology required >12GB VRAM and >13GB RAM. 

TextMorph consolidates text-processing tasks into a **single unified NLP inference service** powered by `llama-cpp-python` and 4-bit quantized GGUF models (e.g. Qwen2.5-7B/3B), reducing hardware demands to **~2.5GB VRAM and ~1.3GB RAM** while boosting generation quality.

---

## 2. Container Topology

```
                              ┌─────────────────────────────┐
                              │       Client Browser        │
                              └──────────────┬──────────────┘
                                             │ HTTP :3000
                                             ▼
                              ┌─────────────────────────────┐
                              │   frontend (React + Nginx)  │
                              └──────────────┬──────────────┘
                                             │ HTTP :8000
                                             ▼
                              ┌─────────────────────────────┐
                              │    gateway (FastAPI)        │
                              │  - JWT Auth & Route Mapping │
                              │  - Audit Logging (asyncpg)  │
                              │  - Request Trace ID & Latency│
                              └──────┬───────────────┬──────┘
                                     │               │
                    Internal :8001   ▼               ▼
             ┌─────────────────────────────┐   ┌───────────────────────────┐
             │    nlp-service (FastAPI)    │   │      postgres:15          │
             │  - llama-cpp-python (CUDA)  │   │  - User Auth / Profiles   │
             │  - Qwen2.5 GGUF (4-bit)     │   │  - Request Audit Logs     │
             │  - Task Prompts Engine      │   └───────────────────────────┘
             └──────────────┬──────────────┘
                            │
                            ▼
             ┌─────────────────────────────┐
             │        redis:7-alpine       │
             │  - SHA-256 Hashed LRU Cache │
             │  - Sub-100ms Repeated Query │
             └─────────────────────────────┘
```

---

## 3. Core Components

### A. Frontend (`frontend`)
- **Technology**: React 18, Vite, Tailwind CSS, Lucide React icons.
- **Role**: Clean Single Page Application (SPA) offering dedicated interfaces for:
  - **Grammar & Spell Check**
  - **Paraphrasing** (with style/tone selection)
  - **Text Simplification** (reading level adjustment)
  - **Summarization** (length sliders & point extraction)
  - **Tone Shifter** (persuasive, formal, casual, empathetic, assertive)
  - **System Health Monitor** (live latency & downstream connectivity)
- **Deployment**: Multi-stage Docker build; compiled static files are served via Nginx on port 3000.

### B. API Gateway (`gateway`)
- **Technology**: FastAPI, Uvicorn, httpx, structlog, SQLAlchemy, asyncpg, PyJWT.
- **Role**:
  - Validates JWT tokens on protected routes.
  - Normalizes external API payloads to downstream NLP inference requests.
  - Injects `X-Trace-Id` headers and logs response durations (`X-Duration-Ms`).
  - Asynchronously writes request audit trails into PostgreSQL.
  - Aggregates readiness checks (`/readiness`) across downstream dependencies.

### C. Unified NLP Service (`nlp-service`)
- **Technology**: FastAPI, `llama-cpp-python` (with CUDA acceleration via GGML), Redis.
- **Model Engine**:
  - Loads a quantized 4-bit GGUF model (`Qwen2.5-7B-Instruct-Q4_K_M.gguf` or `Qwen2.5-3B`) on container startup.
  - Offloads model layers to native NVIDIA GPU (`n_gpu_layers=-1`), utilizing memory mapping (`use_mmap=True`) and 4096-token context window (`n_ctx=4096`).
- **Prompt Engineering**:
  - Applies task-specific system instructions (`TASK_PROMPTS` for grammar, paraphrase, simplify, summarize, tone) directly to the unified model.
  - Enforces deterministic, consistent outputs with low temperature (`0.3`), top-p (`0.9`), and repetition penalty (`1.1`).

### D. Redis Cache (`redis`)
- **Technology**: Redis 7 Alpine with LRU eviction (`--maxmemory 256mb --maxmemory-policy allkeys-lru`).
- **Role**:
  - Keys are generated via SHA-256 hashing over `task:text:tone_target:max_length`.
  - Duplicate user queries are resolved in `<100ms` without triggering GPU inference.

### E. Relational Database (`postgres`)
- **Technology**: PostgreSQL 15 Alpine.
- **Role**:
  - Persists user accounts, hashed credentials, and metadata.
  - Stores audit logs for security, analytics, and operational monitoring.

---

## 4. End-to-End Request Flow (e.g. Paraphrase)

1. **Client** submits text and desired style to `POST http://localhost:8000/api/paraphrase`.
2. **Gateway**:
   - Verifies JWT bearer token.
   - Generates/extracts `X-Trace-Id`.
   - Packages parameters into `{ task: "paraphrase", text: "...", tone_target: "formal" }`.
   - Dispatches internal HTTP POST to `http://nlp-service:8001/infer`.
3. **NLP Service**:
   - Computes SHA-256 hash `sha256(task + ":" + text + ":" + tone + ":" + max_length)`.
   - Checks Redis: if cached, immediately returns `{ result: "...", cached: true, latency_ms: 0 }`.
   - On cache miss, formats chat prompt with the paraphrasing system directive and user prompt.
   - Executes inference through `llama-cpp-python` offloaded to GPU.
   - Saves generated text to Redis with TTL.
   - Returns `{ result: "...", cached: false, latency_ms: 320 }`.
4. **Gateway**:
   - Wraps result in `ParaphraseResponse(success=True, paraphrased_text=...)`.
   - Asynchronously records audit entry in PostgreSQL.
   - Returns response to Frontend with tracing headers.
5. **Frontend** renders paraphrased text side-by-side with copy action.

---

## 5. Hardware Specifications & Footprint

| Component | Legacy Microservices (DocuMesh) | TextMorph Unified Architecture |
|---|---|---|
| Containers | 13 | **5** |
| GPU VRAM Usage | ~8 – 12 GB | **~2.5 – 4.5 GB** |
| System RAM Usage | ~13 GB+ | **~1.3 – 2.0 GB** |
| Storage Footprint | >50 GB (PyTorch base images) | **<10 GB total** |
| Repeated Query Latency | Model rerun (~1–3s) | **Sub-100ms (Redis Cache)** |
