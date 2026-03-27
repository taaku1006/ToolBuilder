# ToolBilder Architecture Codemaps

**Generated**: 2026-03-27
**Status**: Phase 1 MVP Complete
**Documentation Type**: Architecture and implementation reference

---

## What is this?

This directory contains token-lean architecture documentation (codemaps) that serve as the single source of truth for understanding the ToolBilder codebase. Each document is focused, current, and directly derived from the actual code.

---

## Quick Start

1. **New to the project?** Start with [`INDEX.md`](./INDEX.md)
2. **Understanding the system?** Read [`architecture.md`](./architecture.md)
3. **Building the backend?** Reference [`backend.md`](./backend.md)
4. **Working on the UI?** Check [`frontend.md`](./frontend.md)
5. **Designing data?** See [`data.md`](./data.md)
6. **Managing dependencies?** Review [`dependencies.md`](./dependencies.md)

---

## Document Overview

### INDEX.md
**Entry point.** Overview of all codemaps, Phase 1 status, key files, and setup instructions.

### architecture.md
**System design.** Service boundaries, Docker topology, request/response flow, error handling.
- **For**: Understanding how the system works end-to-end
- **Includes**: ASCII diagrams, deployment setup, middleware chain

### backend.md
**API & services.** Module structure, POST /api/generate endpoint, OpenAI integration, configuration.
- **For**: Backend development, API integration
- **Includes**: Endpoint specification, error codes, stub services

### frontend.md
**React components.** Component hierarchy, Zustand store, API client, build configuration.
- **For**: Frontend development, UI/UX work
- **Includes**: Component code samples, state management, styling patterns

### data.md
**Data models.** Request/response schemas, database structure (planned), validation rules.
- **For**: Data design, schema planning, database implementation
- **Includes**: Type definitions, data flow diagrams, planned tables

### dependencies.md
**External packages.** OpenAI API, npm packages, Python packages, development tools.
- **For**: Dependency management, version updates, security audits
- **Includes**: Package list with versions, upgrade strategy, security notes

---

## Key Facts at a Glance

| Aspect | Details |
|--------|---------|
| **Project** | Excel × 自然言語 ツールビルダー |
| **Status** | Phase 1 MVP complete; 55 tests passing |
| **Backend** | FastAPI + Python 3.13 |
| **Frontend** | React 19 + TypeScript + Zustand |
| **API** | POST /api/generate (OpenAI gpt-4o) |
| **Deployment** | Docker Compose (backend, frontend, nginx) |
| **Implemented** | Code generation endpoint + UI |
| **Planned** | File upload, execution, history, skills |

---

## Document Statistics

| Document | Lines | Size | Focus |
|----------|-------|------|-------|
| INDEX.md | 166 | 6.3K | Entry point |
| architecture.md | 261 | 9.5K | System design |
| backend.md | 411 | 12K | API & services |
| frontend.md | 502 | 14K | React components |
| data.md | 462 | 12K | Data models |
| dependencies.md | 441 | 9.8K | Packages & APIs |
| **Total** | **2,243** | **~63K** | **Complete codebase documentation** |

---

## Maintenance

### When to Update

Update these codemaps when:
- New major features are added
- API routes change or new endpoints are created
- Database schema is modified
- Dependency versions change significantly
- System architecture changes

### How to Update

1. Scan the relevant source files
2. Update the corresponding codemap
3. Verify all cross-references still work
4. Update the freshness timestamp (comment at top)

### Quality Checklist

Before committing changes:
- [ ] All file paths verified
- [ ] Code examples match actual implementation
- [ ] No stale references or outdated info
- [ ] Cross-references ("Related Areas") correct
- [ ] Freshness timestamp updated
- [ ] Token count still within budget (~1000 per doc)

---

## File Structure

```
docs/CODEMAPS/
├── README.md                # This file
├── INDEX.md                 # Start here
├── architecture.md          # System overview
├── backend.md               # API & services
├── frontend.md              # React components
├── data.md                  # Data models
└── dependencies.md          # Packages & versions
```

---

## Related Documentation

- [`docs/requirements_v4.md`](../requirements_v4.md) — Full feature specification
- [`docs/2511.13646v3.pdf`](../2511.13646v3.pdf) — LIVE-SWE-AGENT research paper (referenced architecture)
- `docker-compose.yml` — Container orchestration
- `nginx.conf` — Reverse proxy configuration
- `backend/pyproject.toml` — Python dependencies
- `frontend/package.json` — JavaScript dependencies

---

## Links

- **GitHub**: (add link if available)
- **Paper**: [LIVE-SWE-AGENT](https://arxiv.org/abs/2511.13646)
- **Requirements**: Phase 1 MVP; Phase 2 adds upload, execution; Phase 3 adds skills
- **Development**: All work happens in Docker containers

---

## Questions?

Refer to the appropriate codemap:
- "How does the system work?" → architecture.md
- "Where is the API?" → backend.md
- "How do I build UI?" → frontend.md
- "What are the data models?" → data.md
- "What packages are used?" → dependencies.md
- "Overview?" → INDEX.md

---

**These codemaps are the single source of truth for the codebase. Update them when architecture or implementation changes.**
