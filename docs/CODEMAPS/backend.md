<!-- Generated: 2026-03-27 | Files scanned: main.py, routers/*.py, services/*.py, core/*.py | Token estimate: ~900 -->

# Backend Architecture

**Framework**: FastAPI + Python 3.13
**Entry Point**: `backend/main.py`
**Port**: 8000
**Last Updated**: 2026-03-27

---

## Module Overview

```
backend/
├── main.py                          # FastAPI app, CORS, routers (38 lines)
├── routers/
│   ├── generate.py                  # POST /api/generate (56 lines) ✅ IMPLEMENTED
│   ├── upload.py                    # File upload (stub)
│   ├── execute.py                   # Code execution (stub)
│   ├── history.py                   # History tracking (stub)
│   └── skills.py                    # Skills management (stub)
├── services/
│   ├── openai_client.py             # OpenAI API wrapper (21 lines) ✅
│   ├── prompt_builder.py            # Prompt templates (35 lines) ✅
│   ├── agent_orchestrator.py        # Agent coordination (stub)
│   ├── reflection_engine.py         # Self-reflection logic (stub)
│   ├── debug_loop.py                # Auto-debug with retry (stub)
│   ├── skills_engine.py             # Skills matching/loading (stub)
│   ├── sandbox.py                   # Isolated code execution (stub)
│   └── xlsx_parser.py               # Excel structure analysis (stub)
├── schemas/
│   ├── generate.py                  # GenerateRequest, GenerateResponse ✅
│   ├── upload.py                    # Upload schemas (stub)
│   ├── execute.py                   # Execute schemas (stub)
│   ├── history.py                   # History schemas (stub)
│   └── skills.py                    # Skills schemas (stub)
├── core/
│   ├── config.py                    # Settings from env (31 lines) ✅
│   ├── deps.py                      # Dependency injection (stub)
│   └── exceptions.py                # AppError handler (17 lines) ✅
├── db/
│   ├── models.py                    # SQLAlchemy ORM models (stub)
│   └── engine.py                    # Database connection (stub)
├── tests/
│   ├── conftest.py                  # pytest fixtures (stub)
│   └── test_generate.py             # Generate endpoint tests (25 tests)
├── pyproject.toml                   # Dependencies & test config
└── Dockerfile                       # Python 3.13 container
```

---

## Implemented Routes

### POST /api/generate

**Location**: `backend/routers/generate.py:18-56`

**Request**:
```python
# schemas/generate.py
class GenerateRequest(BaseModel):
    task: str                         # Natural language instruction (required)
    file_id: str | None = None        # Uploaded file reference (future)
    max_steps: int = 3                # Max reflection steps (future)
    skill_id: str | None = None       # Skill to apply (future)
```

**Response**:
```python
class GenerateResponse(BaseModel):
    id: str                           # UUID for this generation
    summary: str                      # One-liner summary (Japanese)
    python_code: str                  # Complete Python script
    steps: list[str]                  # Ordered execution steps
    tips: str                         # Runtime notes (Japanese)
```

**Endpoint Implementation**:
```python
@router.post("/generate", response_model=GenerateResponse)
def generate(
    request: GenerateRequest,
    settings: Settings = Depends(get_settings),
) -> GenerateResponse:
    # 1. Build user prompt with task
    user_prompt = build_user_prompt(
        task=request.task,
        file_context=None,
    )

    # 2. Create OpenAI client with settings
    client = OpenAIClient(settings)

    # 3. Get raw response from GPT-4o
    raw_response = client.generate_code(
        system_prompt=SYSTEM_PROMPT,
        user_prompt=user_prompt,
    )

    # 4. Parse JSON response
    try:
        parsed = json.loads(raw_response)
    except (json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=500,
            detail=f"OpenAI returned invalid JSON: {exc}",
        ) from exc

    # 5. Construct and return response
    try:
        return GenerateResponse(
            id=str(uuid.uuid4()),
            summary=parsed["summary"],
            python_code=parsed["python_code"],
            steps=parsed["steps"],
            tips=parsed["tips"],
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=500,
            detail=f"OpenAI response missing required field: {exc}",
        ) from exc
```

**Error Handling**:
- Invalid JSON: 500, "OpenAI returned invalid JSON: ..."
- Missing fields: 500, "OpenAI response missing required field: ..."
- Validation error: 422 (Pydantic)

---

## Services

### OpenAI Client

**Location**: `backend/services/openai_client.py` (21 lines)

```python
class OpenAIClient:
    def __init__(self, settings: Settings) -> None:
        self._client = OpenAI(api_key=settings.openai_api_key)
        self._model = settings.openai_model

    def generate_code(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model,                    # gpt-4o (configurable)
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,                      # Low randomness for code
        )
        return response.choices[0].message.content or ""
```

**Dependencies**: `openai>=1.60` from pyproject.toml

---

### Prompt Builder

**Location**: `backend/services/prompt_builder.py` (35 lines)

**System Prompt** (Japanese):
```
あなたは Excel ファイルを処理する Python コード生成の専門家です。
ユーザーのタスク指示に基づき、openpyxl または pandas を使った Python スクリプトを生成してください。

ルール:
- 入力ファイルのパスは環境変数 INPUT_FILE から取得すること
- 出力ファイルは環境変数 OUTPUT_DIR のディレクトリに保存すること
- 処理の進捗を print() で標準出力に出すこと
- エラーハンドリングを含めること
- コメントは日本語で記述すること
- import os で INPUT_FILE と OUTPUT_DIR を取得するコードを冒頭に含めること

以下の JSON 形式のみで返答してください:
{
  "summary": "...",
  "python_code": "...",
  "steps": [...],
  "tips": "..."
}
```

**User Prompt Builder**:
```python
def build_user_prompt(
    task: str,
    file_context: str | None = None,
) -> str:
    parts: list[str] = []

    if file_context:
        parts.append(f"【対象ファイルの構造】\n{file_context}\n")

    parts.append(f"【タスク】\n{task}")

    return "\n".join(parts)
```

**Current Implementation**: `file_context=None` (future enhancement: XLSX parser analysis)

---

## Middleware & Exception Handling

### CORS Configuration

**Location**: `backend/main.py:21-27`

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,    # From CORS_ORIGINS env
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Default**: `http://localhost:5173` (configurable via env)

---

### Exception Handler

**Location**: `backend/core/exceptions.py` (17 lines)

```python
class AppError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)

async def app_error_handler(_request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )
```

**Registration** (`main.py:32`):
```python
app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
```

---

## Configuration

**Location**: `backend/core/config.py` (31 lines)

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # OpenAI
    openai_api_key: str                           # Required
    openai_model: str = "gpt-4o"

    # Database (future)
    database_url: str = "sqlite+aiosqlite:///./db/history.db"
    upload_dir: str = "./uploads"
    output_dir: str = "./outputs"
    max_upload_mb: int = 50
    exec_timeout: int = 30
    cors_origins: str = "http://localhost:5173"

    # Reflection (future)
    reflection_enabled: bool = True
    reflection_max_steps: int = 3

    # Debug loop (future)
    debug_loop_enabled: bool = True
    debug_retry_limit: int = 3

    # Skills (future)
    skills_enabled: bool = True
    skills_dir: str = "./skills"
    skills_similarity_threshold: float = 0.4

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]
```

---

## Stub Routers (Phase 2+)

### upload.py
```python
# File upload endpoint (phase 2)
```

### execute.py
```python
# Code execution endpoint (phase 3)
```

### history.py
```python
# Generation history tracking (phase 2)
```

### skills.py
```python
# Skills management: list, search, apply (phase 3+)
```

---

## Stub Services (Phase 2+)

| Service | Purpose | Status |
|---------|---------|--------|
| agent_orchestrator.py | Multi-phase agent coordination | Stub |
| reflection_engine.py | Self-reflection & improvement | Stub |
| debug_loop.py | Error detection & auto-fix | Stub |
| skills_engine.py | Skill matching & loading | Stub |
| sandbox.py | Isolated code execution | Stub |
| xlsx_parser.py | Excel structure analysis | Stub |

---

## Dependency Injection

**Location**: `backend/core/deps.py` (stub)

**Pattern** (as used in endpoint):
```python
def generate(
    request: GenerateRequest,
    settings: Settings = Depends(get_settings),  # Injected dependency
) -> GenerateResponse:
    ...
```

**Future Extensions**:
- Database session injection
- Authenticated user context
- Rate limiter

---

## Testing

**Location**: `backend/tests/` (25 tests)

**Test Files**:
- `test_generate.py` — POST /api/generate endpoint tests
- `conftest.py` — pytest fixtures and mocks

**Run Tests**:
```bash
pytest --cov=backend --cov-report=term-missing
```

**Coverage**: 80%+ required

---

## Database Models (Stub)

**Location**: `backend/db/models.py`

**Planned Tables** (from requirements_v4.md):
- History: generation_id, task, response, created_at
- Skills: skill_id, code, context, similarity_score

**Status**: Placeholder; to be implemented with SQLAlchemy ORM

---

## Dependencies

From `pyproject.toml`:
```
fastapi>=0.115          # Web framework
uvicorn[standard]>=0.34 # ASGI server
pydantic>=2.0           # Request validation
pydantic-settings>=2.0  # Environment config
openai>=1.60            # OpenAI API client
openpyxl>=3.1           # Excel parsing (future)
pandas>=2.2             # Data manipulation (future)
python-multipart        # File upload (future)
sqlalchemy>=2.0         # ORM (future)
aiosqlite>=0.21         # Async SQLite (future)
python-dotenv>=1.0      # .env loading

[dev]
pytest>=8.0
pytest-asyncio>=0.25
pytest-cov>=6.0
httpx>=0.28
black>=24.0
ruff>=0.9
```

---

## Related Areas

- [System Architecture](./architecture.md) — Request flow, service boundaries
- [Frontend Components](./frontend.md) — API client calling /api/generate
- [Data Models](./data.md) — Pydantic schemas and database structure
- [External Dependencies](./dependencies.md) — Versions and configuration
