# TextMorph — Intelligent AI Writing Assistant

[![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://reactjs.org/)
[![Vite](https://img.shields.io/badge/Vite-B73BFE?style=for-the-badge&logo=vite&logoColor=FFD62E)](https://vitejs.dev/)
[![Docker](https://img.shields.io/badge/Docker-2CA5E0?style=for-the-badge&logo=docker&logoColor=white)](https://www.docker.com/)
[![llama.cpp](https://img.shields.io/badge/llama.cpp-CUDA%20Accelerated-orange?style=for-the-badge)](https://github.com/ggerganov/llama.cpp)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![Redis](https://img.shields.io/badge/Redis-DC382D?style=for-the-badge&logo=redis&logoColor=white)](https://redis.io/)

**TextMorph** is a high-performance, containerized AI writing platform engineered for low latency, privacy, and minimal resource footprint.

Powered by a unified quantized Large Language Model (Qwen2.5 GGUF via `llama-cpp-python` with CUDA acceleration), an asynchronous FastAPI Gateway, Redis caching, and a modern React + Vite frontend, TextMorph replaces bloated legacy microservice stacks with a lean 5-container architecture.

---

## 🚀 Key Capabilities

TextMorph delivers five core NLP transformations powered by specialized system prompts on a single unified LLM:

| Capability | Description | Input / Options |
|---|---|---|
| **✍️ Grammar Correction** | Detects and fixes grammatical errors, spelling typos, punctuation, and syntax mistakes while preserving original meaning, tone, and formatting. | Raw text |
| **🔄 Contextual Paraphrase** | Intelligently rephrases sentences and paragraphs, varying vocabulary and syntactic structure while retaining core semantics. | Raw text, Style/Tone target |
| **📉 Text Simplification** | Converts dense, technical, or academic prose into clear, accessible plain English (Grade 6–8 reading level) using active voice and shorter sentences. | Raw text, Reading level |
| **📝 Executive Summarization** | Distills lengthy texts into concise, punchy summaries capturing key findings, arguments, and conclusions (~20–30% original length). | Raw text, Max token length |
| **🎭 Tone Shifter** | Restyles content into specific target voices: *Professional/Formal*, *Casual*, *Persuasive*, *Empathetic*, or *Assertive*. | Raw text, Target tone |
| **⚡ High-Speed Caching** | SHA-256 hashed Redis cache layer returning sub-100ms responses on repeated prompts and duplicate queries. | Automatic |
| **📊 Real-Time Health & Diagnostics** | Live dashboard monitoring Gateway status, downstream model readiness, response latencies, and service availability. | UI Dashboard |

---

## 🏗 System Architecture

TextMorph is designed as a **lean 5-container topology**, refactored from an older 13-container microservice system to slash VRAM and system memory usage while dramatically improving maintainability.

```
                  ┌──────────────────────────────┐
                  │       Client Browser         │
                  └──────────────┬───────────────┘
                                 │ HTTP :3000
                                 ▼
                  ┌──────────────────────────────┐
                  │   Frontend (React + Nginx)   │
                  └──────────────┬───────────────┘
                                 │ HTTP :8000
                                 ▼
                  ┌──────────────────────────────┐
                  │      API Gateway (FastAPI)   │
                  │  - Auth / JWT Validation     │
                  │  - Request Tracing & Audit   │
                  │  - Endpoint Normalization    │
                  └──────┬───────────────┬───────┘
                         │               │
        Internal :8001   ▼               ▼
 ┌─────────────────────────────┐   ┌───────────────────────────┐
 │   Unified NLP Service       │   │      PostgreSQL 15        │
 │  - llama-cpp-python (CUDA)  │   │  - User Auth & Sessions   │
 │  - Qwen2.5 GGUF (4-bit)     │   │  - Audit Logging History  │
 │  - Specialized Prompt Engine│   └───────────────────────────┘
 └──────────────┬──────────────┘
                │
                ▼
 ┌─────────────────────────────┐
 │       Redis 7 (LRU)         │
 │  - Prompt & Result Cache    │
 │  - Sub-100ms Cache Hits     │
 └─────────────────────────────┘
```

### Architecture Evolution (DocuMesh → TextMorph)

| Dimension | Legacy Architecture (DocuMesh) | Modern Architecture (TextMorph) |
|---|---|---|
| **Active Containers** | 13 containers | **5 containers** |
| **NLP Engine** | 5 separate T5/Flan-T5 microservices + LoRA | **1 Unified Service (llama-cpp-python + GGUF)** |
| **VRAM Footprint** | ~8 GB – 12 GB | **~2.5 GB – 4.5 GB** (Fully offloaded to GPU) |
| **System RAM** | ~13 GB+ | **~1.3 GB – 2.0 GB** |
| **Quantization** | FP16 / FP32 full weights | **4-bit Quantization (Q4_K_M)** |
| **Inference Framework** | PyTorch + HuggingFace Transformers + Accelerate | **llama.cpp (C++ / CUDA native backend)** |
| **Caching** | Basic Redis cache | **SHA-256 Hashed Prompt/Result Redis LRU Cache** |
| **Observability** | Prometheus, Grafana, OpenTelemetry | **Lightweight JSON Structlog + Live Health API** |

---

## 📦 Services Breakdown

1. **`frontend` (Port 3000)**
   - Built with React 18, Vite, Lucide Icons, and Tailwind CSS.
   - Multi-stage Docker build served via lightweight Nginx.
   - Responsive UI with sidebar navigation, side-by-side text diffing, copy-to-clipboard, and live system monitoring.

2. **`gateway` (Port 8000)**
   - Central FastAPI router managing CORS, JWT token verification, and request lifecycle.
   - Structured JSON logging (`structlog`), automated `X-Trace-Id` propagation, and latency tracking (`X-Duration-Ms`).
   - Async SQLAlchemy (`asyncpg`) for audit logging into PostgreSQL.

3. **`nlp-service` (Internal Port 8001)**
   - Containerized CUDA-accelerated `llama-cpp-python` runtime.
   - Loads GGUF quantized models (defaults to `Qwen2.5-7B-Instruct-Q4_K_M` or `Qwen2.5-3B`).
   - Dynamically injects specialized system prompts per task with temperature (0.3), top_p (0.9), and repetition penalty (1.1).
   - Direct Redis caching integration for zero-latency duplicate inference.

4. **`postgres` (Port 5433 host / 5432 container)**
   - PostgreSQL 15 Alpine storing relational records, user credentials, and request audit trails.

5. **`redis` (Port 6379)**
   - Redis 7 Alpine configured with an LRU eviction policy (`--maxmemory 256mb --maxmemory-policy allkeys-lru`).

---

## 🛠 Prerequisites

- **Docker Desktop** (with Docker Compose v2+)
- **NVIDIA GPU** (recommended with 4GB+ VRAM for CUDA acceleration) + [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
  *(CPU execution is supported if no GPU is present)*
- **Git**

---

## ⚡ Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/Emperor-4037/TextMorph.git
cd TextMorph
```

### 2. Download the Model Weights
Before launching the containers, download the quantized GGUF model into `./models/model.gguf`:

- **On Windows (PowerShell):**
  ```powershell
  .\scripts\download_model.ps1
  ```

- **On Linux / macOS (Bash):**
  ```bash
  chmod +x ./scripts/download_model.sh
  ./scripts/download_model.sh
  ```

*The script fetches `Qwen2.5-7B-Instruct-Q4_K_M.gguf` (~4.7 GB) from Hugging Face and saves it to `./models/model.gguf`. `huggingface-cli`, `curl`, and `wget` are supported.*

### 3. Configure Environment Variables
Copy or adjust `.env.local` or create `.env`:
```bash
# Database
POSTGRES_PASSWORD=postgres

# Security
SECRET_KEY=super-secret-key-change-in-production

# Internal Service URLs
NLP_SERVICE_URL=http://nlp-service:8001
VITE_API_BASE=http://localhost:8000
```

### 4. Build and Run with Docker Compose
```bash
docker compose up -d --build
```

### 5. Access the Platform
- **Web Application**: [http://localhost:3000](http://localhost:3000)
- **API Gateway & Swagger Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **Gateway Health Check**: [http://localhost:8000/health](http://localhost:8000/health)
- **System Readiness Endpoint**: [http://localhost:8000/readiness](http://localhost:8000/readiness)

---

## 📡 API Reference

All requests accept JSON payloads and can optionally include an `Authorization: Bearer <token>` header and an `X-Trace-Id` header.

| Method | Endpoint | Request Body | Response Field |
|---|---|---|---|
| `POST` | `/api/grammar` | `{"text": "string"}` | `{"success": true, "corrected_text": "..."}` |
| `POST` | `/api/paraphrase` | `{"text": "string", "tone": "formal"}` | `{"success": true, "paraphrased_text": "..."}` |
| `POST` | `/api/simplify` | `{"text": "string", "reading_level": "Grade 6-8"}` | `{"success": true, "simplified_text": "..."}` |
| `POST` | `/api/summarize` | `{"text": "string", "max_length": 256}` | `{"success": true, "summary": "..."}` |
| `POST` | `/api/tone` | `{"text": "string", "target_tone": "persuasive"}` | `{"success": true, "toned_text": "..."}` |
| `GET` | `/health` | — | `{"status": "ok", "service": "gateway"}` |
| `GET` | `/readiness` | — | `{"ready": true, "services": {"nlp": {"status": "ok"}}}` |

---

## 💻 Tech Stack

- **Frontend**: React 18, Vite, Tailwind CSS, Lucide Icons, Nginx
- **Backend Gateway**: FastAPI, Uvicorn, httpx, structlog, SQLAlchemy, asyncpg, PyJWT
- **Inference Engine**: `llama-cpp-python` (C++ GGML/GGUF engine with CUDA backend)
- **LLM**: Qwen 2.5 Instruct (GGUF Quantized, 4-bit / Q4_K_M)
- **Data Stores**: PostgreSQL 15, Redis 7 (LRU caching)
- **Infrastructure**: Docker, Docker Compose, Multi-stage Dockerfiles

---

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

Distributed under the MIT License.
