# FastAPI backend for YouTube Live Chat Analysis
# Uses pytchat to collect chat and exposes endpoints for the React frontend

from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import List
import os
import pytchat
from datetime import datetime
import asyncio
import csv # Still needed for chat_callback, if that remains here
import re # May not be needed after refactor
from fastapi.responses import JSONResponse

# Service imports
from services import process_service
from services import chat_data_service

# Config imports for dependency injection into services
from config import db, CHAT_LOG_DIR

app = FastAPI()

# Note: Consider moving get_messages_collection to chat_data_service.py as well
# For now, keeping it as it is used by chat_callback which is also in main.py
# If chat_callback were moved or its DB logic abstracted, get_messages_collection could move.

# Allow CORS for local frontend
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS")
if ALLOWED_ORIGINS:
    allow_origins = [origin.strip() for origin in ALLOWED_ORIGINS.split(',')]
else:
    allow_origins = []

app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# CHAT_LOG_DIR is now imported from config.py
# MongoDB setup (MONGO_URI, mongo_client, db) is now imported from config.py
# The connection ping is also handled in config.py

# --- Potentially move to chat_data_service.py or a db_utils.py ---
def get_messages_collection(video_id: str):
    """Get a collection for the specific video stream."""
    collection_name = f"messages_{video_id}" # Consistent with chat_data_service
    return db[collection_name]
# --- End of section to potentially move ---


# --- pytchat related background tasks ---
# These are more complex to move due to FastAPI's BackgroundTasks and async nature.
# For now, they remain in main.py.
# If these were to be moved, a service might need to accept BackgroundTasks instance
# or use a different mechanism for background operations.

async def chat_callback(chatdata, filename, video_id):
    # This function is called by pytchat's LiveChatAsync, not directly an endpoint.
    # It uses get_messages_collection, which needs `db` from config.
    print(f"Callback triggered, items: {len(chatdata.items)}")
    async with asyncio.Lock(): # Ensure atomic file writes and DB inserts if needed
        with open(filename, 'a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            collection = get_messages_collection(video_id) # Uses local/imported get_messages_collection
            for c in chatdata.items:
                message = {
                    "datetime": c.datetime,
                    "author": c.author.name,
                    "message": c.message,
                    "amountString": getattr(c, 'amountString', None) # SuperChat amount
                }
                writer.writerow([
                    message['datetime'], message['author'], message['message'], message['amountString'] or ''
                ])
                # Also store in MongoDB
                db_message = message.copy()
                db_message["video_id"] = video_id # Add video_id for DB context
                collection.insert_one(db_message)
                await chatdata.tick_async()

async def collect_chat_async(video_id: str, filename: str):
    # Also part of pytchat background processing.
    from pytchat import LiveChatAsync # Keep import here to avoid top-level if pytchat is optional
    print(f"[yt-backend] Starting chat collection for video_id={video_id}, filename={filename}")

    async def callback_for_pytchat(chatdata_from_pytchat):
        await chat_callback(chatdata_from_pytchat, filename, video_id)

    try:
        livechat = LiveChatAsync(video_id, callback=callback_for_pytchat, interruptable=False)
        while livechat.is_alive():
            await asyncio.sleep(3) # Check liveness periodically
    except Exception as e:
        print(f"[yt-backend] Error collecting chat for {video_id}: {e}")
    finally:
        print(f"[yt-backend] Chat collection ended for video_id={video_id}, filename={filename}")
        # livechat.raise_for_status() # This might raise an exception if chat ended normally or with error

# --- End of pytchat background tasks ---


# API Endpoints - Refactored to use services
@app.post("/start_chat/{video_id}")
async def start_chat_collection_endpoint(video_id: str, background_tasks: BackgroundTasks):
    # This endpoint now uses process_service to start the collector.
    # The actual pytchat collection (collect_chat_async) is complex to move entirely
    # to a synchronous service due to its async nature and BackgroundTasks.
    # For this refactor, we assume collector.py (started by process_service) handles the pytchat logic.
    # If main.py were to *also* run collection via pytchat directly (e.g. for a different mode),
    # then collect_chat_async would be relevant here.
    # The current setup uses collector.py as the primary collection mechanism.

    # The request was to move logic from the *old* /start_chat/{video_id} to process_service.
    # That old logic directly started collector.py.
    # Pass CHAT_LOG_DIR to the service function.
    # Service layer now raises HTTPException on error, so no need for explicit checks here.
    return process_service.start_collector_process(video_id, chat_log_dir=CHAT_LOG_DIR)

@app.post("/stop_chat/{video_id}")
def stop_chat_collection_endpoint(video_id: str):
    # Service layer now raises HTTPException on error (e.g., 404 if not running, 500 for other errors)
    return process_service.stop_collector_process(video_id)

@app.get("/chat_logs", response_model=List[str])
def list_chat_logs_endpoint():
    return chat_data_service.list_log_files(chat_log_dir=CHAT_LOG_DIR)

@app.get("/chat_log/{filename}")
def get_chat_log_endpoint(filename: str):
    # HTTPException is handled by the service
    return chat_data_service.get_log_file_messages(filename, chat_log_dir=CHAT_LOG_DIR)

@app.get("/messages/{video_id}")
def get_messages_endpoint(video_id: str):
    # HTTPException is handled by the service
    return chat_data_service.get_db_messages(video_id, db_client=db)

@app.post("/analyze/{video_id}")
def analyze_messages_endpoint(video_id: str):
    # HTTPException is handled by the service
    return chat_data_service.analyze_video_messages(video_id, db_client=db)

@app.get("/chat_log_messages/{video_id}")
def get_chat_log_messages_endpoint(video_id: str):
    # HTTPException is handled by the service
    return chat_data_service.get_latest_csv_messages(video_id, chat_log_dir=CHAT_LOG_DIR)

@app.post("/import_csv_to_mongo/{video_id}")
def import_csv_to_mongo_endpoint(video_id: str):
    # HTTPException is handled by the service
    return chat_data_service.import_csv_to_db(video_id, db_client=db, chat_log_dir=CHAT_LOG_DIR)

# Endpoint to view running collector processes (optional utility)
@app.get("/running_collectors")
def get_running_collectors_endpoint():
    return {"running_collectors": process_service.get_running_processes()}
