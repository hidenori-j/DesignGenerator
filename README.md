# DesignGenerator

Agentic RAG x Conditional Diffusion Model -- 次世代AIデザイン生成システム

## Overview

エージェンティックRAGと条件付き拡散モデルを統合したAIデザイン生成システム。
プロンプトからデザイン要素を分解し、リファレンス画像を検索・スコアリングし、最適なプロバイダーで画像を生成する E2E パイプライン。

> 初めての方は **[ユーザーガイド](docs/USER_GUIDE.md)** をご覧ください。

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Browser (Next.js 16 / React 19 / Tailwind CSS v4)         │
│  :3000                                                      │
│  /generator  /upload  /collector                            │
└───────────────────────┬─────────────────────────────────────┘
                        │ HTTP / WebSocket
┌───────────────────────▼─────────────────────────────────────┐
│  API Gateway (Hono on Bun)  :4000                           │
│  /api/v1/generate  /search  /ingest  /collector/jobs        │
│  /ws/generation (real-time progress polling)                │
└──┬──────────┬───────────┬───────────┬───────────────────────┘
   │          │           │           │
   ▼          ▼           ▼           ▼
 Agent      Ingest    Collector   Generation
 :8000      :8200      :8400       :8100
(FastAPI)  (FastAPI)  (FastAPI)   (FastAPI)
 LangGraph  CLIP       Playwright  ModelRouter
 GPT-5.4   ViT-B/32   HuggingFace Fal.ai FLUX.2 Pro
   │          │           │           │
   └──────────┴───────────┴───────────┘
              │
     ┌────────▼────────┐
     │  GPU Arbiter    │
     │  :8300          │
     │  Semaphore +    │
     │  DLQ + Watchdog │
     └────────┬────────┘
              │
   ┌──────────▼──────────┐
   │  Infrastructure     │
   │  Qdrant / Redis /   │
   │  PostgreSQL / MinIO │
   └─────────────────────┘
```

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16, React 19, Tailwind CSS v4 |
| API Gateway | Hono on Bun |
| Agent (RAG) | FastAPI, LangGraph, GPT-5.4 |
| Collector | FastAPI, Playwright, HuggingFace datasets |
| Ingest | FastAPI, sentence-transformers (CLIP ViT-B/32), Qdrant |
| Generation | FastAPI, Fal.ai FLUX.2 Pro, ModelRouter, aioboto3 |
| Vector DB | Qdrant (Named Vectors: visual + textual) |
| Cache | Redis (embedding cache) |
| GPU Control | Custom Arbiter (semaphore + Redis Stream job queue + DLQ + watchdog) |
| Storage | MinIO (S3-compatible), PostgreSQL 17 |

## Quick Start

### Prerequisites

- [Bun](https://bun.sh/) >= 1.2
- [Python](https://www.python.org/) >= 3.12
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [Docker](https://www.docker.com/) & Docker Compose (推奨、無くても MOCK モードで起動可)

### ワンクリック起動（推奨）

```batch
scripts\start-all.bat
```

ダブルクリックするだけで全サービスが起動し、ブラウザが自動で開きます。

- Docker が見つかれば **FULL モード**（全 7 サービス起動）
- Docker が無ければ **MOCK モード**（API + Web のみ、モックデータ）

### 手動セットアップ

```bash
# 1. TypeScript 依存関係のインストール
bun install

# 2. インフラ起動（Qdrant, Redis, PostgreSQL, MinIO）
docker compose -f infra/docker-compose.yml up -d

# 3. 環境変数の設定
cp .env.example .env
# .env を編集して API キーを設定

# 4. Python サービスの依存関係インストール
cd services/agent && uv sync && cd ../..
cd services/ingest && uv sync && cd ../..
cd services/generation && uv sync && cd ../..
cd services/gpu_arbiter && uv sync && cd ../..
cd services/collector && uv sync && cd ../..

# 5. Playwright ブラウザのインストール（Collector 用）
cd services/collector && .venv\Scripts\python.exe -m playwright install chromium && cd ../..

