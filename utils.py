import os
import csv
from datetime import datetime

# CHAT_LOG_DIR will now be passed as an argument

def create_chat_log_file(video_id: str, chat_log_dir: str) -> str:
    """
    Creates a new CSV chat log file for a given video_id in the specified chat_log_dir.
    The filename includes a timestamp.
    Returns the full path to the created file.
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"chat_log_{video_id}_{timestamp}.csv"
    filepath = os.path.join(chat_log_dir, filename)
    # Create CSV with headers
    # Ensure the directory exists before trying to create the file
    os.makedirs(chat_log_dir, exist_ok=True)
    with open(filepath, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(['datetime', 'author', 'message', 'superChat'])
    print(f"[Utils] Created chat log file: {filepath}")
    return filepath
