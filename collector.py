import pytchat
from datetime import datetime
import os
import sys
import csv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import re

MONGO_URI = os.environ.get("MONGO_URI") or "mongodb+srv://developer_mu:2kGjFiHrnTXOLsRe@yt-cluster.lmgbl7c.mongodb.net/?retryWrites=true&w=majority&appName=yt-cluster"
mongo_client = MongoClient(MONGO_URI, server_api=ServerApi('1'))
db = mongo_client["yt_live_chat"]

def get_messages_collection(video_id):
    return db[f"messages_{video_id}"]

CHAT_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "chat_csv_files")
if not os.path.exists(CHAT_LOG_DIR):
    os.makedirs(CHAT_LOG_DIR)

def create_chat_log_file(video_id):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"chat_log_{video_id}_{timestamp}.csv"
    filepath = os.path.join(CHAT_LOG_DIR, filename)
    # Create CSV with headers
    with open(filepath, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['datetime', 'author', 'message', 'superChat'])
    return filepath

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

def store_chat_messages(video_id):
    chat = pytchat.create(video_id=video_id)
    filename = create_chat_log_file(video_id)
    print(f"Storing chat messages in {filename}")
    messages_collection = get_messages_collection(video_id)
    try:
        while chat.is_alive():
            for c in chat.get().sync_items():
                message = {
                    "datetime": c.datetime,
                    "author": c.author.name,
                    "message": c.message,
                    "superChat": getattr(c, 'amountString', None)
                }
                # Write to CSV
                with open(filename, 'a', newline='', encoding='utf-8') as file:
                    writer = csv.writer(file)
                    writer.writerow([
                        message['datetime'],
                        message['author'],
                        message['message'],
                        message['superChat'] or ''
                    ])
                # Store in MongoDB
                message['video_id'] = video_id
                messages_collection.insert_one(message)
                print(f"{message['datetime']} [{message['author']}] - {message['message']}"
                      f"{' (Superchat: ' + message['superChat'] + ')' if message['superChat'] else ''}")
    except KeyboardInterrupt:
        print("\nStopping chat collection...")
    except Exception as e:
        print(f"An error occurred: {str(e)}")
    finally:
        print(f"\nChat messages have been saved to {filename}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python collector.py <video_id>")
        sys.exit(1)
    store_chat_messages(sys.argv[1])