# 6. 開発サーバー起動
bun run dev
```

### 個別起動スクリプト

| スクリプト | 内容 | ポート |
|-----------|------|--------|
| `scripts\start-all.bat` | 全サービス一括起動 + ブラウザ自動オープン | -- |
| `scripts\start-dev.bat` | API + Web のみ（MOCK モード） | 4000, 3000 |
| `scripts\start-api.bat` | API Gateway 単体 | 4000 |
| `scripts\start-web.bat` | Next.js フロントエンド単体 | 3000 |
| `scripts\start-ingest.bat` | Ingest サービス単体 | 8200 |
| `scripts\start-generation.bat` | Generation サービス単体 | 8100 |
| `scripts\start-arbiter.bat` | GPU Arbiter 単体 | 8300 |
| `scripts\start-collector.bat` | Collector CLI（対話シェル） | -- |

## Features

### デザイン生成 (`/generator`)

プロンプトからAIデザインを生成する。WebSocket によるリアルタイム進捗表示付き。

1. テキストプロンプトを入力（+ 解像度・参照モード・ブランド等のオプション）
2. Agent が RAG パイプライン (クエリ分解 → 検索 → リランキング → プロンプト構築) を実行
3. Generation Service が ModelRouter で最適プロバイダーを選択し、Fal.ai FLUX.2 Pro で画像生成
4. 生成画像を MinIO に保存し、フロントエンドに返却

### 画像アップロード (`/upload`)

手持ちの画像を Ingest サービスに投入し、ベクトルインデックスに登録する。

- ドラッグ＆ドロップ対応
- カテゴリ選択（バナー、UI、アイコン、イラスト、写真）
- 複数ファイル同時アップロード

### デザイン収集 (`/collector`)

外部ギャラリーサイトや HuggingFace データセットからデザイン画像を自動収集する。

**対応ソース:**

| ソース | 方式 | ライセンスタグ |
|--------|------|---------------|
| Dribbble | Playwright スクレイピング | `copyrighted_reference` |
| Behance | Playwright スクレイピング | `copyrighted_reference` |
| Pinterest | Playwright スクレイピング + 無限スクロール | `copyrighted_reference` |
| Unsplash | 公式 API | `unsplash_license` |
| HuggingFace | datasets ライブラリ | `dataset_license` |

## API Reference

### API Gateway (`:4000`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | ヘルスチェック |
| POST | `/api/v1/generate` | デザイン生成ジョブ開始 |
| GET | `/api/v1/search` | リファレンスアセット検索 |
| POST | `/api/v1/ingest` | 画像アップロード（単一） |
| POST | `/api/v1/ingest/batch` | 画像アップロード（バッチ） |
| POST | `/api/v1/collector/jobs` | 収集ジョブ開始 |
| GET | `/api/v1/collector/jobs` | 収集ジョブ一覧 |
| GET | `/api/v1/collector/jobs/:id` | 収集ジョブ詳細 |
| GET | `/api/v1/collector/jobs/:id/images` | 収集済み画像一覧 |
| WS | `/ws/generation` | 生成進捗 WebSocket |

### Agent Service (`:8000`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | ヘルスチェック |
| POST | `/api/v1/generate` | RAG パイプライン + Generation 呼び出し |
| GET | `/api/v1/search` | ベクトル検索 |
| GET | `/api/v1/jobs/:id` | ジョブステータス |
| GET | `/api/v1/jobs` | ジョブ一覧 |

### Generation Service (`:8100`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | ヘルスチェック |
| POST | `/api/v1/generate` | 画像生成（ModelRouter → Fal.ai → MinIO） |
| GET | `/api/v1/jobs/:id` | 生成ジョブステータス |
| GET | `/api/v1/jobs` | 生成ジョブ一覧 |

### GPU Arbiter (`:8300`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | ヘルスチェック |
| POST | `/api/v1/jobs/submit` | GPU ジョブ投入 (Redis Stream) |
| GET | `/api/v1/jobs/:id` | ジョブステータス |
| GET | `/api/v1/jobs/dlq/list` | Dead Letter Queue 一覧 |
| POST | `/api/v1/jobs/dlq/process` | DLQ 再処理 |
| GET | `/api/v1/gpu/status` | GPU セマフォ状態 |
| POST | `/api/v1/gpu/force-release` | GPU セマフォ強制解放 |

### Ingest Service (`:8200`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/ingest` | 画像のベクトル化 + Qdrant 登録 |
| POST | `/api/v1/ingest/batch` | バッチ処理 |
| POST | `/api/v1/encode` | テキスト → ベクトル変換 |

### Collector Service (`:8400`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | ヘルスチェック |
| POST | `/api/v1/jobs` | 収集ジョブ開始 |
| GET | `/api/v1/jobs` | ジョブ一覧 |
| GET | `/api/v1/jobs/:id` | ジョブ詳細・進捗 |
| GET | `/api/v1/jobs/:id/images` | 収集済み画像一覧 |

## Project Structure

