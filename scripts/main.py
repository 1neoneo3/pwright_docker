import asyncio
import json
import logging
import sys
import time
import aiohttp
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s',
    stream=sys.stdout
)

from datetime import datetime, timezone
from google.cloud import bigquery
from scraper_core import SteamDBScraper

# BigQuery設定
PROJECT_ID = "capable-blend-244100"
DATASET_ID = "steam_data"
TABLE_ID = "steam_app_metrics"

def load_sql_file(filename):
    """SQLファイルを読み込み"""
    sql_path = Path(__file__).parent / "sql" / filename
    try:
        with open(sql_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        logging.error(f"SQLファイルが見つかりません: {sql_path}")
        return None

def delete_today_data():
    """本日のデータを削除（UTC基準）"""
    try:
        client = bigquery.Client(project=PROJECT_ID)
        delete_sql = load_sql_file("delete_today_data.sql")
        
        if delete_sql:
            job = client.query(delete_sql)
            job.result()  # 完了まで待機
            logging.info("本日のデータを削除しました（UTC基準）")
            return True
        else:
            logging.error("削除SQLの読み込みに失敗しました")
            return False
            
    except Exception as e:
        logging.error(f"データ削除中にエラー: {e}", exc_info=True)
        return False

def save_data_to_csv(data_records):
    """データを一時CSVファイルに保存"""
    try:
        import csv
        csv_file_path = "/tmp/steam_data_temp.csv"
        
        # CSVファイルに書き込み
        with open(csv_file_path, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['app_id', 'title_name', 'current_followers', 'positive_reviews', 
                         'negative_reviews', 'owner_estimation', 'scraped_at', 'scrape_date']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for record in data_records:
                # ISO形式の日時文字列をdatetimeオブジェクトに変換
                scraped_at = datetime.fromisoformat(record["取得日時"].replace('Z', '+00:00'))
                scrape_date = scraped_at.date()
                
                writer.writerow({
                    'app_id': record["AppID"],
                    'title_name': record["タイトル名"],
                    'current_followers': record.get("現在のfollower数"),
                    'positive_reviews': record.get("ポジティブレビュー数"),
                    'negative_reviews': record.get("ネガティブレビュー数"),
                    'owner_estimation': record.get("オーナー推定数"),
                    'scraped_at': scraped_at.isoformat(),
                    'scrape_date': scrape_date.isoformat()
                })
        
        logging.info(f"データを一時CSVファイルに保存しました: {csv_file_path} ({len(data_records)}件)")
        return csv_file_path
        
    except Exception as e:
        logging.error(f"CSV保存中にエラー: {e}", exc_info=True)
        return None

def save_to_bigquery(data_records):
    """BigQueryにデータを保存（一括MERGE処理）"""
    try:
        # まずCSVファイルに保存
        csv_file_path = save_data_to_csv(data_records)
        if not csv_file_path:
            return False
            
        client = bigquery.Client(project=PROJECT_ID)
        
        # 一時テーブルにCSVデータをロード
        temp_table_id = f"{PROJECT_ID}.{DATASET_ID}.temp_steam_data_{int(time.time())}"
        
        # CSVからBigQueryへのロード設定
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.CSV,
            skip_leading_rows=1,
            autodetect=False,
            schema=[
                bigquery.SchemaField("app_id", "INTEGER"),
                bigquery.SchemaField("title_name", "STRING"),
                bigquery.SchemaField("current_followers", "INTEGER"),
                bigquery.SchemaField("positive_reviews", "INTEGER"),
                bigquery.SchemaField("negative_reviews", "INTEGER"),
                bigquery.SchemaField("owner_estimation", "INTEGER"),
                bigquery.SchemaField("scraped_at", "TIMESTAMP"),
                bigquery.SchemaField("scrape_date", "DATE"),
            ]
        )
        
        # CSVファイルを一時テーブルにロード
        with open(csv_file_path, "rb") as source_file:
            load_job = client.load_table_from_file(
                source_file, temp_table_id, job_config=job_config
            )
        
        load_job.result()  # ロード完了を待機
        logging.info(f"一時テーブルにデータをロードしました: {temp_table_id}")
        
        # 一括MERGE文をSQLファイルから読み込み
        bulk_merge_sql_template = load_sql_file("bulk_merge_data.sql")
        if not bulk_merge_sql_template:
            logging.error("一括MERGE SQLテンプレートの読み込みに失敗しました")
            return False
        
        # SQLテンプレートにパラメータを埋め込み
        merge_sql = bulk_merge_sql_template.format(
            project_id=PROJECT_ID,
            dataset_id=DATASET_ID,
            table_id=TABLE_ID,
            temp_table_id=temp_table_id
        )
        
        # MERGE文を実行
        logging.info("一括MERGE処理を開始します...")
        merge_job = client.query(merge_sql)
        merge_job.result()  # 完了まで待機
        
        # 処理件数を確認
        rows_affected = merge_job.dml_stats.inserted_row_count + merge_job.dml_stats.updated_row_count
        logging.info(f"MERGE処理完了: 挿入 {merge_job.dml_stats.inserted_row_count}件, 更新 {merge_job.dml_stats.updated_row_count}件, 合計 {rows_affected}件")
        
        # 一時テーブルを削除
        client.delete_table(temp_table_id)
        logging.info(f"一時テーブルを削除しました: {temp_table_id}")
        
        # CSVファイルを削除
        import os
        os.remove(csv_file_path)
        logging.info("一時CSVファイルを削除しました")
        
        logging.info(f"BigQueryに一括MERGE処理で {len(data_records)} 件のレコードを保存しました")
        return True

    except Exception as e:
        error_message = str(e)
        if "streaming buffer" in error_message.lower():
            logging.warning("ストリーミングバッファ制限により一括MERGE処理がスキップされました")
            return True  # ストリーミングバッファスキップは正常動作
        else:
            logging.error(f"BigQuery一括MERGE処理中にエラー: {e}", exc_info=True)
            return False


async def get_steam_appids(max_apps=None):
    """Steam APIからAppIDのリストを取得する"""
    api_url = "https://api.steampowered.com/ISteamApps/GetAppList/v2/"
    appids = []
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url) as response:
                response.raise_for_status()  # エラーがあれば例外を発生
                data = await response.json()
                if data and 'applist' in data and 'apps' in data['applist']:
                    # appidが数値で、nameが空でないもののみを対象とする (より堅牢なフィルタリング)
                    valid_apps = [
                        app_info['appid'] 
                        for app_info in data['applist']['apps'] 
                        if isinstance(app_info.get('appid'), int) and app_info.get('name', '').strip()
                    ]
                    if max_apps:
                        appids = valid_apps[:max_apps]
                    else:
                        appids = valid_apps
                    logging.info(f"Steam APIから {len(appids)} 件の有効なAppIDを取得しました。")
                else:
                    logging.error("Steam APIからのレスポンス形式が不正か、appリストが空です。")
    except aiohttp.ClientError as e:
        logging.error(f"Steam APIへの接続中にエラーが発生しました: {e}", exc_info=True)
    except json.JSONDecodeError as e:
        logging.error(f"Steam APIレスポンスのJSONデコード中にエラー: {e}", exc_info=True)
    except Exception as e:
        logging.error(f"Steam AppID取得中に予期せぬエラー: {e}", exc_info=True)
    return appids


