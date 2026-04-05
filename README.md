# ToolBuilder

AI-powered code generation for Excel/CSV processing. Describe what you want in natural language, and ToolBuilder generates, executes, and self-repairs Python code automatically.

## Overview

Upload an Excel/CSV file, describe the task, and ToolBuilder handles the rest: file analysis, code generation, sandboxed execution, automatic debugging, and cross-session learning.

### Key Features

- **Natural language to code**: Describe tasks in any language, get working Python
- **Adaptive Pipeline v2**: 4-stage architecture (Understand → Generate → Verify-Fix → Learn)
- **Self-healing loop**: Automatic error detection, recovery analysis, and code repair
- **Cross-session memory**: Learns from past successes/failures (patterns, gotchas, insights)
- **Multi-LLM support**: OpenAI, Anthropic, Google Gemini, Ollama (local), Claude SDK (subscription)
- **Eval harness**: A/B test different models and configurations

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI, Python 3.13+, SQLAlchemy (async), SQLite |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4, Zustand |
| LLM | LiteLLM (OpenAI/Anthropic/Gemini/Ollama) + Claude Agent SDK |
| Infra | Docker Compose, nginx, Langfuse (optional) |

## Quick Start

### Prerequisites

- Docker & Docker Compose
- At least one of: OpenAI API key, Anthropic API key, Ollama, or Claude Code OAuth token

### Setup

```bash
# 1. Create .env
cp backend/.env.example backend/.env
# Edit backend/.env — set at least one LLM provider:
#   OPENAI_API_KEY=sk-...              (OpenAI)
#   ANTHROPIC_API_KEY=sk-ant-api...    (Anthropic API)
#   GEMINI_API_KEY=...                 (Google Gemini)
#   CLAUDE_CODE_OAUTH_TOKEN=sk-ant-oat01-...  (Claude subscription)
#   LLM_MODEL=ollama/gemma4:e4b       (Ollama — no key needed)

# 2. Start
docker compose up --build

# 3. Access
# http://localhost        (nginx)
# http://localhost:5173   (frontend)
# http://localhost:8000   (backend API)
```

### Local Development

```bash
# Backend
cd backend
uv sync
uv run uvicorn main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

## Environment Variables

Set in `backend/.env` (see `backend/.env.example`).

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENAI_API_KEY` | One of these | OpenAI API key |
| `ANTHROPIC_API_KEY` | | Anthropic API key |
| `GEMINI_API_KEY` | | Google Gemini API key |
| `CLAUDE_CODE_OAUTH_TOKEN` | | Claude subscription OAuth token |
| `LLM_MODEL` | No | Default model (e.g., `gpt-4o`, `ollama/gemma4:e4b`) |
| `LLM_BASE_URL` | No | Custom LLM endpoint |
| `DATABASE_URL` | No | DB connection string |
| `EXEC_TIMEOUT` | No | Code execution timeout in seconds (default: 30) |
| `LANGFUSE_ENABLED` | No | Enable Langfuse tracing |

## Architecture

### Adaptive Pipeline v2

```
Upload → UNDERSTAND (Python analysis + LLM strategy)
              ↓
         GENERATE (complexity-adaptive code generation)
              ↓
    ┌── VERIFY-FIX LOOP ──┐
    │  Verifier → RecoveryManager → Fixer  │
    │  (replan on stuck)                    │
    └──────────────────────┘
              ↓
         LEARN (patterns / gotchas / insights → memory)
```

- **UNDERSTAND**: LLM-free file analysis + LLM strategy planning
- **GENERATE**: SIMPLE (1 call) / STANDARD (+ memory) / COMPLEX (step-by-step)
- **VERIFY-FIX**: Unified loop replacing Phase D/F/G. Judge/Fixer separation, stuck detection, replan
- **LEARN**: Cross-session memory (patterns.json, gotchas.json, insights.json)

### Multi-LLM Provider Routing

```
Model string → client_factory.py → appropriate backend

"gpt-4o"                    → LiteLLM (OpenAI)
"anthropic/claude-sonnet-4-6" → LiteLLM (Anthropic API)
"ollama/gemma4:e4b"         → LiteLLM (Ollama local)
"claude-sdk/claude-sonnet-4-6" → Claude Agent SDK (subscription)
```

### Project Structure

```
ToolBuilder/
├── backend/
│   ├── core/              # Settings, deps, exceptions
│   ├── db/                # SQLAlchemy models & engine
│   ├── routers/           # API endpoints (generate, upload, eval, models)
│   ├── pipeline/
│   │   ├── v2/            # Adaptive Pipeline v2
│   │   │   ├── orchestrator.py    # Main 4-stage orchestrator
│   │   │   ├── stages/            # understand, generate, verify_fix, recovery, learn
│   │   │   ├── models.py          # Data models (PipelineState, Strategy, etc.)
│   │   │   └── config.py          # STAGE_CONFIGS, V2Settings
│   │   └── magentic_one/          # MagenticOne alternative
│   ├── infra/
│   │   ├── llm_client.py          # LiteLLM backend
│   │   ├── claude_sdk_client.py   # Claude Agent SDK backend
│   │   ├── client_factory.py      # Provider routing
│   │   └── sandbox.py             # Code execution sandbox
│   ├── memory/            # Cross-session learning (JSON-based)
│   ├── eval/              # Eval harness (architectures, runner, results)
│   ├── prompts/           # LLM prompt templates
│   └── tests/             # pytest test suite
├── frontend/
│   └── src/
│       ├── components/    # UI (dashboard style)
│       ├── api/           # API client
│       ├── stores/        # Zustand stores
│       └── hooks/         # Custom hooks
├── docker-compose.yml
└── nginx.conf
```

## API Endpoints

### File Operations

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/upload` | Upload & parse file |
| GET | `/api/download/{path}` | Download generated file |

### Code Generation & Execution

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/generate` | Generate code (SSE / JSON) |
| POST | `/api/execute` | Execute code in sandbox |
| GET | `/api/models` | List available LLM models |

### History & Skills

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/history` | Execution history |
| GET/POST/DELETE | `/api/skills` | Skills CRUD |
| POST | `/api/skills/{id}/run` | Run a skill |

### Eval

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/eval/architectures` | List architectures |
| POST | `/api/eval/run` | Start eval run |
| GET | `/api/eval/run/{id}` | Run status & results |

## Testing

```bash
# Backend (in Docker)
docker compose exec backend uv run pytest tests/

# Frontend
cd frontend
npm test
```

## License

Private
