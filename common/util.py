import time, uuid
import os
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
from pymongo import MongoClient

def get_mongo_client() -> MongoClient:
    """
    Build a Mongo client using the MONGO_CONNECTION_STRING env var.

    Raises:
        KeyError: when the env var is missing.
    """
    conn_str = os.environ["MONGO_CONNECTION_STRING"]
    _mongo_client = MongoClient(conn_str)
    return _mongo_client


def _db_name() -> str:
    """Return the Mongo database name from the DBNAME environment variable."""
    return os.environ["DBNAME"]
def get_channel_url(url: str) -> str:
    """
    Look up the given URL in the `url_mapping` collection and return its channel_url.

    Returns an empty string when the URL is missing or the mapping is not found.
    """
    if not url:
        return ""

    db = get_mongo_client()[_db_name()]
    doc = db["Youtube_vid_to_channel"].find_one({"url": url.strip()}, {"channel_url": 1})
    if not doc:
        return ""

    channel_url = doc.get("channel_url")
    return channel_url if isinstance(channel_url, str) else ""

def insert_cotinuation_token(url: str, token: str) -> None:
    """
    Insert a new continuation token document for the given URL into
    the `channel_continuation_mapping` collection.

    Assumes there will be no duplicate URLs.
    """
    db = get_mongo_client()[_db_name()]
    collection = db["channel_continuation_mapping"]

    doc = {
        "url": url,
        "token": token,
        "created_at": datetime.utcnow(),
    }
    try:
        collection.insert_one(doc)
    except Exception as e:
        print(f"{e} error has occur")
    

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