```
DesignGenerator/
├── apps/
│   ├── web/                    # Next.js フロントエンド
│   │   └── src/app/
│   │       ├── page.tsx        #   ホーム
│   │       ├── generator/      #   デザイン生成 (解像度/スタイル/ブランド)
│   │       ├── upload/         #   画像アップロード
│   │       └── collector/      #   デザイン収集
│   └── api/                    # Hono API Gateway (Bun)
│       └── src/
│           ├── routes/
│           │   ├── agent.ts    #   生成・検索プロキシ
│           │   ├── ingest.ts   #   Ingest プロキシ
│           │   └── collector.ts#   Collector プロキシ
│           └── ws/
│               └── generation.ts#  WebSocket 進捗 (実ポーリング/モック切替)
├── services/
│   ├── agent/                  # エージェンティック RAG (Python/FastAPI)
│   │   └── src/
│   │       ├── rag/            #   LangGraph パイプライン
│   │       │   ├── graph.py    #     StateGraph (4ステップ)
│   │       │   ├── decomposer.py#    GPT-5.4 クエリ分解
│   │       │   ├── reranker.py #     GPT-5.4 リランキング
│   │       │   ├── prompt_builder.py# 生成プロンプト構築
│   │       │   └── llm.py      #     OpenAI ユーティリティ
│   │       ├── retrieval/      #   Qdrant ハイブリッド検索
│   │       └── routes/         #   API ルート
│   ├── ingest/                 # データ取込パイプライン (Python/FastAPI)
│   │   └── src/
│   │       ├── embedding/      #   CLIP ViT-B/32 エンコーダー
│   │       ├── pipeline/       #   Ingest パイプライン
│   │       └── routes/         #   API ルート
│   ├── generation/             # 画像生成エンジン (Python/FastAPI)
│   │   └── src/
│   │       ├── clients/
│   │       │   ├── fal_client.py#    Fal.ai FLUX.2 Pro (httpx async)
│   │       │   └── storage.py  #    MinIO アップロード (aioboto3)
│   │       ├── router/
│   │       │   └── model_router.py# ModelRouter + cloud reroute
│   │       └── routes/
│   │           └── generate.py #    生成エンドポイント + ジョブ管理
│   ├── collector/              # デザイン収集 (Python/FastAPI + Playwright)
│   │   └── src/
│   │       ├── scrapers/       #   サイト別スクレイパー
│   │       ├── datasets/       #   HuggingFace 統合
│   │       ├── job_manager.py  #   ジョブ管理
│   │       ├── main.py         #   FastAPI サーバー
│   │       └── cli.py          #   CLI エントリーポイント
│   └── gpu_arbiter/            # GPU メモリアービター (Python/FastAPI)
│       └── src/
│           ├── arbiter.py      #   セマフォベース排他制御
│           ├── job_queue.py    #   Redis Stream ジョブキュー
│           ├── dlq.py          #   Dead Letter Queue + リトライ
│           ├── watchdog.py     #   クラッシュ検知 + 自動復旧
│           ├── fallback.py     #   クラウドフォールバック
│           └── routes/
│               └── jobs.py     #   API ルート (実接続済み)
├── scripts/
│   ├── start-all.bat           # 全サービス一括起動 (7サービス)
│   ├── start-dev.bat           # 開発用（API + Web）
│   ├── start-api.bat           # API Gateway 単体
│   ├── start-web.bat           # Next.js 単体
│   ├── start-ingest.bat        # Ingest 単体
│   ├── start-generation.bat    # Generation 単体
│   ├── start-arbiter.bat       # GPU Arbiter 単体
│   └── start-collector.bat     # Collector CLI
├── infra/
│   ├── docker-compose.yml      # ローカル開発インフラ
│   └── docker-compose.prod.yml # 本番用
├── docs/
│   └── USER_GUIDE.md           # ユーザーガイド
├── .env.example                # 環境変数テンプレート
└── README.md
```

## Environment Variables

`.env.example` をコピーして `.env` を作成し、必要な値を設定してください。

| 変数 | 説明 | デフォルト |
|------|------|-----------|
| `GPU_MODE` | GPU 動作モード (`local` / `cloud` / `hybrid`) | `hybrid` |
| `OPENAI_API_KEY` | OpenAI API キー（GPT-5.4 オーケストレーター） | -- |
| `OPENAI_MODEL` | 使用する OpenAI モデル | `gpt-5.4` |
| `FAL_AI_API_KEY` | Fal.ai API キー（FLUX.2 Pro クラウド生成） | -- |
| `QDRANT_URL` | Qdrant サーバー URL | `http://localhost:6333` |
| `REDIS_URL` | Redis URL | `redis://localhost:6379` |
| `MINIO_ENDPOINT` | MinIO エンドポイント | `localhost:9000` |
| `UNSPLASH_ACCESS_KEY` | Unsplash API キー（Collector 用） | -- |
| `MOCK_API` | `true` でモックモード起動 | `false` |
| `NEXT_PUBLIC_API_URL` | フロントエンドからの API URL | `http://localhost:4000` |

全変数の一覧は `.env.example` を参照してください。

## License

Private - Personal use
