# DesignGenerator ユーザーガイド

現在実装済みの機能を使い始めるためのガイドです。

---

## 目次

1. [起動方法](#起動方法)
2. [ホーム画面](#ホーム画面)
3. [デザイン生成 (/generator)](#デザイン生成)
4. [画像アップロード (/upload)](#画像アップロード)
5. [デザイン収集 (/collector)](#デザイン収集)
6. [動作モード](#動作モード)
7. [環境変数リファレンス](#環境変数リファレンス)
8. [サービス構成](#サービス構成)
9. [トラブルシューティング](#トラブルシューティング)

---

## 起動方法

### ワンクリック起動（推奨）

```
scripts\start-all.bat
```

ダブルクリックするだけで、必要なサービスが全て起動し、ブラウザが自動で開きます。

- Docker がインストールされている場合 → **FULL モード**（全 7 サービス起動）
- Docker が無い場合 → **MOCK モード**（API + Web のみ、モックデータで動作）

### 個別起動

用途に応じて個別に起動することもできます。

| スクリプト | 用途 | ポート |
|-----------|------|--------|
| `scripts\start-all.bat` | 全サービス一括起動 + ブラウザ自動オープン | -- |
| `scripts\start-dev.bat` | API + Web（開発用） | 4000, 3000 |
| `scripts\start-api.bat` | API Gateway のみ | 4000 |
| `scripts\start-web.bat` | フロントエンドのみ | 3000 |
| `scripts\start-ingest.bat` | Ingest サービスのみ | 8200 |
| `scripts\start-generation.bat` | Generation サービスのみ | 8100 |
| `scripts\start-arbiter.bat` | GPU Arbiter のみ | 8300 |
| `scripts\start-collector.bat` | Collector CLI | -- |

---

## ホーム画面

ブラウザで http://localhost:3000 を開くと、ホーム画面が表示されます。

3つの機能にアクセスできます：

- **Generator を開く** → デザイン生成
- **画像をアップロード** → 手動での画像登録
- **デザイン収集** → 外部サイトからの自動収集

---

## デザイン生成

**URL:** http://localhost:3000/generator

AIにデザインを生成させる機能です。

### 使い方

1. **プロンプトを入力**
   - 日本語でも英語でも入力できます
   - 例: 「ネオンカラーを使ったモダンなログイン画面のUI」
   - 例: 「ミニマルなグラデーションバナー、白背景」

2. **「生成する」ボタンをクリック**

3. **詳細オプション（任意）**
   - 「▼ 詳細オプション」をクリックして展開
   - **解像度プリセット**: Full HD (1920x1080) / Square (1080x1080) / Story (1080x1920) / OGP (1200x628) / 4:3 (800x600) から選択、または自由入力
   - **参照モード**: ハイブリッド / スタイルのみ / レイアウトのみ
   - **ブランド**: ブランド名を指定すると、関連するリファレンスが優先される

4. **進捗を確認**
   - Job ID が表示される
   - WebSocket 経由でリアルタイムに進捗がストリーミングされる
   - ステータス遷移:

     ```
     queued → decomposing → searching → reranking → building_prompt → generating → uploading → completed
     ```

5. **結果を確認**
   - 完了すると生成結果が画面下部に表示される
   - **MOCK** バッジ: Fal.ai API キー未設定時のダミー画像
   - **fal_ai** バッジ: Fal.ai FLUX.2 Pro で実際に生成された画像
   - 「原寸大で開く」リンクで原寸画像を別タブで確認可能

### E2E パイプライン（FULL モード時）

生成リクエストを送ると、以下のパイプラインが各サービス間を横断して実行されます：

```
Frontend → API Gateway → Agent Service → Generation Service → Fal.ai → MinIO
              ↑ WebSocket polling                    ↑
              └────── 進捗通知 ──────────────────────┘
```

1. **クエリ分解** (Agent :8000) -- GPT-5.4 がプロンプトからデザイン要素（カテゴリ、スタイル、カラー、レイアウト）を抽出
2. **ハイブリッド検索** (Agent → Qdrant) -- テキスト＋ビジュアル両方のベクトルで検索
3. **リランキング** (Agent) -- GPT-5.4 が検索結果の関連度をスコアリング
4. **プロンプト構築** (Agent) -- リファレンス情報を踏まえた画像生成用プロンプトを構築
5. **モデルルーティング** (Generation :8100) -- ModelRouter がプロンプト属性から最適プロバイダーを選択
6. **画像生成** (Generation → Fal.ai) -- FLUX.2 Pro API で画像を生成
7. **画像保存** (Generation → MinIO) -- 生成画像を MinIO に保存し、署名付き URL を返却

### API キーによる動作の違い

| キー | 設定あり | 設定なし |
|------|---------|---------|
| `OPENAI_API_KEY` | GPT-5.4 でクエリ分解・リランキング・プロンプト構築 | ルールベースのモック処理（パイプラインは正常動作） |
| `FAL_AI_API_KEY` | Fal.ai FLUX.2 Pro で実画像を生成 | WARNING ログ + モックプレースホルダー画像 |

両方未設定でもパイプライン全体は動作します（モック画像が返される）。

---

## 画像アップロード

**URL:** http://localhost:3000/upload

手持ちのデザイン画像をシステムに登録する機能です。

### 使い方

1. **カテゴリを選択**
   - バナー / UI / アイコン / イラスト / 写真 / その他

2. **画像をアップロード**
   - ドラッグ＆ドロップ、またはクリックしてファイルを選択
   - PNG, JPG, WebP に対応
   - 複数ファイルを同時にアップロード可能

3. **結果を確認**
   - 各ファイルのアップロード状態（アップロード中 / 完了 / エラー）が表示される
   - 完了するとアセット ID が表示される

### 登録されたデータ

アップロードされた画像は以下の流れで処理されます：

1. CLIP モデル（sentence-transformers/clip-ViT-B-32）でベクトル化
2. Qdrant の `design_assets` コレクションに visual + textual ベクトルとして登録
3. メタデータ（カテゴリ、ライセンスタイプ、ファイル名）も一緒に保存

登録後は Generator の検索でリファレンスとして使われるようになります。

> **必要条件:** Docker で Qdrant と Redis が起動していること（FULL モード）

---

## デザイン収集

**URL:** http://localhost:3000/collector

外部のデザインギャラリーサイトや HuggingFace データセットから、リファレンス画像を自動収集する機能です。

### 使い方

1. **ソースを選択**

   | ソース | 説明 | 必要なもの |
   |--------|------|-----------|
   | Dribbble | UI/Web デザインギャラリー | Playwright（自動インストール済み） |
   | Behance | クリエイティブプロジェクト | Playwright |
   | Pinterest | デザインインスピレーション | Playwright |
   | Unsplash | 高品質ストック写真 | `UNSPLASH_ACCESS_KEY` 環境変数 |
   | HuggingFace | ML データセットから画像取得 | -- |

2. **検索クエリを入力**
   - Dribbble / Behance / Pinterest / Unsplash の場合: 検索キーワード（例: "web design", "UI minimal"）
   - HuggingFace の場合: データセット名（例: "user/dataset-name"）

3. **オプションを設定**
   - **最大ページ数**: スクレイピングするページ数（Playwright 系のみ）
   - **最大画像数**: 収集する画像の上限
   - **自動的に Ingest サービスに投入**: ON にすると、収集した画像を即座にベクトル DB に登録

4. **「収集を開始」ボタンをクリック**

5. **進捗を確認**
   - プログレスバーと収集枚数がリアルタイムで更新される
   - 完了後はサムネイルギャラリーで収集結果を確認できる

6. **ジョブ履歴**
   - 左サイドバーに過去のジョブ一覧が表示される
   - クリックすると詳細と収集画像を再確認できる

### 「自動 Ingest」について

- **OFF（デフォルト）**: 画像はローカルの `data/collected/` フォルダに保存されるだけ
- **ON**: 収集後に自動で Ingest サービスに送信 → Qdrant に登録 → Generator の検索で利用可能に

> **注意:** 自動 Ingest を使うには、Docker で Qdrant + Redis が起動し、Ingest サービスが動いている必要があります（FULL モード）

### CLI からの利用

Web UI の代わりにコマンドラインからも使えます。

```
scripts\start-collector.bat
```

```bash
# Dribbble からスクレイピング
python -m src.cli scrape dribbble -q "web design" -v

# 全ソースからまとめて収集
python -m src.cli scrape-all -q "UI design"

# HuggingFace データセットからダウンロード
python -m src.cli hf-download user/dataset --max 200

# 収集 + 自動 Ingest
python -m src.cli scrape dribbble -q "web design" --ingest
```

---

## 動作モード

### MOCK モード

Docker がインストールされていない場合に自動で適用されます。

- API Gateway がモックデータを返す
- 検索結果はダミーデータ
- 画像生成はダミーのプレースホルダー画像を返却
- 画像アップロードは動作しない
- バックエンドサービス不要

**用途:** フロントエンドの動作確認、UI のテスト

### FULL モード

Docker で以下のインフラが起動している場合に適用されます。

**インフラコンテナ (Docker Compose):**

| サービス | URL | 用途 |
|---------|-----|------|
| Qdrant | http://localhost:6333 | ベクトル検索 |
| Redis | http://localhost:6379 | キャッシュ + GPU ジョブキュー |
| PostgreSQL | localhost:5432 | リレーショナルデータ（将来用） |
| MinIO | http://localhost:9000 | 生成画像のオブジェクトストレージ |
| MinIO Console | http://localhost:9001 | MinIO 管理画面 (admin/minioadmin) |
| RedisInsight | http://localhost:8001 | Redis 管理画面 |

**アプリケーションサービス:**

| サービス | ポート | 機能 |
|---------|--------|------|
| Web | 3000 | Next.js フロントエンド |
| API Gateway | 4000 | 全サービスへのプロキシ + WebSocket 進捗ストリーミング |
| Agent | 8000 | RAG パイプライン（クエリ分解 + 検索 + リランキング + プロンプト構築） |
| Generation | 8100 | 画像生成エンジン（ModelRouter + Fal.ai FLUX.2 Pro + MinIO 保存） |
| Ingest | 8200 | 画像ベクトル化（CLIP ViT-B/32）+ Qdrant 登録 |
| GPU Arbiter | 8300 | GPU 排他制御（セマフォ + Redis ジョブキュー + DLQ + Watchdog） |
| Collector | 8400 | デザイン画像収集（Playwright スクレイパー + HuggingFace） |

---

## 環境変数リファレンス

`.env.example` をコピーして `.env` を作成し、必要な値を設定してください。

### 必須ではないが推奨

| 変数 | 説明 | 未設定時の動作 |
|------|------|--------------|
| `OPENAI_API_KEY` | GPT-5.4 でクエリ分解・リランキング | ルールベースのフォールバック |
| `FAL_AI_API_KEY` | Fal.ai FLUX.2 Pro で画像生成 | モックプレースホルダー画像 |
| `UNSPLASH_ACCESS_KEY` | Unsplash API で写真収集 | Unsplash ソースが使えない |

### インフラ設定（デフォルトで動作）

| 変数 | デフォルト |
|------|-----------|
| `GPU_MODE` | `hybrid` (`cloud` / `local` / `hybrid`) |
| `QDRANT_URL` | `http://localhost:6333` |
| `REDIS_URL` | `redis://localhost:6379` |
| `MINIO_ENDPOINT` | `localhost:9000` |
| `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | `minioadmin` / `minioadmin` |
| `MOCK_API` | `false` |
| `NEXT_PUBLIC_API_URL` | `http://localhost:4000` |

全変数の一覧は `.env.example` を参照してください。

---

## サービス構成

### データフロー

```
[ユーザー] → [Web :3000] → [API Gateway :4000]
                                    │
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
              [Agent :8000]   [Ingest :8200]  [Collector :8400]
                    │               │               │
                    ▼               │               │
           [Generation :8100]       │               │
                    │               │               │
                    ▼               ▼               ▼
              [Fal.ai API]    [Qdrant :6333]  [Playwright]
                    │               │
                    ▼               │
              [MinIO :9000]         │
                    │               │
                    └───────────────┘
                            │
                    [Redis :6379]
                            │
                  [GPU Arbiter :8300]
                  (Watchdog + DLQ)
```

### ライセンスタグ

収集・アップロードされた画像には、ライセンスタイプが自動的にタグ付けされます。

| タグ | 意味 | ソース |
|------|------|--------|
| `internal` | 自分でアップロードした画像 | /upload |
| `unsplash_license` | Unsplash 経由の画像 | Collector (Unsplash) |
| `dataset_license` | HuggingFace データセット | Collector (HuggingFace) |
| `copyrighted_reference` | 外部ギャラリーから収集 | Collector (Dribbble/Behance/Pinterest) |

これらのタグは Qdrant のメタデータとして保存され、検索時のフィルタリングに使用できます。

---

## トラブルシューティング

### 「WebSocket error」と表示される

- API Gateway（ポート 4000）が起動しているか確認してください
- `scripts\start-all.bat` で全サービスを再起動してください

### 生成結果がずっとモック画像になる

- `.env` の `FAL_AI_API_KEY` を確認してください
- Generation Service のコンソールに `[WARNING] FAL_AI_API_KEY is missing` と出ていれば API キー未設定です
- Fal.ai のアカウント作成: https://fal.ai/

### 生成が「generating」のまま進まない

- Generation Service（ポート 8100）が起動しているか確認してください
- Agent Service のコンソールに `Generation Service unavailable` と出ていれば Generation Service に到達できていません
- `scripts\start-generation.bat` で個別に起動して確認してください

### 画像アップロードが失敗する

- Docker が起動しているか確認（`docker ps` でコンテナ一覧を確認）
- Ingest サービス（ポート 8200）が起動しているか確認
- Qdrant コンテナが正常に動作しているか確認

### Collector のスクレイピングが失敗する

- Playwright のブラウザがインストールされているか確認:

  ```
  cd services\collector
  .venv\Scripts\python.exe -m playwright install chromium
  ```

- 一部のサイト（Pinterest 等）はレート制限が厳しい場合があります。`最大ページ数` と `最大画像数` を小さくしてお試しください

### サービスが起動しない

- 各サービスのポートが他のプロセスで使われていないか確認
- `.env` ファイルが存在するか確認（`.env.example` からコピー）
- Python の仮想環境が作成されているか確認（各 services/ ディレクトリに `.venv` があるか）

### GPU Arbiter が「Redis unavailable」と出る

- Docker で Redis が起動しているか確認 (`docker ps | findstr redis`)
- GPU Arbiter は Redis 未接続でも degraded mode で起動します（GPU ジョブキューは動作しない）

### Qdrant バージョン警告が出る

- Docker の Qdrant イメージ（v1.13.2）と Python クライアント（v1.14.x）は互換範囲内です
- 警告が出ても動作に問題はありません

### MinIO に画像が保存されない

- Docker で MinIO が起動しているか確認 (`docker ps | findstr minio`)
- MinIO Console (http://localhost:9001) にアクセスして `generated-outputs` バケットを確認
- Generation Service のコンソールに `[STORAGE] MinIO is unavailable` と出ている場合、Fal.ai の直接 URL がフォールバックとして使われます
