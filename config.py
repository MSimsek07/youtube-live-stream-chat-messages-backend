import os
import sys
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi

# MongoDB setup
MONGO_URI = os.environ.get("MONGO_URI")
if not MONGO_URI:
    print("Error: MONGO_URI environment variable not set. Application cannot start.")
    sys.exit(1) # Exit if MONGO_URI is not set

try:
    mongo_client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
    # Ping MongoDB to verify connection during initialization
    mongo_client.admin.command('ping')
    print("[Config] Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(f"[Config] MongoDB Connection error: {e}")
    # Exit if connection fails, as the application relies on it
    sys.exit(1)

db = mongo_client["yt_live_chat"]

# Chat log directory setup
CHAT_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat_csv_files")
if not os.path.exists(CHAT_LOG_DIR):
    os.makedirs(CHAT_LOG_DIR)
    print(f"[Config] Created CHAT_LOG_DIR at {CHAT_LOG_DIR}")
else:
    print(f"[Config] CHAT_LOG_DIR already exists at {CHAT_LOG_DIR}")
