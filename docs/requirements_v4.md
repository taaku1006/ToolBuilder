# Excel × 自然言語 ツールビルダー — 機能要件書
## Claude Code 実装用

**バージョン**: 4.1
**作成日**: 2026-03-26
**対象**: Claude Code による実装
**参照論文**: LIVE-SWE-AGENT: Can Software Engineering Agents Self-Evolve on the Fly? (arXiv:2511.13646v3)
**利用環境**: 社内PC
**出力形式**: Python（openpyxl / pandas）

---

## 1. プロダクト概要

Excel ファイル（xlsx/xls/csv）をアップロードし、自然言語でやりたい処理を記述するだけで、
AI エージェントが**自律的に生成・テスト実行・自己修正**し、
動作保証済みの Python スクリプトとして出力するWebアプリケーション。

### v4.1 の設計思想

**Python 完結型**を採用。生成した Python コードをサンドボックスで実行・自律デバッグし、
動作保証が取れた状態でユーザーに提供する。

```
① Python でコード生成・サンドボックス実行・自律デバッグ
      ↓ LIVE-SWE-AGENT のメカニズムをフル活用
② 動作確認済みの Python コードとその実行結果をユーザーに提供
      ↓ コードコピー + 処理済み Excel ダウンロード
③ ユーザーが Python スクリプトを再利用、または処理済みファイルをそのまま使用
```

> 論文 Section 4.4「Applications beyond software issue resolution tasks」より:
> 事前定義された固定のツールセットに依存せず、目の前の課題に合わせてエージェント自身を
> 動的に適応させるアプローチは、異なるドメインのタスク解決にも容易に一般化できる。

### 3つのコアメカニズム

#### メカニズム1: ファイル固有ツールの動的生成
アップロードされたExcelの構成（列名・データ型・空白セルの有無など）を読み取る
探索スクリプトをまず自動生成し、その結果をもとにファイル専用のコードをその場で生成する。

#### メカニズム2: エラーからの自律修正（Step-Reflection）
生成した Python コードをサンドボックスでテスト実行し、エラー出力を振り返って
自律的にコードを修正・進化させるループを回す。

#### メカニズム3: Skillsとしてのスクリプト蓄積・再利用
成功した Python コードを Skills として保存。
類似ファイルが来た際にオンザフライでロードして再利用し、
処理速度と精度を継続的に向上させる。

### 生成フロー（v4.1）

```
アップロード・タスク入力
  │
  ▼
【Phase A: 探索】
  エージェントがExcelの構造を読む探索スクリプトを自動生成
  → サンドボックスで実行
  → 列名・型・欠損・特異値などをフィードバックとして取得
  │
  ▼
【Phase B: Reflect & ツール合成】
  「このデータに特化したツールが必要か？」を内省
  → 必要なら専用スクリプトを生成・実行
  │
  ▼
【Phase C: Python 本番コード生成】
  Phase A/B の知見を全て反映した Python コードを生成
  │
  ▼
【Phase D: 自律デバッグ】
  サンドボックスで実行 → エラー検出
  → Step-Reflection: エラー内容を振り返り修正コードを生成
  → 再実行（最大 retry_limit 回）
  → Python での動作保証が確定
  │
  ▼
【Phase E: Skills 保存】
  Python コードを Skills DB に保存
  → 類似ファイルが来た際に自動サジェスト・再利用
```

---

## 2. 技術スタック

### フロントエンド
| 項目 | 採用技術 |
|---|---|
| フレームワーク | React 18 + TypeScript |
| ビルドツール | Vite |
| スタイリング | Tailwind CSS + shadcn/ui |
| Excel 解析 | SheetJS (xlsx) ※ブラウザ側で処理 |
| HTTP クライアント | axios または fetch |
| 状態管理 | Zustand |

### バックエンド
| 項目 | 採用技術 |
|---|---|
| フレームワーク | Python 3.11 + FastAPI |
| バリデーション | Pydantic v2 |
| AI | OpenAI API (gpt-4o) |
| xlsx 解析 | openpyxl + pandas |
| DB | SQLite（SQLAlchemy） |
| コード実行 | Python subprocess（サンドボックス） |
| Reflection Engine | backend/services/reflection_engine.py |
| Debug Loop | backend/services/debug_loop.py |
| Skills Engine | backend/services/skills_engine.py |
| ファイル保存 | ローカルFS（./uploads/） |

---

## 3. ディレクトリ構成

