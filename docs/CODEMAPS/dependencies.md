<!-- Generated: 2026-03-27 | Files: pyproject.toml, package.json, requirements_v4.md | Token estimate: ~700 -->

# External Dependencies & Services

**Last Updated**: 2026-03-27

---

## External APIs

### OpenAI API

**Service**: OpenAI Chat Completions
**Status**: Production (Phase 1)
**Endpoint**: `https://api.openai.com/v1/chat/completions`

**Configuration** (from `backend/core/config.py`):
```python
openai_api_key: str                    # Required env var
openai_model: str = "gpt-4o"           # Model selection
```

**Usage** (from `services/openai_client.py`):
```python
response = self._client.chat.completions.create(
    model=self._model,                 # gpt-4o
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ],
    temperature=0.2,                   # Low randomness
)
```

**Authentication**: API Key via environment variable
**Rate Limits**: Subject to OpenAI account tier
**Pricing**: Pay-per-token (gpt-4o pricing applies)
**Error Handling**:
- Invalid API key → 401
- Rate limit → 429 (retry with backoff, future)
- Invalid request → 400 (request validation)

**Future Enhancements**:
- [ ] Retry logic with exponential backoff
- [ ] Token counting (input/output usage tracking)
- [ ] Cost analysis (tokens × rate)
- [ ] Caching for identical prompts

---

## Backend Dependencies

### Core Framework

| Package | Version | Purpose |
|---------|---------|---------|
| FastAPI | >=0.115 | Web framework, routing, validation |
| Pydantic | >=2.0 | Request/response schema validation |
| Pydantic-Settings | >=2.0 | Environment variable management |
| Uvicorn | >=0.34 | ASGI server |

**Status**: Production-ready, actively maintained

---

### OpenAI Integration

| Package | Version | Purpose |
|---------|---------|---------|
| openai | >=1.60 | Official OpenAI Python client |

**Status**: Production-ready
**Key Class**: `OpenAI(api_key=...)` from `openai` package
**Features Used**:
- Chat completions (`client.chat.completions.create()`)
- Message roles (system, user, assistant)
- Temperature control

---

### Data Processing (Phase 2+)

| Package | Version | Purpose |
|---------|---------|---------|
| openpyxl | >=3.1 | Excel (.xlsx) parsing and writing |
| pandas | >=2.2 | Tabular data manipulation and analysis |
| python-multipart | >=0.0.18 | File upload handling (FormData) |

**Status**: Stubs only (not yet used in Phase 1)
**Integration**: File upload router + XLSX parser service

---

### Database (Phase 2+)

| Package | Version | Purpose |
|---------|---------|---------|
| SQLAlchemy | >=2.0 | ORM for History and Skills tables |
| aiosqlite | >=0.21 | Async SQLite driver (future async endpoints) |

**Status**: Stubs only
**Database**: SQLite by default (configurable)
**Schema**: History, Skills, FileUpload (future)

---

### Environment

| Package | Version | Purpose |
|---------|---------|---------|
| python-dotenv | >=1.0 | Load .env file for development |

**Status**: Used (recommended, not required in Docker)
**File**: `.env` in backend root

---

### Development Tools

| Package | Version | Purpose |
|---------|---------|---------|
| pytest | >=8.0 | Testing framework |
| pytest-asyncio | >=0.25 | Async test support |
| pytest-cov | >=6.0 | Coverage reporting (80%+ required) |
| httpx | >=0.28 | Async HTTP client for tests |
| black | >=24.0 | Code formatter (PEP 8) |
| ruff | >=0.9 | Fast linter (replaces flake8) |

**Usage**:
```bash
# Test
pytest --cov=backend --cov-report=term-missing

# Format
black backend/

# Lint
ruff check backend/
```

---

## Frontend Dependencies

### Core Framework

| Package | Version | Purpose |
|---------|---------|---------|
| React | ^19.2.4 | UI library |
| React-DOM | ^19.2.4 | DOM binding |

**Status**: Production-ready (React 19 with latest features)
**Features Used**:
- Functional components (hooks)
- useState (local UI state)
- Context consumption via custom hooks

---

### State Management

| Package | Version | Purpose |
|---------|---------|---------|
| Zustand | ^5.0.0 | Lightweight state library |

**Status**: Production-ready
**Usage**: `useGenerateStore` for app state (task, response, loading, error)
**Why**: Simpler than Redux, no boilerplate, great DevX

---

### HTTP Client

| Package | Version | Purpose |
|---------|---------|---------|
| axios | ^1.7.0 | Promise-based HTTP client |

**Status**: Production-ready
**Configuration**: baseURL set to `/api` (relative to nginx)
**Usage**: `client.post<T>(path, data)`

---

### Styling

| Package | Version | Purpose |
|---------|---------|---------|
| Tailwind CSS | ^4.1.0 | Utility-first CSS framework |
| @tailwindcss/vite | ^4.1.0 | Vite plugin for Tailwind |

**Status**: Production-ready
**Configuration**: `tailwind.config.ts`
**Theme**: Dark mode (gray-950 background)
**Colors**:
- Primary: blue-600, blue-700
- Accent: yellow-950 (tips), red-950 (error), green-300 (code)

