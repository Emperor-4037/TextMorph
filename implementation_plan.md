# AI Writing Assistant — Unified LLM Refactor

Refactor the platform from 13 Docker containers (5 T5 NLP services + RAG pipeline + observability stack) into 5 lean containers with a single quantized LLM, reducing VRAM from ~8GB → ~2.5GB and RAM from ~13GB → ~1.3GB.

## User Review Required

> [!IMPORTANT]
> **API Response Shape Changes**: The current gateway returns task-specific response fields (`corrected_text`, `paraphrased_text`, `simplified_text`, `toned_text`, `summary`) plus a `corrections[]` list for grammar. The unified NLP service will generate raw text — it **cannot** produce the structured `corrections` array (original/replacement/start_index/end_index) that the grammar page renders. Two options:
> 1. **Drop corrections UI** — Grammar page shows only the corrected text (same as other tools). Simpler, no hack.
> 2. **Diff-based corrections** — Compute corrections client-side by diffing original vs corrected text. More complex, may produce noisy results.
>
> **Recommendation**: Option 1 (drop corrections detail, keep corrected_text only). The corrected text itself is the valuable output.

> [!WARNING]
> **SSE Streaming Decision**: The spec requests SSE streaming to the frontend. However, the current frontend (`axios.post → response.json()`) does NOT support streaming. Adding SSE would require significant changes to every tool page component. **Proposed approach**: The gateway will return **JSON responses** (matching the current API contract exactly) for the initial refactor. The NLP service will support streaming internally, but the gateway will buffer and return complete JSON. This keeps the frontend completely untouched. Streaming can be added as a follow-up.

> [!IMPORTANT]
> **Model Download**: The GGUF model (~1.9GB) must be downloaded before `docker compose up`. A PowerShell script (`scripts/download_model.ps1`) and a bash script (`scripts/download_model.sh`) will be provided. The user must have `huggingface-cli` installed or the script will use `curl`/`wget` fallback.

## Proposed Changes

### Phase 1: Cleanup — Remove Dead Services & Observability

Delete all deprecated code before writing anything new.

---

#### [DELETE] [services/](file:///d:/AI%20Writing%20Assistant/services/)
Delete the entire `services/` directory containing all 7 microservices:
- `grammar_service/`, `paraphrase_service/`, `simplify_service/`, `summarize_service/`, `tone_service/`, `rag_service/`, `rag_worker/` (or whatever the exact subdirectory names are)

#### [DELETE] [Dockerfile.ml-base](file:///d:/AI%20Writing%20Assistant/infra/docker/Dockerfile.ml-base)
No longer needed — the unified NLP service has its own Dockerfile.

#### [DELETE] [Dockerfile.service](file:///d:/AI%20Writing%20Assistant/infra/docker/Dockerfile.service)
Generic service Dockerfile is replaced by the new NLP-specific one.

#### [DELETE] Observability config files
- `infra/monitoring/` (Prometheus config)
- `infra/prometheus/` (if exists)
- `infra/grafana/` (if exists)  
- `infra/otel/` (OpenTelemetry collector config)

