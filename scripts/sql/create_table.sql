-- SteamDB データ保存用 BigQuery テーブル設計

CREATE OR REPLACE TABLE `capable-blend-244100.steam_data.steam_app_metrics` (
  -- 基本情報
  app_id INT64,
  title_name STRING,
  
  -- フォロワー・レビュー数
  current_followers INT64,
  positive_reviews INT64,
  negative_reviews INT64,
  
  -- オーナー推定数
  owner_estimation INT64,
  
  -- メタデータ
  scraped_at TIMESTAMP,
  scrape_date DATE
)
PARTITION BY scrape_date
CLUSTER BY app_id, scrape_date
OPTIONS(
  description="Steam アプリケーションの日次メトリクス（フォロワー数、レビュー数、オーナー推定数）",
  labels=[("environment", "production"), ("data_source", "steamdb")]
);

-- データ保持ポリシー（オプション）
-- ALTER TABLE `capable-blend-244100.steam_data.steam_app_metrics`
-- SET OPTIONS (
--   partition_expiration_days=365  -- 1年後にパーティションを自動削除
-- );