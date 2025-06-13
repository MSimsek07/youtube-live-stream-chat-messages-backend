import pytchat
from datetime import datetime
import os
import sys
import csv # Still needed for the service if it uses csv writer directly, but not here
import re # Not used here anymore
from config import db, CHAT_LOG_DIR # Import db and CHAT_LOG_DIR for dependency injection
from services.message_writer_service import MessageWriterService

# get_messages_collection is removed as MessageWriterService handles DB collection.
# CHAT_LOG_DIR and create_chat_log_file are used by MessageWriterService.

# parse_chat_line function was here, removed as it was unused.

def store_chat_messages(video_id):
    chat = pytchat.create(video_id=video_id)

    # Instantiate the message writer service
    # This will also create the initial CSV file and set up MongoDB collection
    try:
        # Pass db and CHAT_LOG_DIR to the service constructor
        writer_service = MessageWriterService(video_id=video_id, db_client=db, chat_log_directory=CHAT_LOG_DIR)
    except Exception as e:
        print(f"Error initializing MessageWriterService: {e}")
        # Depending on how MessageWriterService handles init errors (e.g., if create_chat_log_file fails),
        # this might need more robust error handling or the service ensures it can be instantiated.
        return # Exit if service cannot be initialized

    csv_log_filename = writer_service.get_csv_filepath()
    print(f"Storing chat messages. CSV: {csv_log_filename}, MongoDB Collection: messages_{video_id}")

    try:
        while chat.is_alive():
            for c in chat.get().sync_items():
                message_data = {
                    "video_id": video_id, # Ensure video_id is included
                    "datetime": c.datetime,
                    "author": c.author.name,
                    "message": c.message,
                    "superChat": getattr(c, 'amountString', None)
                }

                # Use the service to write the message
                writer_service.write_message(message_data)

                # Print to console (as before)
                print(f"{message_data['datetime']} [{message_data['author']}] - {message_data['message']}"
                      f"{' (SuperChat: ' + message_data['superChat'] + ')' if message_data['superChat'] else ''}")

    except KeyboardInterrupt:
        print("\nStopping chat collection...")
    except Exception as e:
        print(f"An error occurred during chat collection: {str(e)}")
    finally:
        # The CSV file is managed (opened and closed per write or kept open) by the service.
        # Here, we just confirm where it was being saved.
        print(f"\nChat messages have been saved to {csv_log_filename} and MongoDB.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python collector.py <video_id>")
        sys.exit(1)
    store_chat_messages(sys.argv[1])