```
excel-tool-builder/
├── backend/
│   ├── main.py
│   ├── routers/
│   │   ├── generate.py               # POST /api/generate
│   │   ├── upload.py                 # POST /api/upload
│   │   ├── execute.py                # POST /api/execute
│   │   ├── history.py                # GET/DELETE /api/history
│   │   └── skills.py                 # GET/POST /api/skills
│   ├── services/
│   │   ├── openai_client.py
│   │   ├── reflection_engine.py      # Reflection Loop
│   │   ├── debug_loop.py             # 自律デバッグ
│   │   ├── skills_engine.py          # Skills 蓄積・検索
│   │   ├── xlsx_parser.py
│   │   └── sandbox.py
│   ├── db/
│   ├── schemas/
│   ├── uploads/
│   ├── tools/
│   └── skills/
│       ├── index.json
│       └── {skill_id}/
│           └── script.py
├── frontend/
│   └── src/components/
│       ├── FileUpload.tsx
│       ├── SheetPreview.tsx
│       ├── TaskInput.tsx
│       ├── AgentLog.tsx              # Phase A〜E の進捗ログ
│       ├── DebugLog.tsx              # 自律デバッグ履歴
│       ├── CodeResult.tsx            # Python コード表示 + コピー
│       ├── SkillsPanel.tsx
│       └── HistoryPanel.tsx
├── docker-compose.yml
├── nginx.conf
└── README.md
```

---

## 4. 機能要件

### 4.1 ファイルアップロード・解析（F-01〜F-06）

| ID | 機能 | 優先度 |
|---|---|---|
| F-01 | xlsx / xls / csv のドラッグ&ドロップ + クリック選択 | Must |
| F-02 | ブラウザ側 SheetJS によるシート一覧・列名・型の即時解析 | Must |
| F-03 | 先頭 30 行のインラインテーブルプレビュー（シートタブ切替） | Must |
| F-04 | 列名・型・サンプル3行をプロンプトに自動注入 | Must |
| F-05 | ファイルをバックエンドにも送信し server-side でも解析（実行用） | Must |
| F-06 | 50 MB 超・非対応形式はエラーメッセージ表示 | Must |

---

### 4.2 コード生成・エージェントループ（F-10〜F-20）

| ID | 機能 | 優先度 |
|---|---|---|
| F-10 | 自然言語（日本語）でタスクを自由記述 | Must |
| F-11 | 出力形式は Python に統一 | Must |
| F-12 | Cmd+Enter ショートカットで生成 | Must |
| F-13 | クイック入力プリセット（5〜8件） | Should |
| F-14 | フェーズ別進捗表示（Phase A〜E） | Must |
| F-15 | ファイル未添付でも動作（汎用コード生成モード） | Must |
| F-16 | Reflection ステップ数を UI で設定（1〜5） | Should |
| F-17 | Skills サジェスト: 類似ファイル・タスクの既存 Skill を冒頭に提示 | Should |
| F-18 | Skill を選択して「このSkillをベースに生成」する機能 | Should |
| F-19 | 生成成功時に Skill として保存するかユーザーが選択 | Should |
| F-20 | 探索フェーズ（Phase A）の結果をユーザーが確認・承認してから本番生成 | Should |

---

### 4.3 コード実行・プレビュー（F-30〜F-37）

| ID | 機能 | 優先度 |
|---|---|---|
| F-30 | 生成 Python コードをサンドボックスで実行 | Must |
| F-31 | stdout / stderr をリアルタイムで表示 | Must |
| F-32 | DataFrame 出力はテーブル形式でレンダリング | Should |
| F-33 | タイムアウト: デフォルト 30 秒（.env で変更可） | Must |
| F-34 | 実行後に生成された xlsx をダウンロード | Must |
| F-35 | Python コードのコピーボタン | Must |
| F-36 | アップロードファイルを INPUT_FILE に自動バインド | Must |
| F-37 | 自律デバッグログの表示（何回目の修正で成功したか・修正理由） | Should |

---

### 4.4 Skills 蓄積・再利用（F-40〜F-45）

| ID | 機能 | 優先度 |
|---|---|---|
| F-40 | 生成成功時に Skill として保存（タイトル・タグ・対象ファイル特徴を記録） | Should |
| F-41 | アップロード時にファイルの特徴と既存 Skills を照合してサジェスト | Should |
| F-42 | Skills 一覧画面: 名前・タグ・作成日・使用回数・成功率を表示 | Should |
| F-43 | Skill を選択してベースとして生成 | Should |
| F-44 | Skill の編集・削除・エクスポート（.py） | Could |
| F-45 | Skill の使用回数・成功率を自動集計 | Could |

