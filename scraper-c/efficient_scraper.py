
import requests
from logging import LoggerAdapter, Logger
import hashlib
import re
from datetime import datetime, timezone
import gzip
from google.cloud import storage
from common.logging_config import get_logger
from constants import continuation_payload, continuation_headers, continuation_url
import json
logger: LoggerAdapter[Logger] = get_logger()
_storage = storage.Client()
bucket_name = "isolated-temp-1-yt-scrape-2c493a"
headers = {
  'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
  'accept-encoding': '',
  'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8',
  'connection': 'keep-alive',
  'host': 'www.youtube.com',
  'sec-ch-ua': '"Chromium";v="112", "Google Chrome";v="142", "Not_A Brand";v="99"',
  'sec-ch-ua-mobile': '?0',
  'sec-ch-ua-platform': '"macOS"',
  'sec-fetch-dest': 'document',
  'sec-fetch-mode': 'navigate',
  'sec-fetch-site': 'none',
  'sec-fetch-user': '?1',
  'upgrade-insecure-requests': '1',
  'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36',
  'x-browser-channel': 'stable',
  'x-browser-year': '2025'
}
payload = {}


# class ChannelIdResponse(BaseModel):
#     channel_id: str

def parse_url_to_meta_data(url: str) -> str:
    try:
        response = requests.request("GET", url, headers=headers, data=payload)
        html_res = response.text
        # gcs_uri = upload_html(url, html_res)
        continuation_token = re.search(
            r'"token":"([^"]+)","request":"CONTINUATION_REQUEST_TYPE_BROWSE"', html_res
        )
        visitor_data = re.search(
            r'"visitorData":"([^"]+)"', html_res
        )
        if not visitor_data:
            raise ValueError("visitor data not found in response")
        visitor_data = visitor_data.group(1)
        
        continuation_payload["context"]["client"]["visitorData"] = visitor_data
        if not continuation_token:
            raise ValueError("continuation token not found in response")
        continuation_token = continuation_token.group(1)
        continuation_payload["continuation"] = continuation_token
        continuation_payload["context"]["client"]["originalUrl"] = url
        continuation_headers["referer"] = url
        response = requests.request("POST", continuation_url, headers=continuation_headers, data=json.dumps(continuation_payload))
        meta_data = response.json()
        # gcs_uri = upload_html(url, json.dumps(meta_data), "raw/scraper-b/meta_data")
        logger.info(
            "meta_data_uploaded"
        )
        return meta_data
    except Exception as e:
        logger.error(f"Exception while scraping {e}")
        return ""