---

### Build & Development

| Package | Version | Purpose |
|---------|---------|---------|
| Vite | ^8.0.1 | Next-gen build tool |
| TypeScript | ~5.9.3 | Static typing |
| @vitejs/plugin-react | ^6.0.1 | React plugin for Vite (JSX, HMR) |

**Status**: Production-ready
**Dev Server**: HMR enabled on 5173

---

### Code Quality

| Package | Version | Purpose |
|---------|---------|---------|
| ESLint | ^9.39.4 | Linter |
| eslint-plugin-react-hooks | ^7.0.1 | React hooks rules |
| eslint-plugin-react-refresh | ^0.5.2 | Fast refresh rules |
| @types/* | Latest | TypeScript definitions |

**Run**: `npm run lint`

---

### Testing

| Package | Version | Purpose |
|---------|---------|---------|
| Vitest | ^3.2.4 | Fast unit/component tests |
| @testing-library/react | ^16.3.0 | Component testing utilities |
| @testing-library/jest-dom | ^6.6.3 | Custom matchers |
| @testing-library/user-event | ^14.5.2 | User interaction simulation |
| happy-dom | ^18.0.1 | Lightweight DOM implementation |
| jsdom | ^26.1.0 | Full DOM emulation (alternative) |

**Status**: 30 tests passing
**Run**:
```bash
npm run test              # Single run
npm run test:watch       # Watch mode
npm run test:coverage    # Coverage (80%+ required)
```

---

## Development Environment

### Backend (.venv)

**Python**: 3.13
**Package Manager**: uv (modern, fast replacement for pip)

**Setup**:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# or
.\.venv\Scripts\activate   # Windows

uv pip install -e ".[dev]"
# or
pip install -e ".[dev]"
```

---

### Frontend (node_modules)

**Node**: 18+ (via Docker)
**Package Manager**: npm

**Setup**:
```bash
cd frontend
npm install
npm run dev              # Start Vite dev server
npm run test            # Run tests
npm run build           # Production build
```

---

## Docker Images

### Backend Container

**Base Image**: `python:3.13-slim`
**Entry**: `uvicorn main:app --host 0.0.0.0 --port 8000`

**Dockerfile** (typical):
```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install -e .[dev]
COPY . .
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

---

### Frontend Container

**Base Image**: `node:20-alpine`
**Entry**: `npm run dev` (development) or built output (production)

**Dockerfile** (typical):
```dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json .
RUN npm ci

FROM node:20-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
```

---

### Reverse Proxy

**Base Image**: `nginx:alpine`
**Port**: 80 (external)

**Config** (`nginx.conf`):
```nginx
server {
  listen 80;
  server_name _;

  location / {
    proxy_pass http://frontend:5173;
  }

  location /api/ {
    proxy_pass http://backend:8000/api/;
  }
}
```

---

## Version Constraints

### Minimum Supported Versions

| Component | Version | Reason |
|-----------|---------|--------|
| Python | 3.13 | Modern syntax (str \| None) |
| Node | 18+ | ES2020+ features |
| React | 19 | Latest hooks API |
| FastAPI | 0.115 | Recent features |
| Pydantic | 2.0 | v2 validation model |

---

## Security Considerations

### API Keys

- **OPENAI_API_KEY**: Never commit, always use .env in development, use secrets manager in production

### Dependencies Audit

```bash
# Backend
pip-audit                        # Check for known vulnerabilities

# Frontend
npm audit                        # Check npm packages
npm audit fix                    # Auto-fix (if safe)
```

---

## Update Strategy

### Backend

**Minor/Patch Updates**: Safe (compatible APIs)
```bash
cd backend
uv pip install --upgrade FastAPI Pydantic pytest
```

**Major Version Updates**: Test thoroughly (breaking changes possible)

---

### Frontend

**React 19 → Future**: Monitor React blog for release notes
**Zustand 5 → Future**: Check GitHub releases

```bash
cd frontend
npm update              # Update to latest compatible
npm outdated           # Check outdated packages
npm audit              # Security audit
```

---

## Performance Optimization

### OpenAI Calls

| Strategy | Status | Benefit |
|----------|--------|---------|
| Response caching | Future | Avoid duplicate prompts |
| Token counting | Future | Cost tracking, optimization |
| Streaming | Future | Real-time UI feedback |
| Batch processing | Future | Rate limit efficiency |

---

### Frontend Assets

| Optimization | Tool | Status |
|--------------|------|--------|
| Tree shaking | Vite | Enabled |
| Code splitting | Vite | Auto (routes, components) |
| Compression | nginx | Enabled |
| Caching | nginx | ETags, long-term (hashed files) |

---

## Related Areas

- [Backend Architecture](./backend.md) — Package integration, service usage
- [Frontend Architecture](./frontend.md) — React, Zustand, axios usage
- [System Architecture](./architecture.md) — Docker Compose, service dependencies
- [Data Models](./data.md) — Pydantic validation, database ORM