#### [DELETE] Shared ML files
- [adapter_loader.py](file:///d:/AI%20Writing%20Assistant/shared/adapter_loader.py) — LoRA loading no longer needed
- [model_utils.py](file:///d:/AI%20Writing%20Assistant/shared/model_utils.py) — Hardware detection moves to NLP service
- [model_config.py](file:///d:/AI%20Writing%20Assistant/shared/model_config.py) — Model configuration no longer needed
- [model_loader.py](file:///d:/AI%20Writing%20Assistant/shared/model_loader.py) — Model loading no longer needed
- [qdrant_client.py](file:///d:/AI%20Writing%20Assistant/shared/qdrant_client.py) — Qdrant removed
- [redis_client.py](file:///d:/AI%20Writing%20Assistant/shared/redis_client.py) — Will be inlined where needed
- [tracing.py](file:///d:/AI%20Writing%20Assistant/shared/tracing.py) — OpenTelemetry removed
- [metrics.py](file:///d:/AI%20Writing%20Assistant/shared/metrics.py) — Prometheus removed

#### [MODIFY] [config.py](file:///d:/AI%20Writing%20Assistant/shared/config.py)
Remove Qdrant settings. Add `NLP_SERVICE_URL` setting. Keep all auth, Redis, and Postgres settings.

#### [MODIFY] [schemas.py](file:///d:/AI%20Writing%20Assistant/shared/schemas.py)
- Remove `RAGQueryRequest`, `RAGQueryResponse`, `ChunkMetadata`
- Remove `Correction` model (grammar corrections array no longer possible with LLM)
- Simplify `GrammarResponse` to just have `corrected_text` without `corrections` list
- Keep all other request/response schemas exactly as-is

#### [MODIFY] [logging.py](file:///d:/AI%20Writing%20Assistant/shared/logging.py)
Replace with structlog-based JSON logging. Keep the same `setup_logging(service_name)` function signature for backward compatibility.

#### [DELETE] [docker-compose.override.yml](file:///d:/AI%20Writing%20Assistant/docker-compose.override.yml)
Will be replaced by resource constraints inline in the main compose file.

---

### Phase 2: Build — Unified NLP Service

Create `nlp-service/` from scratch using llama-cpp-python.

---

#### [NEW] [nlp-service/Dockerfile](file:///d:/AI%20Writing%20Assistant/nlp-service/Dockerfile)
- Base: `nvidia/cuda:12.1.0-runtime-ubuntu22.04`
- Install Python 3.11, llama-cpp-python with CUDA (`CMAKE_ARGS="-DGGML_CUDA=on"`)
- Install FastAPI, uvicorn, structlog, redis
- NO PyTorch, NO Transformers, NO PEFT, NO Accelerate
- Model mounted via volume at `/models/model.gguf`

#### [NEW] [nlp-service/app/main.py](file:///d:/AI%20Writing%20Assistant/nlp-service/app/main.py)
- FastAPI app with lifespan: load GGUF model on startup as singleton
- `Llama(model_path, n_gpu_layers=-1, n_ctx=4096, n_threads=4, verbose=False, use_mmap=True)`
- `POST /infer` — accepts `{ task, text, tone_target?, max_length? }`
- `GET /health` — returns `{ status, model_loaded }`

#### [NEW] [nlp-service/app/inference.py](file:///d:/AI%20Writing%20Assistant/nlp-service/app/inference.py)
- `build_messages(task, text, tone_target)` — builds chat messages array with system prompt
- `run_inference(model, task, text, tone_target, max_length)` → returns complete text
- Temperature: 0.3, top_p: 0.9, repeat_penalty: 1.1
- max_tokens: min(max_length or 1024, 1024)

#### [NEW] [nlp-service/app/prompts.py](file:///d:/AI%20Writing%20Assistant/nlp-service/app/prompts.py)
`TASK_PROMPTS` dict with system prompts for: grammar, paraphrase, simplify, summarize, tone.

#### [NEW] [nlp-service/app/cache.py](file:///d:/AI%20Writing%20Assistant/nlp-service/app/cache.py)
- Redis cache with SHA-256 key: `hash(task + ":" + text)`
- `get_cached(key)`, `set_cached(key, value, ttl=3600)`
- Fail-open on Redis errors

#### [NEW] [nlp-service/requirements.txt](file:///d:/AI%20Writing%20Assistant/nlp-service/requirements.txt)
```
fastapi
uvicorn[standard]
llama-cpp-python
redis
structlog
```

---

### Phase 3: Refactor — Gateway

Rewrite `gateway/app/main.py` to route all 5 writing tasks to the single NLP service.

---

#### [MODIFY] [main.py](file:///d:/AI%20Writing%20Assistant/gateway/app/main.py)
Major changes:
- **Remove** all imports of: `metrics`, `tracing`, Prometheus instrumentator, OpenTelemetry, RAG schemas
- **Remove** service URL variables for individual NLP services and RAG
- **Add** single `NLP_SERVICE_URL` env var
- **Replace** 5 individual NLP route handlers with unified logic:
  - Each endpoint calls `call_nlp_service(task, text, extra_fields)` 
  - Which POSTs to `NLP_SERVICE_URL/infer` with `{ task, text, tone_target?, max_length? }`
  - Returns the response mapped to the existing schema (e.g., `{ success: true, paraphrased_text: "..." }`)
- **Replace** RAG routes with HTTP 501 stub
- **Remove** `/readiness` check for deleted services (keep only gateway + nlp-service)
- **Replace** Prometheus counters/latency tracking with structlog request logging
- **Keep** CORS middleware, audit log middleware, JWT auth (`verify_token`) **completely unchanged**

**Critical API contract mapping** (gateway transforms NLP service response to match existing schema):

| Endpoint | NLP task | Request body fields | Response field name |
|---|---|---|---|
| `POST /api/grammar` | `grammar` | `{ text }` | `corrected_text` |
| `POST /api/paraphrase` | `paraphrase` | `{ text, tone }` | `paraphrased_text` |
| `POST /api/simplify` | `simplify` | `{ text, reading_level }` | `simplified_text` |
| `POST /api/summarize` | `summarize` | `{ text, max_length }` | `summary` |
| `POST /api/tone` | `tone` | `{ text, target_tone }` | `toned_text` |

#### [MODIFY] [requirements.txt](file:///d:/AI%20Writing%20Assistant/gateway/requirements.txt)
Remove:
- `prometheus-fastapi-instrumentator`
- `opentelemetry-api`
- `opentelemetry-sdk`
- `opentelemetry-exporter-otlp-proto-http`

Add:
- `structlog`

---

### Phase 4: Docker Compose

Complete rewrite.

---

#### [MODIFY] [docker-compose.yml](file:///d:/AI%20Writing%20Assistant/docker-compose.yml)
5 services only:
1. **frontend** — React + Nginx (port 3000:80)
2. **gateway** — FastAPI (port 8000:8000), env: DATABASE_URL, REDIS_URL, NLP_SERVICE_URL, SECRET_KEY
3. **nlp-service** — llama-cpp-python (internal port 8001), GPU reservation, model volume mount
4. **postgres** — PostgreSQL 15 Alpine (port 5433:5432)
5. **redis** — Redis 7 Alpine (port 6379), `--maxmemory 256mb --maxmemory-policy allkeys-lru`

Removed: ml-base, grammar-service, paraphrase-service, simplify-service, tone-service, summarize-service, rag-service, rag-worker, qdrant, prometheus, grafana.

Volumes: `pg_data` only (removed `qdrant_data`, `grafana_data`).

---

### Phase 5: Frontend — Minimal RAG Cleanup

---

#### [MODIFY] [api.js](file:///d:/AI%20Writing%20Assistant/frontend/src/api.js)
- Remove `ragQuery`, `ragIngest`, `ingestStatus` exports
- Keep all 5 NLP API functions exactly as-is

#### [MODIFY] [RagPage.jsx](file:///d:/AI%20Writing%20Assistant/frontend/src/pages/RagPage.jsx)
Replace entire component with a "Coming Soon" placeholder page. Keep the same export/import structure so navigation doesn't break.

#### [MODIFY] [HealthDashboard.jsx](file:///d:/AI%20Writing%20Assistant/frontend/src/components/HealthDashboard.jsx)
- Remove `rag` from the `SERVICES` array
- Update `/readiness` parsing to match the refactored gateway (only `nlp-service` downstream)

#### [MODIFY] [Sidebar.jsx](file:///d:/AI%20Writing%20Assistant/frontend/src/components/Sidebar.jsx)
- Change the RAG nav item label to "Doc Assistant (Coming Soon)"
- Or: Keep it but visually dim it / add a "soon" badge

---

### Phase 6: Model Download Script

---

#### [NEW] [scripts/download_model.ps1](file:///d:/AI%20Writing%20Assistant/scripts/download_model.ps1)
PowerShell script (Windows-first since target OS is Windows 11):
- Downloads `Qwen/Qwen2.5-3B-Instruct-GGUF` Q4_K_M variant
- Saves to `./models/model.gguf`
- Fallback to curl if `huggingface-cli` not available

#### [NEW] [scripts/download_model.sh](file:///d:/AI%20Writing%20Assistant/scripts/download_model.sh)
Bash equivalent for Linux.

---

### Phase 7: Environment & Config Updates

---

#### [MODIFY] [.env](file:///d:/AI%20Writing%20Assistant/shared/../.env)
- Remove individual service URLs (`GRAMMAR_SERVICE_URL`, etc.)
- Remove `RAG_SERVICE_URL`, `OTEL_EXPORTER_OTLP_ENDPOINT`
- Add `NLP_SERVICE_URL=http://nlp-service:8001`

---

## Verification Plan

### Automated Tests
```bash
# 1. Validate Docker Compose syntax
docker compose config --quiet

# 2. Verify no banned imports in codebase
grep -r "opentelemetry\|prometheus_client\|celery\|qdrant\|sentence_transformers\|peft\|accelerate" --include="*.py" .

# 3. Build all images
docker compose build

# 4. Start and check resource usage
docker compose up -d
docker stats --no-stream
nvidia-smi
```

### Manual Verification
1. Send `POST /api/summarize` with 500-word text → verify response in <5s
2. Send same request again → verify cache hit (<100ms, `cached: true`)
3. Send `GET /api/rag/query` → verify HTTP 501
4. Test all 5 endpoints: grammar, paraphrase, simplify, summarize, tone
5. Verify total RAM < 6GB via `docker stats`
6. Verify VRAM < 3GB via `nvidia-smi`

## Open Questions

> [!IMPORTANT]
> **Grammar corrections UI**: Should we drop the detailed corrections list (option 1) or implement client-side diffing (option 2)? See "User Review Required" above.

> [!NOTE]
> **Existing models directory**: The current `models/` directory contains `flan-t5-base-finetuned/` and 5 LoRA adapters. These will be left in place (not deleted) but won't be used. The new `model.gguf` file will be added alongside them. If you want disk space reclaimed, we can delete the old model files in a separate step.
