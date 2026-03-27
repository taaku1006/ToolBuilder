<!-- Generated: 2026-03-27 | Files scanned: src/**/*.tsx, src/**/*.ts | Token estimate: ~850 -->

# Frontend Architecture

**Framework**: React 19 + TypeScript + Vite
**Port**: 5173 (dev), served via nginx in production
**Package Manager**: npm
**Last Updated**: 2026-03-27

---

## Module Overview

```
frontend/src/
├── App.tsx                          # Root component (26 lines) ✅
├── main.tsx                         # React entry point
├── components/
│   ├── TaskInput.tsx                # Input textarea + button (39 lines) ✅
│   ├── CodeResult.tsx               # Results display (64 lines) ✅
│   ├── layout/
│   │   └── Header.tsx               # App header ✅
│   └── __tests__/
│       ├── TaskInput.test.tsx       # Input component tests (30 tests)
│       └── CodeResult.test.tsx      # Result component tests
├── api/
│   ├── client.ts                    # Axios instance (7 lines) ✅
│   ├── generate.ts                  # postGenerate function (8 lines) ✅
│   └── __tests__/
│       └── generate.test.ts         # API integration tests
├── stores/
│   ├── useGenerateStore.ts          # Zustand store (46 lines) ✅
│   └── __tests__/
│       └── useGenerateStore.test.ts # Store logic tests
├── types/
│   └── index.ts                     # TypeScript interfaces (15 lines) ✅
├── hooks/                           # Utilities directory (empty)
├── lib/                             # Utility functions (empty)
├── index.css                        # Global styles (Tailwind)
├── test-setup.ts                    # Vitest config
├── assets/                          # Static assets
├── vite.config.ts                   # Build configuration
├── tsconfig.json                    # TypeScript config
├── tailwind.config.ts               # Tailwind CSS config
├── package.json                     # Dependencies & scripts
└── __tests__/
    └── e2e/                         # E2E tests (Playwright, future)
```

---

## Component Hierarchy

```
App.tsx (Root)
├─ Header (Layout)
├─ TaskInput (Form)
│  └─ useGenerateStore hook
│     ├─ task (input state)
│     ├─ loading (UI state)
│     ├─ setTask (setter)
│     └─ generate (async action)
├─ Error Display (Conditional)
│  └─ useGenerateStore.error
└─ CodeResult (Display)
   └─ useGenerateStore.response
      ├─ Summary section
      ├─ Steps section (list)
      ├─ Code block (syntax-highlighted)
      ├─ Copy button
      └─ Tips section (conditional)
```

---

## Core Components

### App.tsx

**Location**: `frontend/src/App.tsx` (26 lines)

```typescript
function App() {
  const { error } = useGenerateStore()

  return (
    <div className="min-h-screen bg-gray-950 text-gray-100">
      <Header />
      <main className="max-w-4xl mx-auto px-6 py-8 space-y-6">
        <TaskInput />
        {error && (
          <div className="bg-red-950 border border-red-800 text-red-300 rounded-lg px-4 py-3 text-sm">
            {error}
          </div>
        )}
        <CodeResult />
      </main>
    </div>
  )
}
```

**Features**:
- Dark theme (gray-950 background, gray-100 text)
- Responsive grid (max-w-4xl, px-6)
- Error banner with red styling
- Vertical spacing (space-y-6)

---

### TaskInput.tsx

**Location**: `frontend/src/components/TaskInput.tsx` (39 lines)

```typescript
export function TaskInput() {
  const { task, loading, setTask, generate } = useGenerateStore()

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
      e.preventDefault()
      generate()
    }
  }

  return (
    <div className="w-full">
      <textarea
        className="w-full min-h-32 px-4 py-3 bg-gray-800 text-gray-100 border border-gray-600 rounded-lg resize-y focus:outline-none focus:border-blue-500 placeholder-gray-500 font-sans text-sm disabled:opacity-50 disabled:cursor-not-allowed"
        placeholder="タスクを日本語で入力してください (例: 売上データを月別に集計してグラフを作成する)"
        value={task}
        onChange={(e) => setTask(e.target.value)}
        onKeyDown={handleKeyDown}
        disabled={loading}
      />
      <div className="mt-3 flex items-center justify-between">
        <span className="text-xs text-gray-500">
          Cmd+Enter でも生成できます
        </span>
        <button
          className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          onClick={generate}
          disabled={loading}
        >
          {loading ? '生成中...' : '生成'}
        </button>
      </div>
    </div>
  )
}
```