async def main():
    main_processing_start_time = time.perf_counter()

    appids_to_scrape = await get_steam_appids(max_apps=1000)
    if not appids_to_scrape:
        logging.error("処理対象のAppIDが取得できませんでした。スクリプトを終了します。")
        return

    selected_appids = [100, 130]
    logging.info(f"処理対象のAppID (SQLファイルベース一括MERGE処理テスト): {selected_appids}")

    scraper = SteamDBScraper()
    successful_extractions, collected_data = await scraper.scrape_multiple_apps(selected_appids)

    if collected_data:
        logging.info(f"BigQueryに {len(collected_data)} 件のデータを保存します...")
        bigquery_success = save_to_bigquery(collected_data)
        if bigquery_success:
            logging.info("BigQueryへのデータ保存が正常に完了しました")
        else:
            logging.error("BigQueryへのデータ保存に失敗しました")
    else:
        logging.warning("保存するデータがありません")

    main_processing_end_time = time.perf_counter()
    total_main_duration = main_processing_end_time - main_processing_start_time
    logging.info(f"全AppIDの処理完了。成功件数: {successful_extractions}/{len(selected_appids)}")
    logging.info(f"main関数全体の実行時間: {total_main_duration:.2f}秒")


if __name__ == "__main__":
    program_start_time = time.perf_counter()
    logging.info("SteamDB Playwrightスクレイパーを開始します。")
    
    asyncio.run(main())
    
    logging.info("SteamDB Playwrightスクレイパーを終了します。")