#### Skills DB スキーマ
```sql
CREATE TABLE skills (
  id            TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
  created_at    DATETIME DEFAULT CURRENT_TIMESTAMP,
  title         TEXT NOT NULL,
  tags          TEXT,               -- JSON array
  python_code   TEXT NOT NULL,
  file_schema   TEXT,               -- 対象ファイルの列構成特徴
  task_summary  TEXT,
  use_count     INTEGER DEFAULT 0,
  success_rate  REAL DEFAULT 1.0,
  source_history_id TEXT
);
```

---

### 4.5 生成履歴管理（F-50〜F-57）

| ID | 機能 | 優先度 |
|---|---|---|
| F-50 | 生成成功時に SQLite へ自動保存 | Must |
| F-51 | 履歴サイドバー: タスク概要・日時 | Must |
| F-52 | 履歴クリックで生成結果を再表示 | Must |
| F-53 | タスク内容の全文検索（SQLite FTS5） | Must |
| F-54 | フィルタリング（成功 / 失敗） | Should |
| F-55 | 履歴の個別削除 | Must |
| F-56 | 履歴へのメモ追記（インライン編集） | Should |
| F-57 | 履歴から「再生成」— 同パラメータで OpenAI API 再実行 | Should |

#### 生成履歴 DB スキーマ
```sql
CREATE TABLE history (
  id               TEXT PRIMARY KEY DEFAULT (lower(hex(randomblob(8)))),
  created_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
  task             TEXT NOT NULL,
  file_name        TEXT,
  summary          TEXT,
  python_code      TEXT NOT NULL,
  steps            TEXT,
  tips             TEXT,
  memo             TEXT,
  exec_stdout      TEXT,
  exec_stderr      TEXT,
  agent_log        TEXT,               -- JSON: Phase A〜E の全ログ
  reflection_steps INTEGER DEFAULT 1,
  debug_retries    INTEGER DEFAULT 0,
  skill_id         TEXT
);
```

---

## 5. API 設計

### POST /api/upload
```
Body: multipart/form-data (file: xlsx/xls/csv, max 50MB)
Response 200: {
  file_id, filename,
  sheets[{name, total_rows, headers, types, preview}],
  suggested_skills: [{id, title, tags, similarity}]
}
```

### POST /api/generate
```
Body: { task, file_id?, max_steps?, skill_id? }
Response 200: {
  id, summary, steps[],
  python_code,
  tips,
  agent_log: [{phase, action, content, timestamp}],
  reflection_steps, debug_retries,
  suggested_skill_save: true
}
```

### POST /api/execute
```
Body: { code, file_id? }
Response 200: {
  stdout, stderr, elapsed_ms,
  output_files[], dataframe_json,
  generated_tools[],
  debug_log: [{retry, reason, fixed}],
  success: bool
}
```

### GET/POST /api/skills | GET/DELETE /api/history/{id}
（v3.0 と同仕様）

---

## 6. 環境変数

```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
DATABASE_URL=sqlite:///./db/history.db
UPLOAD_DIR=./uploads
OUTPUT_DIR=./outputs
MAX_UPLOAD_MB=50
EXEC_TIMEOUT=30
CORS_ORIGINS=http://localhost:5173,http://社内サーバーIP

# Reflection Loop
REFLECTION_ENABLED=true
REFLECTION_MAX_STEPS=3
TOOLS_DIR=./tools

# 自律デバッグ
DEBUG_LOOP_ENABLED=true
DEBUG_RETRY_LIMIT=3

# Skills
SKILLS_ENABLED=true
SKILLS_DIR=./skills
SKILLS_SIMILARITY_THRESHOLD=0.4
```

---

## 7. docker-compose 構成

```yaml
version: "3.9"
services:
  backend:
    build: ./backend
    ports: ["8000:8000"]
    env_file: ./backend/.env
    volumes:
      - ./backend/uploads:/app/uploads
      - ./backend/outputs:/app/outputs
      - ./backend/tools:/app/tools
      - ./backend/skills:/app/skills
      - ./backend/db:/app/db
  frontend:
    build: ./frontend
    ports: ["5173:80"]
    depends_on: [backend]
  nginx:
    image: nginx:alpine
    ports: ["80:80"]
    volumes: [./nginx.conf:/etc/nginx/nginx.conf]
    depends_on: [backend, frontend]
```

---

## 8. 画面構成

