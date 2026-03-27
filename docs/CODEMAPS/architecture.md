<!-- Generated: 2026-03-27 | Files: main.py, docker-compose.yml | Token estimate: ~750 -->

# ToolBilder System Architecture

**Entry Points**: `backend/main.py`, `frontend/src/App.tsx`
**Deployment**: Docker Compose (3 services)
**Last Updated**: 2026-03-27

---

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Browser                              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  React App (frontend:5173)                               │   │
│  │  ├─ TaskInput: textarea input + button                   │   │
│  │  ├─ CodeResult: syntax-highlighted code display          │   │
│  │  ├─ useGenerateStore: state management (Zustand)         │   │
│  │  └─ axios client (baseURL: /api)                         │   │
│  └──────────────────────────────────────────────────────────┘   │
└──────────────────────┬──────────────────────────────────────────┘
                       │ HTTP requests (via nginx)
┌──────────────────────▼──────────────────────────────────────────┐
│              nginx reverse proxy (port 80)                       │
│  ├─ /      → frontend:5173 (React SPA)                          │
│  └─ /api   → backend:8000 (FastAPI)                             │
└──────────────────────┬──────────────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        │                             │
        ▼                             ▼
┌──────────────────────┐    ┌──────────────────────┐
│   backend:8000       │    │   frontend:5173      │
│  FastAPI + Python    │    │   React dev server   │
│                      │    │   (with HMR)         │
│ POST /api/generate   │    │                      │
│  ├─ Validate input   │    │                      │
│  ├─ Call OpenAI API  │    │                      │
│  ├─ Parse response   │    │                      │
│  └─ Return JSON      │    │                      │
└──────────────────────┘    └──────────────────────┘
        │
        ▼
┌──────────────────────┐
│   OpenAI API         │
│   model: gpt-4o      │
│   temperature: 0.2   │
└──────────────────────┘
```

---

## Service Boundaries

### 1. **Frontend (React 19 + TypeScript + Vite)**
- **Port**: 5173 (dev), built into nginx
- **State**: Zustand store (useGenerateStore)
- **API Client**: axios instance at `/api`
- **Components**: TaskInput, CodeResult, Header, layout
- **Testing**: Vitest (30 tests)

**Key Files**:
- `frontend/src/App.tsx` — Root component
- `frontend/src/stores/useGenerateStore.ts` — State management
- `frontend/src/components/TaskInput.tsx` — Input UI
- `frontend/src/components/CodeResult.tsx` — Output UI

---

### 2. **Backend (FastAPI + Python 3.13)**
- **Port**: 8000
- **Framework**: FastAPI with Pydantic
- **Middleware**: CORS (configured from env)
- **Exception Handler**: Custom AppError → JSONResponse
- **Testing**: pytest with coverage (25 tests)

**Key Files**:
- `backend/main.py` — FastAPI app, middleware, routers
- `backend/routers/generate.py` — POST /api/generate endpoint
- `backend/core/config.py` — Settings (env variables)
- `backend/core/exceptions.py` — Error handling

---

### 3. **Reverse Proxy (nginx:alpine)**
- **Port**: 80 (external)
- **Routing**:
  - `/` → frontend:5173
  - `/api` → backend:8000
- **Config**: `nginx.conf` (relative URL rewriting)

---

## Request/Response Flow

### POST /api/generate

```
User Input (TaskInput component)
  ├─ task: string (natural language instruction)
  └─ send via axios: POST /api/generate { task }
       │
       ▼
    nginx reverse proxy
       │ (route to backend:8000)
       ▼
    FastAPI endpoint: routers/generate.py
       ├─ Parse GenerateRequest (task, file_id?, max_steps?, skill_id?)
       ├─ Build user prompt: build_user_prompt(task, file_context=None)
       ├─ Call OpenAI: OpenAIClient.generate_code(system_prompt, user_prompt)
       │   └─ system: Japanese instructions for Excel code generation
       │   └─ user: task description
       ├─ Parse JSON response: summary, python_code, steps, tips
       └─ Return GenerateResponse (id, summary, python_code, steps, tips)
            │
            ▼
       axios client in frontend
            │
            ▼
       Zustand store: setResponse(response)
            │
            ▼
       CodeResult component renders
            ├─ Summary (one-liner)
            ├─ Steps (ordered list)
            ├─ Python code (syntax-highlighted)
            ├─ Tips (yellow box)
            └─ Copy button (copies python_code to clipboard)