**Features**:
- Textarea with min-h-32 (resizable)
- Placeholder with example
- Cmd/Ctrl+Enter keyboard shortcut
- Generate button with loading state
- Disabled state when loading
- Blue primary button style

**Keyboard Shortcut**:
```typescript
if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
  e.preventDefault()
  generate()
}
```

---

### CodeResult.tsx

**Location**: `frontend/src/components/CodeResult.tsx` (64 lines)

```typescript
export function CodeResult() {
  const { response } = useGenerateStore()
  const [copied, setCopied] = useState(false)

  if (!response) return null

  const handleCopy = async () => {
    await navigator.clipboard.writeText(response.python_code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="w-full space-y-4">
      {/* Summary Section */}
      <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
        <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-2">
          概要
        </h2>
        <p className="text-gray-100 text-sm">{response.summary}</p>
      </div>

      {/* Steps Section */}
      {response.steps.length > 0 && (
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-4">
          <h2 className="text-sm font-semibold text-gray-400 uppercase tracking-wider mb-3">
            実行ステップ
          </h2>
          <ol className="space-y-1.5 list-decimal list-inside">
            {response.steps.map((step, index) => (
              <li key={index} className="text-gray-200 text-sm">
                {step}
              </li>
            ))}
          </ol>
        </div>
      )}

      {/* Code Block */}
      <div className="bg-gray-900 border border-gray-700 rounded-lg overflow-hidden">
        <div className="flex items-center justify-between px-4 py-2 bg-gray-800 border-b border-gray-700">
          <span className="text-xs text-gray-400 font-medium">Python</span>
          <button
            className="px-3 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-gray-200 rounded transition-colors"
            onClick={handleCopy}
          >
            {copied ? 'コピー済み' : 'コピー'}
          </button>
        </div>
        <pre className="p-4 overflow-x-auto text-sm text-green-300 font-mono leading-relaxed">
          <code>{response.python_code}</code>
        </pre>
      </div>

      {/* Tips Section */}
      {response.tips && (
        <div className="bg-yellow-950 border border-yellow-800 rounded-lg p-4">
          <h2 className="text-sm font-semibold text-yellow-400 mb-1">ヒント</h2>
          <p className="text-yellow-200 text-sm">{response.tips}</p>
        </div>
      )}
    </div>
  )
}
```

**Features**:
- Summary box (gray-800, p-4)
- Steps list (ordered, conditional display)
- Code block with header
  - Language label: "Python"
  - Copy button (with state feedback)
  - Syntax highlighting (green-300, font-mono)
- Tips section (yellow theme, conditional)
- Responsive overflow handling

**Copy Button Logic**:
```typescript
const handleCopy = async () => {
  await navigator.clipboard.writeText(response.python_code)
  setCopied(true)
  setTimeout(() => setCopied(false), 2000)  // Hide feedback after 2s
}
```

---

## State Management (Zustand)

### useGenerateStore

**Location**: `frontend/src/stores/useGenerateStore.ts` (46 lines)

```typescript
interface GenerateState {
  task: string
  response: GenerateResponse | null
  loading: boolean
  error: string | null
  setTask: (task: string) => void
  generate: () => Promise<void>
  reset: () => void
}

const initialState = {
  task: '',
  response: null,
  loading: false,
  error: null,
}

export const useGenerateStore = create<GenerateState>((set, get) => ({
  ...initialState,

  setTask: (task) => set({ task }),

  generate: async () => {
    const { task } = get()
    if (!task.trim()) return

    set({ loading: true, error: null })

    try {
      const response = await postGenerate(task)
      set({ response, loading: false })
    } catch {
      set({
        loading: false,
        error: 'コード生成に失敗しました。もう一度お試しください。',
      })
    }
  },

  reset: () => set({ ...initialState }),
}))
```

**State**:
- `task: string` — Current input text
- `response: GenerateResponse | null` — API response or null
- `loading: boolean` — Network operation in progress
- `error: string | null` — Error message or null

