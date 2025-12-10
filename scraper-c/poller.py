import json, os, signal, threading, time
from flask import Flask, jsonify
from google.cloud import pubsub_v1
from logging import LoggerAdapter, Logger
from common.logging_config import get_logger
from browser_scraper import scrape_meta_data  # your local module: scraping.process(job_id, url)
from dotenv import load_dotenv
load_dotenv()

PROJECT_ID = os.getenv("PROJECT_ID")
SUBSCRIPTION_ID = os.getenv("SUBSCRIPTION_ID")
MAX_IN_FLIGHT = 10
logger: LoggerAdapter[Logger] = get_logger()


# app = Flask(__name__)

_stop = threading.Event()
_running = False
_last_msg_ts = 0.0

def _handle_messages(messages, subscriber, sub_path):  # Accept list of messages
    global _last_msg_ts
    _last_msg_ts = time.time()
    
    # Prepare all messages to send to scraping module
    messages_to_scrape = []
    invalid_ack_ids = []
    
    for message in messages:
        try:
            # ReceivedMessage has message.message.data, not message.data
            payload = json.loads(message.message.data.decode("utf-8"))
            job_id = payload.get("job_id")
            url = payload.get("url")
            if not job_id or not url:
                invalid_ack_ids.append(message.ack_id)
                continue
            messages_to_scrape.append({
                "url": url,
                "job_id": job_id,
                "ack_id": message.ack_id
            })
        except Exception as e:
            logger.error(f"Error parsing message: {e}")
            invalid_ack_ids.append(message.ack_id)
    
    # Send all messages to scraping module
    result = scrape_meta_data(messages_to_scrape) or {}
    ack_ids = result.get("ack_ids", [])
    nack_ids = result.get("nack_ids", [])
    
    # Add invalid messages to nack_ids
    # nack_ids.extend(invalid_ack_ids)
    
    # Acknowledge successful messages
    if ack_ids:
        subscriber.acknowledge(
            request={"subscription": sub_path, "ack_ids": ack_ids}
        )
    
    # Nack failed messages (modify ack deadline to 0 to make them immediately available again)
    if nack_ids:
        subscriber.modify_ack_deadline(
            request={
                "subscription": sub_path,
                "ack_ids": nack_ids,
                "ack_deadline_seconds": 0,
            }
        )

def _run_subscriber():
    global _running
    print(f"running {PROJECT_ID} {SUBSCRIPTION_ID}")
    
    if not PROJECT_ID or not SUBSCRIPTION_ID:
        _running = False
        return

    subscriber = pubsub_v1.SubscriberClient()
    sub_path = subscriber.subscription_path(PROJECT_ID, SUBSCRIPTION_ID)

    _running = True
    try:
        while not _stop.is_set():
            # Pull up to MAX_IN_FLIGHT messages at once
            response = subscriber.pull(
                request={
                    "subscription": sub_path,
                    "max_messages": MAX_IN_FLIGHT,
                }
            )
            
            if response.received_messages:
                _handle_messages(response.received_messages, subscriber, sub_path)
            
            time.sleep(1)  # Small delay if no messages
    finally:
        try: subscriber.close()
        except Exception: pass
        _running = False

# @app.route("/health", methods=["GET"])
# def health():
#     ok = bool(PROJECT_ID and SUBSCRIPTION_ID and _running)
#     age = None if _last_msg_ts == 0 else round(time.time() - _last_msg_ts, 2)
#     return jsonify(ok=ok, running=_running, last_message_age_sec=age), (200 if ok else 503)

def _graceful_shutdown(*_):
    _stop.set()

if __name__ == "__main__":
    signal.signal(signal.SIGTERM, _graceful_shutdown)
    signal.signal(signal.SIGINT, _graceful_shutdown)
    signal.signal(signal.SIGTERM, _graceful_shutdown)
    signal.signal(signal.SIGINT, _graceful_shutdown)

    _run_subscriber()

    # t = threading.Thread(target=_run_subscriber, name="pubsub-consumer")
    # t.start()

    # MIG health check hits this
    # app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
