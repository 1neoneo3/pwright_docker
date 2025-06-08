-- 最新データのみを表示するビューを作成
-- 同一日・同一AppIDで重複がある場合は最新の scraped_at を使用

CREATE OR REPLACE VIEW `capable-blend-244100.steam_data.steam_app_metrics_latest` AS
SELECT 
  app_id,
  title_name,
  current_followers,
  positive_reviews,
  negative_reviews,
  owner_estimation,
  scraped_at,
  scrape_date,
  -- 計算フィールド
  (positive_reviews + negative_reviews) as total_reviews,
  CASE 
    WHEN (positive_reviews + negative_reviews) > 0 
    THEN ROUND((positive_reviews / (positive_reviews + negative_reviews)) * 100, 2)
    ELSE NULL
  END as positive_review_percentage
FROM (
  SELECT 
    *,
    ROW_NUMBER() OVER (
      PARTITION BY app_id, scrape_date 
      ORDER BY scraped_at DESC
    ) as rn
  FROM `capable-blend-244100.steam_data.steam_app_metrics`
) 
WHERE rn = 1;