**Actions**:
- `setTask(task)` — Update input
- `generate()` — Call API (async)
  - Validates non-empty task
  - Sets loading=true, error=null
  - Calls postGenerate(task)
  - Updates response on success
  - Sets error message on failure
- `reset()` — Clear all state

---

## API Client

### client.ts

**Location**: `frontend/src/api/client.ts` (7 lines)

```typescript
import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
})

export default client
```

**Configuration**:
- baseURL: `/api` (relative, routed to backend:8000 by nginx)
- Uses axios interceptors (future: add auth headers, response transformation)

---

### generate.ts

**Location**: `frontend/src/api/generate.ts` (8 lines)

```typescript
import client from './client'
import type { GenerateResponse } from '../types'

export async function postGenerate(task: string): Promise<GenerateResponse> {
  const response = await client.post<GenerateResponse>('/generate', { task })
  return response.data
}
```

**Endpoint**: POST /api/generate
**Request Body**: `{ task: string }`
**Response**: `GenerateResponse` (typed)

---

## Data Types

### types/index.ts

**Location**: `frontend/src/types/index.ts` (15 lines)

```typescript
export interface GenerateRequest {
  task: string
  file_id?: string
  max_steps?: number
  skill_id?: string
}

export interface GenerateResponse {
  id: string
  summary: string
  python_code: string
  steps: string[]
  tips: string
}
```

**GenerateRequest**:
- `task` (required): Natural language instruction
- `file_id` (optional): Future file upload reference
- `max_steps` (optional): Reflection iteration count
- `skill_id` (optional): Skill to apply

**GenerateResponse**:
- `id`: UUID from backend
- `summary`: One-liner in Japanese
- `python_code`: Complete executable script
- `steps`: Array of execution steps
- `tips`: Runtime notes in Japanese

---

## Build & Development

### Vite Configuration

**File**: `frontend/vite.config.ts`

```typescript
// Builds React with hot module replacement (HMR)
// Output: dist/ (built into nginx in production)
```

### Scripts (package.json)

```json
{
  "dev": "vite",                          # Start dev server on 5173
  "build": "tsc -b && vite build",        # Compile TS + build
  "lint": "eslint .",                     # Lint code
  "preview": "vite preview",              # Preview built app
  "test": "vitest run",                   # Run tests once
  "test:watch": "vitest",                 # Watch mode
  "test:coverage": "vitest run --coverage"
}
```

---

## Testing

**Framework**: Vitest (30 tests)

**Test Files**:
- `components/__tests__/TaskInput.test.tsx` — Input component behavior
- `components/__tests__/CodeResult.test.tsx` — Output component display
- `stores/__tests__/useGenerateStore.test.ts` — Store state & async actions
- `api/__tests__/generate.test.ts` — API client integration

**Run Tests**:
```bash
npm run test              # Single run
npm run test:watch       # Watch mode
npm run test:coverage    # Coverage report (80%+ required)
```

---

## Styling

### Tailwind CSS

**Colors**:
- Background: gray-950 (dark), gray-900, gray-800, gray-700
- Text: gray-100 (primary), gray-200, gray-400, gray-500
- Primary: blue-600, blue-700
- Accent: yellow-950 (tips), red-950 (error), green-300 (code)

**Utilities**:
- Responsive: `min-h-screen`, `px-6`
- Layout: `flex`, `items-center`, `justify-between`, `space-y-6`
- Typography: `text-sm`, `font-semibold`, `uppercase`, `font-mono`

---

## Dependencies

From `package.json`:
```
react@^19.2.4              # UI library
react-dom@^19.2.4          # DOM binding
zustand@^5.0.0             # State management
axios@^1.7.0               # HTTP client

[dev]
@types/react@^19.2.14
@types/react-dom@^19.2.3
typescript@~5.9.3
vite@^8.0.1
vitest@^3.2.4
@testing-library/react@^16.3.0
@tailwindcss/vite@^4.1.0
tailwindcss@^4.1.0
eslint@^9.39.4
```

---

## Related Areas

- [System Architecture](./architecture.md) — Request flow from React to API
- [Backend API](./backend.md) — POST /api/generate endpoint
- [Data Models](./data.md) — Request/response schemas
- [External Dependencies](./dependencies.md) — React, Zustand, axios versions
