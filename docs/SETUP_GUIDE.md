# DesignGenerator セットアップガイド

Windows 環境でゼロから開発環境を構築する手順です。

---

## 目次

1. [前提ソフトウェアのインストール](#1-前提ソフトウェアのインストール)
2. [リポジトリのクローン](#2-リポジトリのクローン)
3. [TypeScript 依存関係のインストール](#3-typescript-依存関係のインストール)
4. [Python 依存関係のインストール](#4-python-依存関係のインストール)
5. [環境変数の設定](#5-環境変数の設定)
6. [Docker インフラの起動](#6-docker-インフラの起動)
7. [Playwright ブラウザのインストール](#7-playwright-ブラウザのインストール)
8. [起動と動作確認](#8-起動と動作確認)
9. [API キーの取得方法](#9-api-キーの取得方法)

---

## 1. 前提ソフトウェアのインストール

以下のソフトウェアが必要です。

### 必須

| ソフトウェア | バージョン | インストール方法 |
|-------------|-----------|----------------|
| **Git** | 最新版 | https://git-scm.com/download/win |
| **Python** | 3.12 以上 | Microsoft Store または https://www.python.org/ |
| **Bun** | 1.2 以上 | PowerShell: `npm install -g bun` |
| **uv** | 最新版 | PowerShell: `pip install uv` |

### 推奨（FULL モードに必要）

| ソフトウェア | バージョン | インストール方法 |
|-------------|-----------|----------------|
| **Docker Desktop** | 最新版 | https://www.docker.com/products/docker-desktop/ |

> Docker が無くても **MOCK モード** で動作します（フロントエンドの確認が可能）。

### バージョン確認

```powershell
git --version
python --version     # 3.12 以上であること
bun --version        # 1.2 以上であること
python -m uv --version
docker --version     # (任意)
```

---

## 2. リポジトリのクローン

```powershell
git clone https://github.com/your-username/DesignGenerator.git
cd DesignGenerator
```

---

## 3. TypeScript 依存関係のインストール

プロジェクトルートで実行します。

```powershell
bun install
```

これにより `apps/web` (Next.js) と `apps/api` (Hono) の依存関係がインストールされます。

---

## 4. Python 依存関係のインストール

各サービスの仮想環境と依存関係をインストールします。

```powershell
# Agent サービス
cd services\agent
python -m uv sync
cd ..\..

# Ingest サービス
cd services\ingest
python -m uv sync
cd ..\..

# Generation サービス
cd services\generation
python -m uv sync
cd ..\..

# GPU Arbiter
cd services\gpu_arbiter
python -m uv sync
cd ..\..

# Collector サービス
cd services\collector
python -m uv sync
cd ..\..
```

> `uv sync` は各サービスの `pyproject.toml` を読み取り、`.venv` フォルダに仮想環境を自動作成します。

### 一括インストール（コピペ用）

```powershell
$services = @("agent", "ingest", "generation", "gpu_arbiter", "collector")
foreach ($s in $services) {
    Push-Location "services\$s"
    python -m uv sync
    Pop-Location
}
```

---

## 5. 環境変数の設定

`.env.example` をコピーして `.env` を作成します。

```powershell
copy .env.example .env
```

### 最小構成（全て未設定でも MOCK モードで動作）

`.env` の全項目を空のままにしても、システムは MOCK モードで起動します。

### 推奨設定

以下を設定すると、より多くの機能が利用できます。

```ini
# GPT-5.4 によるクエリ分解・リランキングを有効化
OPENAI_API_KEY=sk-your-key-here

# Fal.ai FLUX.2 Pro による実画像生成を有効化
FAL_AI_API_KEY=your-fal-key-here
```

設定しない場合でも、それぞれルールベースのフォールバックやモック画像で代替されるため、パイプライン自体は正常に動作します。

---

## 6. Docker インフラの起動

Docker Desktop を起動した状態で、以下を実行します。

```powershell
docker compose -f infra\docker-compose.yml up -d
```

以下の 4 つのコンテナが起動します。

| コンテナ | ポート | 確認方法 |
|---------|--------|---------|
| **Qdrant** | 6333, 6334 | http://localhost:6333/dashboard |
| **Redis** | 6379, 8001 | http://localhost:8001 (RedisInsight) |
| **PostgreSQL** | 5432 | -- |
| **MinIO** | 9000, 9001 | http://localhost:9001 (Console, admin: `minioadmin`/`minioadmin`) |

### 起動確認

```powershell
docker ps
```

4 つのコンテナ (`qdrant`, `redis`, `postgres`, `minio`) + 初期化コンテナ (`minio-init`) が表示されればOKです。

> MinIO 初期化コンテナは `design-assets` と `generated-outputs` バケットを自動作成した後、自動で終了します。

### Docker が無い場合

Docker を使わずに MOCK モードで起動できます。`start-all.bat` が Docker の有無を自動判定します。

---

## 7. Playwright ブラウザのインストール

Collector サービス（デザイン収集）を使う場合のみ必要です。

```powershell
cd services\collector
.venv\Scripts\python.exe -m playwright install chromium
cd ..\..
```

> 約 200MB のダウンロードが発生します。初回のみ実行すれば以降は不要です。

---

## 8. 起動と動作確認

### ワンクリック起動

```powershell
.\scripts\start-all.bat
```

ダブルクリックでも実行可能です。全サービスが順次起動し、ブラウザが自動で http://localhost:3000 を開きます。

### 起動順序

`start-all.bat` は以下の順序でサービスを起動します：

```
1. Docker インフラ (Qdrant, Redis, PostgreSQL, MinIO)
2. Ingest Service     (:8200)
3. Generation Service (:8100)
4. GPU Arbiter        (:8300)
5. Agent Service      (:8000)
6. Collector Service  (:8400)
7. API Gateway        (:4000) + Web (:3000)
→ ブラウザ自動オープン
```

### 動作確認チェックリスト

1. http://localhost:3000 が開く → ホーム画面が表示される
2. 「Generator を開く」をクリック → Generator ページに遷移
3. プロンプトに「test」と入力して「生成する」をクリック → プログレスバーが動く
4. 完了すると画像が表示される（MOCK バッジ付き = 正常）

### ヘルスチェック

各サービスが正常に起動しているか確認できます。

```powershell
# API Gateway
curl http://localhost:4000/health

# Agent
curl http://localhost:8000/health

# Generation
curl http://localhost:8100/health

# GPU Arbiter (GPU ステータス付き)
curl http://localhost:8300/health

# Ingest
curl http://localhost:8200/health

# Collector
curl http://localhost:8400/health
```

---

## 9. API キーの取得方法

### OpenAI API キー（推奨）

GPT-5.4 によるクエリ分解・リランキング・プロンプト構築に使用します。

1. https://platform.openai.com/ にアクセス
2. アカウント作成 / ログイン
3. API Keys → 「Create new secret key」
4. `.env` の `OPENAI_API_KEY` に設定

### Fal.ai API キー（推奨）

FLUX.2 Pro による実画像生成に使用します。

1. https://fal.ai/ にアクセス
2. アカウント作成 / ログイン
3. Dashboard → API Keys → 「Create Key」
4. `.env` の `FAL_AI_API_KEY` に設定

### Unsplash API キー（任意）

Collector で Unsplash からの写真収集に使用します。

1. https://unsplash.com/developers にアクセス
2. アカウント作成 / ログイン
3. 「Your apps」→「New Application」
4. Access Key を `.env` の `UNSPLASH_ACCESS_KEY` に設定

---

## よくある質問

### Q: 最小構成で何が動きますか？

Python + Bun のみインストールし、API キーを一切設定しなくても以下が動作します：

- MOCK モード: フロントエンド（Generator / Upload / Collector ページ）の表示確認
- API Gateway のモックレスポンス
- WebSocket の進捗ストリーミング（ダミーデータ）

### Q: Docker を入れたら何が変わりますか？

FULL モードになり、以下が利用可能になります：

- Qdrant でのベクトル検索（画像アップロード → 検索 → リファレンス活用）
- Redis でのキャッシュ + GPU ジョブキュー
- MinIO への生成画像保存
- 全 7 サービスの完全な E2E パイプライン

### Q: OpenAI API キーは必須ですか？

いいえ。未設定でもルールベースのフォールバックで動作します。ただし、GPT-5.4 による高品質なクエリ分解やリランキングは無効になります。

### Q: Fal.ai API キーは必須ですか？

いいえ。未設定の場合、Generation Service のコンソールに WARNING が表示され、モックのプレースホルダー画像が返されます。実際の画像生成を行いたい場合のみ設定してください。

### Q: ポートが競合して起動できません

以下のコマンドで、使用中のポートを確認できます：

```powershell
netstat -ano | findstr :3000
netstat -ano | findstr :4000
netstat -ano | findstr :8000
```

該当プロセスを終了するか、`.env` でポート番号を変更してください。
