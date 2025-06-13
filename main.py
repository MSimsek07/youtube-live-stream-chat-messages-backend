# FastAPI backend for YouTube Live Chat Analysis
# Uses pytchat to collect chat and exposes endpoints for the React frontend

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import os
import pytchat
from datetime import datetime
import asyncio
import subprocess
import signal
import psutil
import csv
from pymongo import MongoClient
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import re
from fastapi.responses import JSONResponse

app = FastAPI()

# Allow CORS for local frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CHAT_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat_csv_files")
if not os.path.exists(CHAT_LOG_DIR):
    os.makedirs(CHAT_LOG_DIR)

# MongoDB setup
MONGO_URI = os.environ.get("MONGO_URI") or "mongodb+srv://developer_mu:2kGjFiHrnTXOLsRe@yt-cluster.lmgbl7c.mongodb.net/?retryWrites=true&w=majority&appName=yt-cluster"
try:
    mongo_client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
    mongo_client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(f"[MongoDB] Connection error: {e}")
    raise RuntimeError(f"Failed to connect to MongoDB: {e}")

db = mongo_client["yt_live_chat"]

# Store collection datetime for each video_id
collection_datetimes = {}

def get_collection_datetime(video_id: str):
    if video_id not in collection_datetimes:
        # Generate datetime string when first used for this video_id
        collection_datetimes[video_id] = datetime.now().strftime("%Y%m%d_%H%M%S")
    return collection_datetimes[video_id]

def get_messages_collection(video_id: str):
    """Get or create a collection for the specific video stream and datetime"""
    dt = get_collection_datetime(video_id)
    collection_name = f"messages_{video_id}_{dt}"
    return db[collection_name]

# Helper to create filename

def create_chat_log_file(video_id):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"chat_log_{video_id}_{timestamp}.csv"
    filepath = os.path.join(CHAT_LOG_DIR, filename)
    # Create CSV with headers
    with open(filepath, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['datetime', 'author', 'message', 'superChat'])
    return filepath

# Background task to collect chat

async def chat_callback(chatdata, filename, video_id):
    print(f"Callback triggered, items: {len(chatdata.items)}")
    async with asyncio.Lock():
        with open(filename, 'a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            collection = get_messages_collection(video_id)
            for c in chatdata.items:
                message = {
                    "datetime": c.datetime,
                    "author": c.author.name,
                    "message": c.message,
                    "amountString": getattr(c, 'amountString', None)
                }
                # Write CSV row
                writer.writerow([
                    message['datetime'],
                    message['author'],
                    message['message'],
                    message['amountString'] or ''
                ])
                collection.insert_one(message)  # Insert into MongoDB
                await chatdata.tick_async()

async def collect_chat_async(video_id: str, filename: str):
    from pytchat import LiveChatAsync
    print(f"[yt-backend] Starting chat collection for video_id={video_id}, filename={filename}")
    async def callback(chatdata):
        await chat_callback(chatdata, filename, video_id)
    try:
        livechat = LiveChatAsync(video_id, callback=callback, interruptable=False)
        while livechat.is_alive():
            await asyncio.sleep(3)
    except Exception as e:
        print(f"[yt-backend] Error collecting chat for {video_id}: {e}")
    try:
        livechat.raise_for_status()
    except Exception as e:
        print(f"[yt-backend] Chat finished for {video_id}: {e}")
    print(f"[yt-backend] Chat collection ended for video_id={video_id}, filename={filename}")

# Track running collector processes by video_id
collector_processes = {}

@app.post("/start_chat/{video_id}")
def start_chat_collection(video_id: str):
    # Launch the collector.py script as a subprocess
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "collector.py")
    proc = subprocess.Popen(["python", script_path, video_id])
    collector_processes[video_id] = proc.pid
    # Find the latest log file for this video_id
    files = [f for f in os.listdir(CHAT_LOG_DIR) if f.startswith(f"chat_log_{video_id}_") and f.endswith(".csv")]
    latest_file = max(files, key=lambda f: os.path.getctime(os.path.join(CHAT_LOG_DIR, f)), default=None)
    return {"status": "started", "filename": latest_file}

@app.post("/stop_chat/{video_id}")
def stop_chat_collection(video_id: str):
    pid = collector_processes.get(video_id)
    if not pid:
        return {"status": "not running"}
    try:
        p = psutil.Process(pid)
        p.terminate()
        p.wait(timeout=5)
        del collector_processes[video_id]
        return {"status": "stopped"}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.get("/chat_logs", response_model=List[str])
