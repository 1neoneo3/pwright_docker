# Playwright Docker Scraper for Steam

Dockerコンテナ化されたPlaywrightを使用してSteamゲーム情報をスクレイピングするツールです。

## 機能

- Steamゲームのfollower数などの情報を自動収集
- PlaywrightとChromiumを使用した堅牢なスクレイピング
- Docker環境でのクロスプラットフォーム実行
- Google Cloud Run Jobsでの自動スケジュール実行
- Cloud Storageへのデータ保存機能

## ローカル環境での実行方法

### 前提条件

- Docker
- Docker Compose
- Git

### セットアップ

1. リポジトリをクローン

```bash
git clone <repository-url>
cd pwright_docker
```

2. Dockerイメージをビルド

```bash
docker-compose build
```

3. スクリプトの実行

```bash
docker-compose run app python scripts/main.py
```

または開発モードでの実行:

```bash
docker-compose -f docker-compose.dev.yml up
```

## Google Cloud Run Jobの設定

このプロジェクトはGoogle Cloud Run Jobとして実行することができます。

### Cloud Run Jobのセットアップ

以下のスクリプトを使用してCloud Run Jobの環境を構築できます：

```bash
# 実行権限を付与
chmod +x scripts/cloud_run_setup.sh

# セットアップスクリプトを実行
./scripts/cloud_run_setup.sh
```

このスクリプトは以下の処理を行います：

1. 必要なGoogle Cloud APIの有効化
2. サービスアカウントの作成と権限設定
3. Artifact Registryリポジトリの作成
4. Dockerイメージのビルドとプッシュ
5. Cloud Storageバケットの作成
6. Cloud Run Jobの作成
7. Cloud Schedulerによる定期実行の設定

### 手動実行

セットアップ後、以下のコマンドでジョブを手動実行できます：

```bash
gcloud run jobs execute steam-scraper-job --region=asia-northeast1 --project=capable-blend-244100
```

### 環境変数

Cloud Run Jobでは以下の環境変数を設定しています：

- `ENVIRONMENT`: 実行環境 (`production`)
- `PYTHONUNBUFFERED`: Pythonの出力バッファリングを無効化 (`1`)
- `GCS_BUCKET_NAME`: 結果を保存するCloud Storageバケット名
- `MAX_APPS`: 取得するSteam AppIDの最大数
- `PROCESS_COUNT`: 実際に処理するAppIDの数

## プロジェクト構成

```
pwright_docker/
├── Dockerfile            # マルチステージビルドを使用したDockerfile
├── Makefile              # 便利なコマンド集
├── README.md             # このファイル
├── docker-compose.dev.yml # 開発用のDocker Compose設定
├── docker-compose.yml    # 本番用のDocker Compose設定
├── docs/                 # プロジェクト関連ドキュメント
│   └── requirements/     # 要件と仕様書
├── pyproject.toml        # Pythonプロジェクト設定
├── requirements.txt      # 依存パッケージ一覧
└── scripts/              # Pythonスクリプト
    ├── cloud_run_setup.sh # Cloud Run Job設定スクリプト
    ├── main.py           # メインスクレイパースクリプト
    ├── scraper_core.py   # スクレイピングロジック
    └── sql/              # SQLファイル
```

## モニタリングとログ

Cloud Run Job実行時のログはCloud Loggingで確認できます：

```bash
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=steam-scraper-job" \
  --limit=10 \
  --format=json \
  --project=capable-blend-244100
```

収集したデータはCloud Storageで確認できます：

```bash
gsutil ls -l gs://capable-blend-244100-scraper-results/
```