-- 分析用クエリ集

-- 1. 日別のトップゲーム（フォロワー数順）
SELECT 
    title_name,
    current_followers,
    positive_reviews,
    negative_reviews,
    owner_estimation,
    scrape_date
FROM `capable-blend-244100.steam_data.steam_app_metrics` 
WHERE scrape_date = CURRENT_DATE('UTC')
    AND current_followers IS NOT NULL
ORDER BY current_followers DESC;

-- 2. レビュー満足度の高いゲーム
SELECT 
    title_name,
    positive_reviews,
    negative_reviews,
    ROUND(positive_reviews / (positive_reviews + negative_reviews) * 100, 2) as satisfaction_rate,
    (positive_reviews + negative_reviews) as total_reviews
FROM `capable-blend-244100.steam_data.steam_app_metrics` 
WHERE scrape_date = CURRENT_DATE('UTC')
    AND positive_reviews IS NOT NULL 
    AND negative_reviews IS NOT NULL
    AND (positive_reviews + negative_reviews) > 1000
ORDER BY satisfaction_rate DESC;

-- 3. フォロワー数とオーナー推定数の比較
SELECT 
    title_name,
    current_followers,
    owner_estimation,
    ROUND(SAFE_DIVIDE(owner_estimation, current_followers), 2) as owner_follower_ratio
FROM `capable-blend-244100.steam_data.steam_app_metrics` 
WHERE scrape_date = CURRENT_DATE('UTC')
    AND current_followers IS NOT NULL 
    AND owner_estimation IS NOT NULL
    AND current_followers > 0
ORDER BY owner_follower_ratio DESC;

-- 4. 時系列での変化（過去7日間）
SELECT 
    app_id,
    title_name,
    scrape_date,
    current_followers,
    LAG(current_followers) OVER (PARTITION BY app_id ORDER BY scrape_date) as previous_followers,
    current_followers - LAG(current_followers) OVER (PARTITION BY app_id ORDER BY scrape_date) as followers_change
FROM `capable-blend-244100.steam_data.steam_app_metrics` 
WHERE scrape_date >= DATE_SUB(CURRENT_DATE('UTC'), INTERVAL 7 DAY)
    AND current_followers IS NOT NULL
ORDER BY app_id, scrape_date DESC;