def list_chat_logs():
    files = [f for f in os.listdir(CHAT_LOG_DIR) if f.startswith("chat_log_") and f.endswith(".csv")]
    return files

@app.get("/chat_log/{filename}")
def get_chat_log(filename: str):
    filepath = os.path.join(CHAT_LOG_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="File not found")
    messages = []
    with open(filepath, 'r', newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)  # Skip header row
        for row in reader:
            if len(row) >= 4:
                messages.append({
                    "datetime": row[0],
                    "author": row[1],
                    "message": row[2],
                    "superChat": row[3]
                })
    return {"messages": messages}

# Helper to parse a chat log line to dict
def parse_chat_line(line, video_id):
    match = re.match(r"^([\d-]+ [\d:]+) \[(.+?)\]- (.*)$", line)
    if not match:
        return None
    datetime_str, author, text = match.groups()
    return {
        "video_id": video_id,
        "datetime": datetime_str,
        "author": author.strip(),
        "text": text.strip(),
    }

@app.get("/messages/{video_id}")
def get_messages(video_id: str):
    msgs = list(get_messages_collection(video_id).find({}, {"_id": 0}))
    return {"messages": msgs}

@app.post("/analyze/{video_id}")
def analyze_messages(video_id: str):
    # Placeholder: just return count for now
    msgs = list(get_messages_collection(video_id).find({}, {"_id": 0}))
    return {"count": len(msgs), "message": "Analysis would run here."}

# Helper to get latest chat log file for a video_id

def get_latest_chat_log_file(video_id):
    files = [f for f in os.listdir(CHAT_LOG_DIR) if f.startswith(f"chat_log_{video_id}_") and f.endswith(".csv")]
    if not files:
        return None
    latest_file = max(files, key=lambda f: os.path.getctime(os.path.join(CHAT_LOG_DIR, f)))
    return os.path.join(CHAT_LOG_DIR, latest_file)

@app.get("/chat_log_messages/{video_id}")
def get_chat_log_messages(video_id: str):
    """Return all messages from the latest chat log CSV file for this video_id as JSON."""
    log_file = get_latest_chat_log_file(video_id)
    if not log_file or not os.path.exists(log_file):
        return JSONResponse(status_code=404, content={"error": "Chat log file not found."})
    messages = []
    with open(log_file, 'r', newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)  # Skip header row
        for row in reader:
            if len(row) >= 4:
                msg = {
                    "datetime": row[0],
                    "author": row[1],
                    "message": row[2],
                    "superChat": row[3],
                    "video_id": video_id
                }
                # Add numeric timestamp (ms since epoch, UTC)
                try:
                    dt = datetime.strptime(msg["datetime"], "%Y-%m-%d %H:%M:%S")
                    msg["timestamp"] = int(dt.timestamp() * 1000)
                except Exception:
                    msg["timestamp"] = 0
                messages.append(msg)
    return {"messages": messages}

@app.post("/import_csv_to_mongo/{video_id}")
def import_csv_to_mongo(video_id: str):
    """Read all messages from the latest chat log CSV file and insert them into MongoDB."""
    log_file = get_latest_chat_log_file(video_id)
    if not log_file or not os.path.exists(log_file):
        return JSONResponse(status_code=404, content={"error": "Chat log file not found."})
    messages = []
    with open(log_file, 'r', newline='', encoding='utf-8') as f:
        reader = csv.reader(f)
        next(reader)  # Skip header row
        for row in reader:
            if len(row) >= 4:
                msg = {
                    "video_id": video_id,
                    "datetime": row[0],
                    "author": row[1],
                    "message": row[2],
                    "superChat": row[3]
                }
                messages.append(msg)
    if not messages:
        return {"inserted": 0, "message": "No messages to import."}
    # Insert only messages that are not already in MongoDB
    inserted_count = 0
    for msg in messages:
        if not get_messages_collection(video_id).find_one({
            "video_id": msg["video_id"],
            "datetime": msg["datetime"],
            "author": msg["author"],
            "message": msg["message"]
        }):
            get_messages_collection(video_id).insert_one(msg)
            inserted_count += 1
    return {"inserted": inserted_count, "message": f"Imported {inserted_count} new messages to MongoDB."}
