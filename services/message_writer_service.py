import csv
import os

from utils import create_chat_log_file # For creating the CSV log file
# db and CHAT_LOG_DIR will be passed as arguments

class MessageWriterService:
    """
    Handles writing chat messages to both CSV and MongoDB.
    """
    def __init__(self, video_id: str, db_client, chat_log_directory: str):
        self.video_id = video_id
        self.chat_log_dir = chat_log_directory # Store for potential future use, though create_chat_log_file uses it

        # Initialize CSV file path using create_chat_log_file from utils
        # This creates the file and writes headers.
        self.csv_filepath = create_chat_log_file(video_id, self.chat_log_dir)
        print(f"[MessageWriterService] CSV log file initialized at: {self.csv_filepath}")

        # Get the MongoDB collection using the passed-in db_client
        self.mongo_collection_name = f"messages_{video_id}"
        self.mongo_collection = db_client[self.mongo_collection_name]
        print(f"[MessageWriterService] Using MongoDB collection: {self.mongo_collection_name}")

    def write_message(self, message_data: dict):
        """
        Writes a single message to both the CSV file and MongoDB.
        message_data should be a dictionary containing all necessary fields
        including 'video_id'.
        """
        if "video_id" not in message_data:
            # Ensure video_id is part of the message_data for MongoDB consistency,
            # though the service is initialized with a video_id.
            message_data["video_id"] = self.video_id

        # 1. Write to CSV file (append mode)
        try:
            with open(self.csv_filepath, 'a', newline='', encoding='utf-8') as file:
                writer = csv.writer(file)
                writer.writerow([
                    message_data.get('datetime', ''),
                    message_data.get('author', ''),
                    message_data.get('message', ''),
                    message_data.get('superChat', '') # Ensure this key exists or provide default
                ])
        except Exception as e:
            print(f"[MessageWriterService] Error writing to CSV {self.csv_filepath}: {e}")
            # Decide if you want to raise the error or just log it and continue to MongoDB

        # 2. Write to MongoDB
        try:
            self.mongo_collection.insert_one(message_data)
        except Exception as e:
            print(f"[MessageWriterService] Error writing to MongoDB collection {self.mongo_collection_name}: {e}")
            # Decide if you want to raise the error or just log it

        # Optional: print confirmation for each message written by the service
        # print(f"[{self.video_id}] {message_data.get('datetime')} [{message_data.get('author')}] - {message_data.get('message')}")
        # This might be too verbose if collector.py already prints.

    def get_csv_filepath(self) -> str:
        """Returns the path to the CSV file being managed by this service instance."""
        return self.csv_filepath
