from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import requests
from lxml import html
import pandas as pd
from logging import LoggerAdapter, Logger

from common.logging_config import get_logger

logger: LoggerAdapter[Logger] = get_logger()
app = FastAPI()

headers = {
  'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
  'accept-encoding': 'gzip, deflate, br, zstd',
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
        tree = html.fromstring(html_res)
        channel_url = tree.xpath("//link[starts-with(@href, 'http://www.youtube.com/@')]/@href")[0]
        return channel_url
    except Exception as e:
        logger.error(f"Exception while scraping {e}")
        return ""
    
@app.post("/extract-channel-id", response_model=ChannelIdResponse)
def extract_channel_id(body: UrlRequest):
    url = body.url.strip()
    logger.info(
        "request_received",
        extra={"event": "request_received", "url": url},
    )
    channel_id = parse_url_to_channel_id(url)
    
    if not channel_id:
        raise HTTPException(status_code=400, detail="Could not extract channel_id")
    return ChannelIdResponse(channel_id=channel_id)
