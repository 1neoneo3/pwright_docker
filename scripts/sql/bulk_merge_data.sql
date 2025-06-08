-- 一括MERGE処理用SQL
-- 一時テーブルからメインテーブルへの一括UPSERT処理

MERGE `{project_id}.{dataset_id}.{table_id}` AS target
USING `{temp_table_id}` AS source
ON target.app_id = source.app_id 
   AND target.scrape_date = source.scrape_date
WHEN MATCHED THEN
  UPDATE SET
    title_name = source.title_name,
    current_followers = source.current_followers,
    positive_reviews = source.positive_reviews,
    negative_reviews = source.negative_reviews,
    owner_estimation = source.owner_estimation,
    scraped_at = source.scraped_at
WHEN NOT MATCHED THEN
  INSERT (app_id, title_name, current_followers, positive_reviews, negative_reviews, owner_estimation, scraped_at, scrape_date)
  VALUES (source.app_id, source.title_name, source.current_followers, source.positive_reviews, source.negative_reviews, source.owner_estimation, source.scraped_at, source.scrape_date)