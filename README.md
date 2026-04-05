# ToolBuilder

自然言語の指示から Excel/CSV 処理用の Python コードを自動生成・実行する AI ツールビルダー。

## 概要

ToolBuilder は、ユーザーが Excel ファイルをアップロードし、やりたい処理を日本語で記述するだけで、Python コードの生成・サンドボックス実行・自動デバッグまでを一貫して行う Web アプリケーションです。

### 主な機能

- **自然言語→コード生成**: タスク記述から Python コードを自動生成
- **多段パイプライン**: 探索(A)→分析(B)→生成(C)→デバッグ(D)→保存(E) の段階的処理
- **自己修復ループ**: 実行エラー時に自動でコードを修正・リトライ
- **スキル機能**: 成功したコードを再利用可能なスキルとして保存・提案
- **Eval ハーネス**: アーキテクチャ比較のための A/B テスト基盤
- **MagenticOne 統合**: Microsoft のマルチエージェントフレームワークによる代替オーケストレーション

## 技術スタック

| レイヤー | 技術 |
|----------|------|
| Backend | FastAPI, Python 3.13+, SQLAlchemy (async), SQLite |
| Frontend | React 19, TypeScript, Vite, Tailwind CSS v4, Zustand |
| AI/LLM | OpenAI API (gpt-4o) |
| Infra | Docker Compose, nginx, Langfuse (optional) |

## クイックスタート

### 前提条件

- Docker & Docker Compose
- OpenAI API キー

### セットアップ

```bash
# 1. .env を作成
cp backend/.env.example backend/.env
# backend/.env の OPENAI_API_KEY を設定

# 2. 起動
docker-compose up --build

# 3. アクセス
# http://localhost (nginx経由)
# http://localhost:5173 (フロントエンド直接)
# http://localhost:8000 (バックエンド直接)
```

### ローカル開発

```bash
# Backend
cd backend
uv sync
uvicorn main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev
```

## 環境変数

`backend/.env` で設定します（`backend/.env.example` を参照）。

| 変数名 | 必須 | 説明 |
|--------|------|------|
| `OPENAI_API_KEY` | Yes | OpenAI API キー |
| `OPENAI_MODEL` | No | 使用モデル（デフォルト: `gpt-4o`） |
| `DATABASE_URL` | No | DB 接続文字列 |
| `EXEC_TIMEOUT` | No | コード実行タイムアウト秒数（デフォルト: 30） |
| `DEBUG_RETRY_LIMIT` | No | デバッグリトライ上限（デフォルト: 3） |
| `SKILLS_ENABLED` | No | スキル機能の有効化 |
| `LANGFUSE_ENABLED` | No | Langfuse トレーシングの有効化 |

## アーキテクチャ

### パイプライン

```
Upload → Phase A (探索) → Phase B (分析) → Phase C (コード生成)
                                                ↓
         Phase E (スキル保存) ← Phase D (デバッグループ)
                                                ↓ (eval時)
                                  Phase F/G (品質評価ループ)
```

### プロジェクト構成

```
ToolBuilder/
├── backend/
│   ├── core/          # 設定、依存性注入、例外処理
│   ├── db/            # SQLAlchemy モデル・エンジン
│   ├── routers/       # API エンドポイント
│   ├── pipeline/      # オーケストレーション・各フェーズ処理
│   │   └── magentic_one/  # MagenticOne マルチエージェント
│   ├── infra/         # OpenAI クライアント、サンドボックス、プロンプト管理
│   ├── eval/          # Eval ハーネス（テストケース・アーキテクチャ定義）
│   ├── prompts/       # LLM プロンプトテンプレート
│   └── tests/         # テスト
├── frontend/
│   └── src/
│       ├── components/    # UI コンポーネント
│       ├── api/           # API クライアント
│       ├── stores/        # Zustand ストア
│       └── hooks/         # カスタムフック
├── docker-compose.yml
└── nginx.conf
```

## API エンドポイント

### ファイル操作

| メソッド | パス | 説明 |
|----------|------|------|
| POST | `/api/upload` | ファイルアップロード・パース |
| GET | `/api/download/{path}` | 生成ファイルのダウンロード |

### コード生成・実行

| メソッド | パス | 説明 |
|----------|------|------|
| POST | `/api/generate` | コード生成（SSE / JSON） |
| POST | `/api/execute` | サンドボックスでコード実行 |

### 履歴・スキル

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/api/history` | 実行履歴一覧 |
| GET/POST/DELETE | `/api/skills` | スキル CRUD |
| POST | `/api/skills/{id}/run` | スキル実行 |

### Eval

| メソッド | パス | 説明 |
|----------|------|------|
| GET | `/eval/architectures` | アーキテクチャ一覧 |
| POST | `/eval/run` | Eval 実行開始 |
| GET | `/eval/run/{id}/stream` | 進捗 SSE ストリーム |

## テスト

```bash
# Backend
cd backend
pytest

# Frontend
cd frontend
npm test
```

## ライセンス

Private
