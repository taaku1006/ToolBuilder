<!-- Generated: 2026-03-27 | Codebase scanned: 25+ files | Token estimate: ~850 -->

# ToolBilder Architecture - Codemaps Index

**Project**: Excel × 自然言語 ツールビルダー
**Status**: Phase 1 MVP Complete (Backend: 25 tests, Frontend: 30 tests)
**Last Updated**: 2026-03-27

---

## Overview

ToolBilder is a monorepo web application that generates Python code for Excel processing from natural language tasks. Users describe what they want to do with an Excel file, and the AI agent generates production-ready Python code with built-in error handling.

### Key Features (Phase 1)
- Natural language task input
- OpenAI-powered code generation (gpt-4o)
- JSON response with summary, steps, tips, and executable Python code
- React UI with task input and code result display
- Error handling and response validation

### Architecture Pattern
- **Frontend**: React 19 + TypeScript + Zustand + Vite
- **Backend**: FastAPI + Python 3.13 + OpenAI API
- **Deployment**: Docker Compose with nginx reverse proxy
- **Testing**: Pytest (backend 25 tests) + Vitest (frontend 30 tests)

---

## Codemaps

### 1. [architecture.md](./architecture.md) — System Overview
High-level service boundaries, deployment topology, request flow, and component interactions.
- Service boundaries and dependencies
- Deployment with Docker Compose and nginx
- Request/response flow for the POST /api/generate endpoint

### 2. [backend.md](./backend.md) — API & Services
Backend module structure, routes, schemas, services, and middleware.
- POST /api/generate endpoint (implemented)
- OpenAI client integration
- Prompt building (Japanese system/user prompts)
- Placeholder routers: upload, execute, history, skills
- Exception handling and CORS configuration

### 3. [frontend.md](./frontend.md) — UI & Components
React component hierarchy, Zustand store, API client, and TypeScript types.
- TaskInput: textarea with Cmd+Enter shortcut
- CodeResult: syntax-highlighted code display with copy button
- useGenerateStore: state management for task, response, loading, error
- API client using axios

### 4. [data.md](./data.md) — Data Models
Request/response schemas, database structure (planned).
- GenerateRequest: task, file_id, max_steps, skill_id
- GenerateResponse: id, summary, python_code, steps, tips
- Placeholder tables: history, skills (SQLAlchemy ORM planned)

### 5. [dependencies.md](./dependencies.md) — External Services & Packages
Third-party APIs, packages, and configuration.
- OpenAI API (gpt-4o, temperature=0.2)
- Backend: FastAPI, Pydantic, SQLAlchemy, openpyxl, pandas
- Frontend: React, Zustand, axios, Tailwind CSS
- Dev: pytest, vitest, coverage tools

---

## Implementation Status

### Phase 1: Complete ✅
- [x] Backend FastAPI app (main.py, CORS middleware, exception handlers)
- [x] POST /api/generate route with OpenAI integration
- [x] Prompt builder with Japanese system/user prompts
- [x] Frontend React app with TaskInput and CodeResult
- [x] Zustand state management
- [x] Docker Compose setup (backend, frontend, nginx)
- [x] 55 tests passing (25 backend + 30 frontend)

### Phase 2+: Placeholders (Stub files with comments)
- [ ] File upload: routers/upload.py, schemas/upload.py
- [ ] Code execution: routers/execute.py, schemas/execute.py
- [ ] History tracking: routers/history.py, schemas/history.py
- [ ] Skills management: routers/skills.py, schemas/skills.py
- [ ] Agent orchestration: services/agent_orchestrator.py
- [ ] Reflection engine: services/reflection_engine.py
- [ ] Debug loop: services/debug_loop.py
- [ ] Skills engine: services/skills_engine.py
- [ ] Sandbox execution: services/sandbox.py
- [ ] XLSX parsing: services/xlsx_parser.py
- [ ] Database models: db/models.py, db/engine.py

---

## Key Files

### Backend (Python 3.13, FastAPI)
```
backend/
├── main.py                          # Entry point, CORS, exception handlers
├── routers/
│   └── generate.py                  # POST /api/generate endpoint (40 lines, implemented)
├── services/
│   ├── openai_client.py             # OpenAI API wrapper (21 lines)
│   └── prompt_builder.py            # Prompt templates (35 lines)
├── schemas/
│   ├── generate.py                  # Pydantic models for request/response
│   └── [upload, execute, history, skills].py (placeholders)
├── core/
│   ├── config.py                    # Settings (environment variables)
│   ├── deps.py                      # Dependency injection
│   └── exceptions.py                # AppError handler
└── db/
    ├── models.py                    # SQLAlchemy ORM (stub)
    └── engine.py                    # Database connection (stub)
```

### Frontend (React 19, TypeScript, Vite)
```
frontend/src/
├── App.tsx                          # Root component with Header, TaskInput, CodeResult
├── components/
│   ├── TaskInput.tsx                # Textarea with Cmd+Enter and button
│   ├── CodeResult.tsx               # Results display with copy button
│   └── layout/
│       └── Header.tsx               # App header
├── api/
│   ├── client.ts                    # Axios instance (baseURL: /api)
│   └── generate.ts                  # postGenerate(task) function
├── stores/
│   └── useGenerateStore.ts          # Zustand: task, response, loading, error
├── types/
│   └── index.ts                     # GenerateRequest, GenerateResponse
└── test-setup.ts                    # Vitest configuration
```

---

## Environment Variables

### Backend (.env)
```
OPENAI_API_KEY=sk-...                # Required: OpenAI API key
OPENAI_MODEL=gpt-4o                  # Default model (optional)
CORS_ORIGINS=http://localhost:5173   # Frontend URL (optional)
DATABASE_URL=sqlite:///./db/history.db
UPLOAD_DIR=./uploads
OUTPUT_DIR=./outputs
```

### Frontend
No .env needed (uses relative /api baseURL)

---

## Quick Links

- **Requirements**: `/docs/requirements_v4.md`
- **Docker**: `docker-compose.yml` (backend:8000, frontend:5173, nginx:80)
- **Tests**: `pytest --cov` (backend), `npm run test:coverage` (frontend)
- **Development**: Use Docker; all development happens inside containers

---

## See Also

- [LIVE-SWE-AGENT Paper](../2511.13646v3.pdf) — Reference for multi-phase architecture design