```
┌─────────────────────────────────────────────────────────────┐
│  Header: Excel × AI ツールビルダー                          │
├──────────────┬──────────────────────────────────────────────┤
│              │                                              │
│  履歴        │  ① ファイルアップロードゾーン               │
│  サイドバー  │     └─ シートプレビュー（タブ切替）         │
│              │     └─ Skills サジェスト                    │
│  [検索]      │                                              │
│              │  ② タスク入力 + Skills ベース選択          │
│  履歴リスト  │                                              │
│  ・task概要  │  ③ Generate ボタン                          │
│  ・成功/失敗 │                                              │
│  ・日時      │  ④ エージェントログ（Phase A〜E）           │
│              │     ├─ Phase A: 探索結果                    │
│  ──────      │     ├─ Phase B: ツール合成                  │
│              │     ├─ Phase C: Python 本番コード           │
│  Skills      │     ├─ Phase D: 自律デバッグ履歴            │
│  サイドバー  │     └─ Phase E: Skills 保存                │
│  ・skill名   │                                              │
│  ・.py       │  ⑤ 結果パネル                               │
│  ・使用回数  │     ├─ Python コード + コピーボタン         │
│              │     ├─ 実行結果（stdout / テーブル表示）     │
│              │     └─ 処理済みファイル ダウンロード         │
│              │                                              │
└──────────────┴──────────────────────────────────────────────┘
```

---

## 9. 実装フェーズ

### Phase 1 — MVP（目安: 3〜5日）
- [ ] FastAPI ベース構築 + CORS 設定
- [ ] OpenAI API 呼び出し + Python コード生成
- [ ] React フロント: 入力 → 生成 → Python コードブロック表示
- [ ] Docker 化（全フラグ=false で稼働）

### Phase 2 — ファイル連携（目安: 2〜3日）
- [ ] xlsx アップロード + SheetJS ブラウザ解析
- [ ] /api/upload + openpyxl 解析 + プロンプト注入
- [ ] シートプレビューテーブル UI

### Phase 3 — 実行 + 履歴（目安: 2〜3日）
- [ ] SQLite 履歴 DB
- [ ] Python サンドボックス実行 + stdout/stderr 表示
- [ ] 実行成功フラグの管理
- [ ] 処理済みファイルのダウンロード機能

### Phase 4 — Reflection Loop（目安: 2〜3日）※ Phase 3 完了後
- [ ] reflection_engine.py 実装（Phase A〜C）
- [ ] AgentLog コンポーネント（フェーズ別進捗表示）

### Phase 5 — 自律デバッグ（目安: 1〜2日）※ Phase 4 完了後
- [ ] debug_loop.py 実装
- [ ] DebugLog コンポーネント（修正履歴表示）

### Phase 6 — Skills 蓄積（目安: 2〜3日）※ Phase 5 完了後
- [ ] skills_engine.py 実装
- [ ] SkillsPanel + サジェスト UI

### Phase 7 — 品質向上（随時）
- [ ] DataFrame テーブルレンダリング
- [ ] Skills のエクスポート（.py）
- [ ] Reflection 効果の A/B 計測

---

## 10. 設計根拠

### Python 完結型の採用根拠

| 比較軸 | Python 完結型（採用） |
|---|---|
| サンドボックス実行 | subprocess で安全に実行可能 |
| 自律デバッグ | エラー出力を解析 → 自動修正ループ |
| 動作保証 | 実行成功をもって品質担保 |
| Skills 蓄積 | 実行成功済みコードのみ保存 |
| 出力の柔軟性 | 処理済み Excel ダウンロード + コードコピー |

### 論文との対応

| 本プロダクトの仕組み | LIVE-SWE-AGENT 論文との対応 |
|---|---|
| Phase A: 探索スクリプト自動生成 | Figure 3b: marc_analyzer.py の動的生成（Section 2.2） |
| Phase D: 自律デバッグ | フィードバックを受けた反復的修正（Section 2.2） |
| Phase E: Skills 保存 | Section 4.4 Skills Future Work の具体実装 |
| REFLECTION_ENABLED フラグ | Table 4: 62% → 76% の A/B 比較設計 |

---

## 11. Claude Code 向け実装メモ

### 起動コマンド
```bash
cd backend && pip install -r requirements.txt
uvicorn main:app --reload --port 8000

cd frontend && npm install && npm run dev
```

### 推奨実装順序
Phase 1 → 2 → 3（サンドボックス確立）
→ 4（Reflection）→ 5（自律デバッグ）
→ 6（Skills）→ 7（品質向上）

### 注意事項
- OPENAI_API_KEY は必ず環境変数から読み込む（ハードコーディング禁止）
- DEBUG_RETRY_LIMIT を超えてもエラーが残る場合はユーザーに手動修正を促す
