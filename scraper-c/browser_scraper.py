# app.py
import time, uuid
from io import BytesIO
from pathlib import Path
from flask import Flask, jsonify, send_file, abort, request
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from common.gcp_functions import upload_html_gzip,upload_png_gzip,upload_dicts_gzip

app = Flask(__name__)

SCREEN_DIR = Path("screens")          # <-- local path (relative)
SCREEN_DIR.mkdir(parents=True, exist_ok=True)
SCREEN_CACHE: dict[str, bytes] = {}
def construct_success_path(url: str, suffix : str):
    """
    Build a GCS object prefix for successfully scraped artifacts.

    Result pattern: scraped/<YYYY-MM-DD>/<prefix>_
    """
    # Drop query/fragment noise and trailing slash before taking the tail segment
    trimmed = url.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    prefix = trimmed.split("/")[-1] or "root"
    day = time.strftime("%Y-%m-%d")
    return f"scraped/{day}/{prefix}_{suffix}"
def construct_failure_path(url: str , suffix : str):
    """
    Build a GCS object prefix for erraneous scraped artifacts.

    Result pattern: error/<YYYY-MM-DD>/<prefix>_
    """
    # Drop query/fragment noise and trailing slash before taking the tail segment
    trimmed = url.split("?", 1)[0].split("#", 1)[0].rstrip("/")
    prefix = trimmed.split("/")[-1] or "root"
    day = time.strftime("%Y-%m-%d")
    return f"error/{day}/{prefix}_{suffix}"
js_to_run = """
([xp1, xp2]) => {
  const has1 = !!document.evaluate(
    xp1, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null
  ).singleNodeValue;

  if (has1) return "primary";

  const has2 = !!document.evaluate(
    xp2, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null
  ).singleNodeValue;

  if (has2) return "fallback";

  // Keep waiting
  return false;
}
"""
def snap(page, label: str) -> str:
    ts = time.strftime("%Y%m%d-%H%M%S")
    fname = f"{ts}-{label}-{uuid.uuid4().hex[:8]}.png"
    # Keep screenshots in-memory to avoid filesystem writes
    SCREEN_CACHE[fname] = page.screenshot(full_page=True)
    return fname
def get_html(page, label:str) -> str:
    ts = time.strftime("%Y%m%d-%H%M%S")
    fname = f"{ts}-{label}-{uuid.uuid4().hex[:8]}.html"
    html_content = page.content()
    (SCREEN_DIR / fname).write_text(html_content, encoding='utf-8')
    return fname
import re
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError



def has_key_anywhere(obj, key: str) -> bool:
    if isinstance(obj, dict):
        if key in obj:
            return True
        return any(has_key_anywhere(v, key) for v in obj.values())
    elif isinstance(obj, list):
        return any(has_key_anywhere(i, key) for i in obj)
    return False
def is_youtube_browse_response(response):
    url = response.url
    # Match base endpoint; query params (like prettyPrint=false) are optional
    return url.startswith("https://www.youtube.com/youtubei/v1/browse")
@app.post("/debug/title")
def scrape():
    data = request.get_json()
    if not data or "url" not in data:
        return jsonify({"ok": False, "error": "Missing 'url' in request body"}), 400
    url = data.get('url')
    jobid = data.get('jobid')
    scrape_res = scrape_meta_data(url)
    return jsonify(scrape_res), 200
    # if scrape_res.get("ok"):
    #     return jsonify(scrape_res), 200
    # else:
    #     return jsonify(scrape_res), 500

