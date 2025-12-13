# app.py
import time, uuid
from io import BytesIO
from pathlib import Path
import os
from flask import Flask, jsonify, send_file, abort, request
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from common.gcp_functions import upload_html_gzip,upload_png_gzip,upload_dicts_gzip
from common.util import construct_success_path, construct_failure_path, insert_cotinuation_token
import random
from constants import js_to_run, proxy_options
from dotenv import load_dotenv
load_dotenv()
from logging import LoggerAdapter, Logger
from common.logging_config import get_logger

logger: LoggerAdapter[Logger] = get_logger()
SCREEN_CACHE: dict[str, bytes] = {}
PROXY_SERVER = os.getenv("PROXY_SERVER")
PROXY_USER = os.getenv("PROXY_USER","")
prox_to_use = random.choice(proxy_options)
PROXY_PASS_TEMPLATE = "wifi;{country};{isp};{region};{city}"


import re
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

class ScrapingError(Exception):
    """Custom error for scraping-related failures."""
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message

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

def scrape_meta_data(messages_to_scrape):
    PROXY_PASS = PROXY_PASS_TEMPLATE.format(country = prox_to_use.get("country",""),isp = prox_to_use.get("isp",""),
                                        region = prox_to_use.get("region"), city = prox_to_use.get("city",""))
    timeout_ms = 45000
    ack_ids =[]
    image_file_destination = ""
    html_file_destination = ""
    json_file_destination = ""
    with sync_playwright() as p:
        
        browser = p.chromium.launch(headless=True, 
                                            args=["--no-sandbox"],
                                            proxy={
                                                "server": os.getenv("PROXY_SERVER",""),
                                                "username": os.getenv("PROXY_USER",""),
                                                "password": PROXY_PASS,
                                            }
                                            )
        context = browser.new_context(viewport={"width": 1280, "height": 720},user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.1938.81")
        context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
            """)
        for message in messages_to_scrape:
            yt_responses_data = []
            yt_request_data = []
            url = message.get('url')
            full_page = ""
            html_str = ""
            try:
                    page = context.new_page()
                    def on_response(response):
                        if not is_youtube_browse_response(response):
                            return
                        try:
                            data = response.json()
                        except Exception as e:
                            logger.error("Failed to parse JSON from", response.url, ":", e)
                            return

                        if has_key_anywhere(data, "country"):
                            logger.info("✅ Matched YouTube browse response with 'country':", response.url)
                            yt_responses_data.append(data)
                            try:
                                request = response.request
                                raw_body = request.post_data          # string or None
                                json_body = request.post_data_json 
                                yt_request_data.append(json_body)
                            except Exception as e:
                                logger.error(f"Error {e} occurred while inspecting request")
                    page.on("response", on_response)
                    page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
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
                                raise ScrapingError(f"Failed to click cookie consent while scraping {url}")
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
                        raise ScrapingError(f"Failed to click more while scraping {url}")
                    page.wait_for_event(
                        "response",
                        predicate=lambda r: is_youtube_browse_response(r),
                        timeout=timeout_ms,
                    )
                    if len(yt_responses_data) == 0:
                        logger.error(f"Failed to intercept enrichment response while scraping {url}")
                        raise ScrapingError(f"Failed to intercept enrichment response while scraping {url}")
                    else:
                        json_file_destination = construct_success_path(url,"more_click.json.gz")  
                        if len(yt_request_data)>0 and  yt_request_data[0].get('continuation'):
                            logger.info(f"Got continuation token for {url}")       
                            insert_cotinuation_token(url,yt_request_data[0].get('continuation'))
                        else:
                            logger.error("Failed to get continuation token for {url}")
                        
                        upload_dicts_gzip(yt_request_data,json_file_destination)
                        ack_ids.append(message.get('ack_id'))
                        page.close()
            
            except ScrapingError as e:
                logger.error(f"Error {e} happened while scraping")
                full_page =page.screenshot(full_page=True)
                html_str = page.content()
                image_file_destination = construct_failure_path(url,".png.gz")
                html_file_destination = construct_failure_path(url,".html.gz") 
                upload_html_gzip(html_str,html_file_destination) 
                upload_png_gzip(full_page,image_file_destination)   
                page.close()             
            except PlaywrightTimeoutError:
                logger.error(f"Playwright timed out while sccraping {url}")
                full_page =page.screenshot(full_page=True)
                html_str = page.content()
                image_file_destination = construct_failure_path(url,".png.gz")
                html_file_destination = construct_failure_path(url,".html.gz") 
                upload_html_gzip(html_str,html_file_destination) 
                upload_png_gzip(full_page,image_file_destination) 
                page.close()            
            except Exception as e:
                logger.error(f"Error {e} in Playwright while scraping {url}")
        try:  
            browser.close()
        except Exception as e:
            logger.error(f"Error {e} while closing browser")
        return ack_ids
