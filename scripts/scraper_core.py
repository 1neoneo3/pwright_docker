# scripts/scraper_core.py
import asyncio
import json
import logging
import random
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timezone
from playwright.async_api import async_playwright
from playwright_stealth import stealth_async

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:131.0) Gecko/20100101 Firefox/131.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:132.0) Gecko/20100101 Firefox/132.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1.1 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
]

def parse_number_with_suffix(text):
    if not text:
        return None
    match = re.search(r'~?([\d.,]+)\s*([MKBmkb]?)', text.strip())
    if not match:
        return None
    number_str = match.group(1).replace(',', '')
    suffix = match.group(2).lower()
    try:
        number = float(number_str)
    except ValueError:
        return None
    if suffix == 'k':
        number *= 1_000
    elif suffix == 'm':
        number *= 1_000_000
    elif suffix == 'b':
        number *= 1_000_000_000
    return int(number)

def parse_html_content(html_content, appid):
    soup = BeautifulSoup(html_content, 'html.parser')
    data = {"AppID": appid, "取得日時": datetime.now(timezone.utc).isoformat()}
    
    title_tag = soup.find('h1', itemprop='name')
    data["タイトル名"] = title_tag.get_text(strip=True) if title_tag else "N/A"

    followers_text = "N/A"
    try:
        store_data_header = soup.find('h3', string=lambda t: t and 'store data' in t.lower())
        if store_data_header:
            ul_tag = store_data_header.find_next_sibling('ul')
            if ul_tag:
                followers_li = ul_tag.find('li')
                if followers_li:
                    followers_text = followers_li.get_text(strip=True)
        else:
            store_sections = soup.find_all('h3')
            for h3_tag in store_sections:
                if 'store data' in h3_tag.get_text().lower():
                    next_ul = h3_tag.find_next_sibling('ul')
                    if next_ul:
                        first_li = next_ul.find('li')
                        if first_li:
                            followers_text = first_li.get_text(strip=True)
                            break
    except Exception as e:
        logging.warning(f"フォロワー数抽出エラー (AppID: {appid}): {e}")
    data["現在のfollower数"] = parse_number_with_suffix(followers_text)

    positive_reviews_text = "N/A"
    negative_reviews_text = "N/A"
    try:
        review_summary_strong = soup.find('strong', string=lambda t: t and "user reviews" in t.lower())
        if review_summary_strong:
            parent_div = review_summary_strong.parent
            if parent_div:
                tooltip_span = parent_div.find('span', class_='tooltip')
                if tooltip_span:
                    tooltip_text = tooltip_span.get_text(separator='|', strip=True)
                    parts = tooltip_text.split('|')
                    if len(parts) >= 2:
                        positive_reviews_text = parts[0]
                        negative_reviews_text = parts[1]
    except Exception as e:
        logging.warning(f"レビュー数抽出エラー (AppID: {appid}): {e}")
    data["ポジティブレビュー数"] = parse_number_with_suffix(positive_reviews_text)
    data["ネガティブレビュー数"] = parse_number_with_suffix(negative_reviews_text)
    
    owner_estimation_text = "N/A"
    try:
        owner_row = soup.find('td', string='Owners')
        if owner_row:
            owner_value_td = owner_row.find_next_sibling('td')
            if owner_value_td:
                owner_estimation_text = owner_value_td.get_text(strip=True).split(' ± ')[0]
    except Exception as e:
        logging.warning(f"オーナー推定数抽出エラー (AppID: {appid}): {e}")
    data["オーナー推定数"] = parse_number_with_suffix(owner_estimation_text)
    return data

def extract_data_from_brightdata_html(html_content, appid):
    if not html_content:
        logging.warning(f"BrightDataからHTMLコンテンツがありません (AppID: {appid})。")
        return {"AppID": appid, "エラー": "HTMLコンテンツなし"}
    try:
        return parse_html_content(html_content, appid)
    except Exception as e:
        logging.error(f"BrightData HTMLの解析中にエラー (AppID: {appid}): {e}", exc_info=True)
        return {"AppID": appid, "エラー": str(e)}