```

---

## Middleware Chain

```
Request → CORS middleware → Router matching → Endpoint handler
                                              ↓
                                      OpenAI API call
                                      JSON parsing
                                      Response validation
                                      ↓
         Exception handler ← Exception (if any)
         (AppError → JSONResponse)
                                      ↓
                            Response (GenerateResponse)
                                      ↓
                            Client (axios receives JSON)
```

---

## Docker Compose Setup

| Service | Image/Build | Port | Environment | Dependencies |
|---------|------------|------|-------------|---|
| backend | ./backend Dockerfile | 8000 | `.env` | — |
| frontend | ./frontend Dockerfile | 5173 | — | backend |
| nginx | nginx:alpine | 80 | nginx.conf | backend, frontend |

**Volume Mounts**:
- backend: `./backend:/app` (for development hot reload)
- frontend: `./frontend:/app` + `/app/node_modules` (for dev server + isolation)

**Build Process**:
```bash
docker-compose up --build
# Starts: backend (port 8000), frontend (port 5173), nginx (port 80)
```

---

## Data Flow

### API Request (Frontend → Backend)
```json
POST /api/generate
{
  "task": "売上データを月別に集計してグラフを作成する"
}
```

### API Response (Backend → Frontend)
```json
200 OK
{
  "id": "uuid-string",
  "summary": "月別売上の集計とグラフ化スクリプト",
  "python_code": "import openpyxl\nimport pandas as pd\n...",
  "steps": [
    "CSVファイルをpandasで読込",
    "月別に集計",
    "グラフを作成"
  ],
  "tips": "INPUT_FILE環境変数にCSVファイルのパスを設定してください"
}
```

---

## Error Handling

### Backend Exception Flow
1. **Validation Error**: Pydantic raises ValidationError → FastAPI converts to 422
2. **OpenAI API Error**: Custom handling in `routers/generate.py`
   - JSONDecodeError → HTTPException (500, "invalid JSON")
   - Missing fields → HTTPException (500, "missing required field")
3. **AppError**: Custom exception → `app_error_handler` → JSONResponse

### Frontend Error Display
```typescript
// In useGenerateStore.generate()
try {
  const response = await postGenerate(task)
  set({ response, loading: false })
} catch {
  set({
    loading: false,
    error: 'コード生成に失敗しました。もう一度お試しください。',
  })
}

// In App.tsx
{error && (
  <div className="bg-red-950 ...">
    {error}
  </div>
)}
```

---

## Configuration

### Backend Settings (core/config.py)
```python
openai_api_key: str                     # Required
openai_model: str = "gpt-4o"            # Default
cors_origins: str = "http://localhost:5173"
database_url: str = "sqlite+aiosqlite:///./db/history.db"
upload_dir: str = "./uploads"
output_dir: str = "./outputs"
max_upload_mb: int = 50
exec_timeout: int = 30
```

### OpenAI Integration
- **Model**: gpt-4o (configurable)
- **Temperature**: 0.2 (low randomness for code generation)
- **System Prompt**: Japanese instructions for Excel code with openpyxl/pandas
- **Response Format**: JSON-only (specified in prompt)

---

## Related Areas

- [Backend API & Services](./backend.md) — Detailed endpoint, router, service structure
- [Frontend Components & State](./frontend.md) — Component hierarchy, hooks, store patterns
- [Data Models & Schemas](./data.md) — Request/response schemas, database models (planned)
- [External Dependencies](./dependencies.md) — Packages, versions, API configurations
