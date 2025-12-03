from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from logging import LoggerAdapter, Logger
import hashlib
import re
from datetime import datetime, timezone
import gzip
from google.cloud import storage
from common.logging_config import get_logger

logger: LoggerAdapter[Logger] = get_logger()
app = FastAPI()
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
class UrlRequest(BaseModel):
    url: str

class ChannelIdResponse(BaseModel):
    channel_id: str

def parse_url_to_channel_id(url: str) -> str:
    try:
        response = requests.request("GET", url, headers=headers, data=payload)
        html_res = response.text
        gcs_uri = upload_html(url, html_res)
        logger.info(
            "raw_html_uploaded",
            extra={"event": "raw_html_uploaded", "url": url, "gcs_uri": gcs_uri},
        )
        match = re.search(r'"canonicalBaseUrl":"(/@[^"]+)"', html_res)
        if not match:
            raise ValueError("canonicalBaseUrl not found in response")
        channel_url = f"https://www.youtube.com{match.group(1)}"
        return channel_url
    except Exception as e:
        logger.error(f"Exception while scraping {e}")
        return ""
    
@app.post("/extract-channel-id", response_model=ChannelIdResponse)
def extract_channel_id(body: UrlRequest):
    url = body.url.strip()
    logger.info(
        f"request_received url: {url}",
        extra={"event": "request_received", "url": url},
    )
    channel_id = parse_url_to_channel_id(url)
    
    if not channel_id:
        raise HTTPException(status_code=400, detail="Could not extract channel_id")
    return ChannelIdResponse(channel_id=channel_id)
def _url_hash(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
def upload_html(url: str, html: str, prefix: str = "raw/scraper-a") -> str:
    day = datetime.now(timezone.utc).date().isoformat()
    name = f"{prefix}/{day}/{_url_hash(url)}.txt.gz"
    blob = _storage.bucket(bucket_name).blob(name)
    compressed = gzip.compress(html.encode("utf-8"))
    blob.upload_from_string(compressed, content_type="application/gzip")
    return f"gs://{bucket_name}/{name}"