class SteamDBScraper:
    def __init__(self, brightdata_api_token=None):
        if not brightdata_api_token:
            raise ValueError("BrightData API token is required")
        self.brightdata_api_token = brightdata_api_token
        self.user_agents = USER_AGENTS
        self.successful_extractions = 0
        self.collected_data = []
    
    def get_random_user_agent(self):
        return random.choice(self.user_agents)
    
    def get_browser_headers(self, user_agent):
        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": random.choice([
                "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
                "en-US,en;q=0.9,ja;q=0.8",
                "ja,en-US;q=0.9,en;q=0.8"
            ]),
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0"
        }
        if "Chrome" in user_agent:
            headers["sec-ch-ua"] = '"Google Chrome";v="131", "Chromium";v="131", "Not_A Brand";v="24"'
            headers["sec-ch-ua-mobile"] = "?0"
            headers["sec-ch-ua-platform"] = random.choice(['"Windows"', '"macOS"', '"Linux"'])
        elif "Firefox" in user_agent:
            pass
        elif "Safari" in user_agent and "Chrome" not in user_agent:
            headers["Accept"] = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
        return headers
    
    def fetch_with_brightdata_unlocker(self, url):
        try:
            api_url = "https://api.brightdata.com/request"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.brightdata_api_token}"
            }
            data = {
                "zone": "claude_flare_captcha1",
                "url": url,
                "format": "raw"
            }
            logging.info(f"BrightData Web Unlocker APIでページを取得: {url}")
            response = requests.post(api_url, headers=headers, json=data, verify=False, timeout=60)
            if response.status_code == 200:
                logging.info("BrightData APIからコンテンツ取得成功")
                return response.text
            else:
                logging.warning(f"BrightData API エラー: {response.status_code} - {response.text}")
                return None
        except Exception as e:
            logging.error(f"BrightData API呼び出し中にエラー: {e}")
            return None
    
    def _extract_data_from_brightdata_html(self, html_content, appid):
        return extract_data_from_brightdata_html(html_content, appid)
    
    async def scrape_app_data(self, appid, progress_text=""):
        logging.info(f"--- {progress_text} AppID {appid} の処理を開始 ---")
        steamdb_url = f"https://steamdb.info/app/{appid}/charts/"
        async with async_playwright() as p:
            browser = None
            context = None
            page = None
            try:
                user_agent = self.get_random_user_agent()
                headers = self.get_browser_headers(user_agent)
                launch_args = [
                    '--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu',
                    '--disable-dev-shm-usage', '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-blink-features=AutomationControlled',
                    '--window-size=1920,1080', '--start-maximized',
                    f'--user-agent={user_agent}'
                ]
                browser_options = {'headless': True, 'args': launch_args}
                browser = await p.chromium.launch(**browser_options)
                context_options = {
                    'user_agent': user_agent, 'viewport': {'width': 1920, 'height': 1080},
                    'locale': random.choice(['ja-JP', 'en-US']),
                    'timezone_id': random.choice(['Asia/Tokyo', 'America/New_York', 'Europe/London']),
                    'permissions': ['geolocation'], 'device_scale_factor': random.uniform(1.0, 2.0),
                    'has_touch': False, 'java_script_enabled': True, 'accept_downloads': False,
                    'color_scheme': random.choice(['light', 'dark']), 'extra_http_headers': headers
                }
                context = await browser.new_context(**context_options)
                page = await context.new_page()
                await stealth_async(page)
                await page.mouse.move(random.randint(50, 200), random.randint(50, 200))
                await asyncio.sleep(random.uniform(0.5, 1.5))
                logging.info(f"URLからデータを読み込んでいます: {steamdb_url}")
                await page.goto(steamdb_url, wait_until="domcontentloaded", timeout=30000)
                logging.info("ページ遷移完了 (domcontentloaded)。コンテンツの読み込みを待ちます...")
                try:
                    await page.wait_for_selector('body', timeout=10000)
                    page_content = await page.content()
                    if "cloudflare" in page_content.lower() or "checking your browser" in page_content.lower():
                        logging.warning("CloudFlare チャレンジを検出しました。BrightData APIで回避を試行...")
                        brightdata_html = self.fetch_with_brightdata_unlocker(steamdb_url)
                        if brightdata_html:
                            extracted_data = self._extract_data_from_brightdata_html(brightdata_html, appid)
                            logging.info(f"BrightData APIでCloudFlare回避成功: {extracted_data}")
                            logging.info(f"{progress_text} AppID {appid} のBrightData抽出データ:")
                            logging.info(json.dumps(extracted_data, indent=2, ensure_ascii=False))
                            if extracted_data.get("エラー") is None and extracted_data.get("AppID") is not None:
                                self.successful_extractions += 1
                                self.collected_data.append(extracted_data)
                            raise Exception("BrightData_Success")
                        else:
                            logging.warning("BrightData APIも失敗、従来の待機方法を試行...")
                            await asyncio.sleep(random.uniform(10, 20))
                            await page.reload(wait_until="domcontentloaded", timeout=30000)
                            await asyncio.sleep(random.uniform(3, 7))
                except Exception as e:
                    if str(e) != "BrightData_Success":
                        logging.warning(f"CloudFlare検出チェック中にエラー (AppID: {appid}): {e}")
            except Exception as e:
                if str(e) == "BrightData_Success":
                    logging.info(f"{progress_text} AppID {appid} BrightDataで正常に処理完了")
                else:
                    logging.error(f"AppID {appid} のPlaywright処理中にエラーが発生しました: {e}", exc_info=True)
            finally:
                if page and not page.is_closed(): 
                    await page.close()
                if context:
                    await context.close()
                if browser:
                    await browser.close()
        logging.info(f"--- {progress_text} AppID {appid} の処理を終了 ---")

    async def scrape_multiple_apps(self, appid_list, delay_between_apps=10):
        for appid_index, appid in enumerate(appid_list):
            progress_text = f"[{appid_index + 1}/{len(appid_list)}]"
            await self.scrape_app_data(appid, progress_text)
            if appid_index < len(appid_list) - 1:
                logging.info(f"次のAppID処理まで{delay_between_apps}秒待機します...")
                await asyncio.sleep(delay_between_apps)
        return self.successful_extractions, self.collected_data