def scrape_meta_data(messages_to_scrape):
    
    timeout_ms = int("15000")
    shots = []
    PROXY_SERVER = "http://proxy.froxy.com:9000"
    PROXY_USER = "hADds22r8q5wXOnf"
    PROXY_PASS = "wifi;us;;;"
    image_file_destination = ""
    html_file_destination = ""
    json_file_destination = ""
    with sync_playwright() as p:
        
        browser = p.chromium.launch(headless=True, 
                                            args=["--no-sandbox"],
                                            proxy={
                                                "server": PROXY_SERVER,
                                                "username": PROXY_USER,
                                                "password": PROXY_PASS,
                                            }
                                            )
        context = browser.new_context(viewport={"width": 1280, "height": 720},user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.1938.81")
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            """)
        for message in messages_to_scrape:
            yt_responses_data = []
            url = message.get('url')
            
            try:
                    page = context.new_page()
                    def on_response(response):
                        if not is_youtube_browse_response(response):
                            return
                        try:
                            data = response.json()
                        except Exception as e:
                            print("Failed to parse JSON from", response.url, ":", e)
                            return

                        if has_key_anywhere(data, "country"):
                            print("✅ Matched YouTube browse response with 'country':", response.url)
                            yt_responses_data.append(data)
                    page.on("response", on_response)
                    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
                    html_path = get_html(page,"error")
                    more_xpath = "(//span[normalize-space(.)='...more' and contains(@style,'font-weight: 500')])[1]"
                    accept_cookies_xpath = '//button[@aria-label="Accept all"]'
                    main_page = False
                    while not main_page:
                        handle =page.wait_for_function(js_to_run, arg=[more_xpath,accept_cookies_xpath],timeout= timeout_ms)
                        if handle.json_value() == "primary":
                            main_page = True
                            continue
                        else:
                            cookie_consent_clicked = page.evaluate("""
                            (xp) => {
                            const el = document.evaluate(xp, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                            if (!el) return false;
                            el.scrollIntoView({ block: "center" });
                            el.click();
                            return true;
                            }
                            """, accept_cookies_xpath)
                            if not cookie_consent_clicked:
                                image_file_destination = construct_failure_path(url,"cookie_click.png.gz")
                                html_file_destination = construct_failure_path(url,"cookie_click.html.gz")
                    clicked = page.evaluate("""
                            (xp) => {
                            const el = document.evaluate(xp, document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
                            if (!el) return false;
                            el.scrollIntoView({ block: "center" });
                            el.click();
                            return true;
                            }
                            """, more_xpath)
                            
                    if not clicked:
                        image_file_destination = construct_failure_path(url,"more_click.png.gz")
                        html_file_destination = construct_failure_path(url,"more_click.html.gz")
                    
                    time.sleep(2)
                    full_page =page.screenshot(full_page=True)
                    html_str = page.content()
                    page.close()
                    if len(yt_responses_data) == 0:
                        image_file_destination = construct_failure_path(url,"more_click.png.gz")
                        html_file_destination = construct_failure_path(url,"more_click.html.gz")
                    
                    image_file_destination = construct_success_path(url,"more_click.png.gz")
                    html_file_destination = construct_success_path(url,"more_click.html.gz")
                    json_file_destination = construct_success_path(url,"more_click.json.gz")                    
                    
                
            except PlaywrightTimeoutError:
                image_file_destination = construct_failure_path(url,".png.gz")
                html_file_destination = construct_failure_path(url,".html.gz")
                json_file_destination = construct_failure_path(url,".json.gz")
                # return {"ok": False, "error": str(e),
                #                         "screenshots": [f"/screens/{s}" for s in shots],
                #                         "HTML":html_path
                #                         }
            except Exception as e:
                image_file_destination = construct_failure_path(url,".png.gz")
                html_file_destination = construct_failure_path(url,".html.gz")
                json_file_destination = construct_failure_path(url,".json.gz")
                # return {"ok": False, "error": str(e),
                #                         "screenshots": [f"/screens/{s}" for s in shots],
                #                         "HTML":html_path
                #                         }
            upload_png_gzip(full_page,image_file_destination)
            upload_html_gzip(html_str,html_file_destination)
            if image_file_destination:
                upload_dicts_gzip(yt_responses_data,json_file_destination)
        browser.close()

# @app.get("/screens/<path:filename>")
# def get_screen(filename):
#     if ".." in filename or filename.startswith("/"):
#         abort(400)
#     data = SCREEN_CACHE.get(filename)
#     if data is None:
#         abort(404)
#     return send_file(BytesIO(data), mimetype="image/png", download_name=filename)
