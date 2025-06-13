import pytest
import os
import csv
from datetime import datetime
import shutil # For cleaning up directories

# Import the function to test
from utils import create_chat_log_file
# CHAT_LOG_DIR from config is no longer directly used by the test logic here,
# as the path is explicitly managed by the fixture.

# Define the path for the test-specific chat log directory
TEST_CHAT_LOG_DIR_ROOT = os.path.dirname(os.path.abspath(__file__))
TEST_CHAT_LOG_SUBDIR = "test_chat_csv_files_utils" # Unique name for this test module
TEST_CHAT_LOG_DIR = os.path.join(TEST_CHAT_LOG_DIR_ROOT, TEST_CHAT_LOG_SUBDIR)

@pytest.fixture(scope="function") # Changed autouse to False, test will explicitly use it.
def managed_test_chat_log_dir():
    """
    Fixture to create a test-specific chat log directory before a test
    and clean it up afterwards. Yields the path to the created directory.
    """
    # Create the test directory if it doesn't exist
    if not os.path.exists(TEST_CHAT_LOG_DIR):
        os.makedirs(TEST_CHAT_LOG_DIR)

    yield TEST_CHAT_LOG_DIR # Provide the path to the test

    # Teardown: Remove the test directory and its contents
    if os.path.exists(TEST_CHAT_LOG_DIR):
        shutil.rmtree(TEST_CHAT_LOG_DIR)

def test_create_chat_log_file_creates_file_with_headers(managed_test_chat_log_dir):
    """
    Tests if create_chat_log_file correctly creates a CSV file
    with the specified headers in the provided chat_log_dir.
    """
    video_id = "test_video_123"
    test_dir = managed_test_chat_log_dir # Get the directory from the fixture

    # Call the function that creates the file, passing the test-specific directory
    created_filepath = create_chat_log_file(video_id, test_dir)

    # 1. Check if the file was created in the test_dir
    assert os.path.exists(created_filepath), "CSV file was not created."
    assert test_dir in created_filepath, "File created in wrong directory."

    # 2. Verify the filename pattern (somewhat)
    # Filename is chat_log_{video_id}_{timestamp}.csv
    assert f"chat_log_{video_id}_" in os.path.basename(created_filepath)
    assert os.path.basename(created_filepath).endswith(".csv")

    # 3. Check if the CSV file contains the correct headers
    headers_found = []
    with open(created_filepath, 'r', newline='', encoding='utf-8') as file:
        reader = csv.reader(file)
        headers_found = next(reader) # Read the first line (headers)

    expected_headers = ['datetime', 'author', 'message', 'superChat']
    assert headers_found == expected_headers, f"CSV headers are incorrect. Found {headers_found}"

    # 4. Check if the file is initially empty (only headers)
    with open(created_filepath, 'r', newline='', encoding='utf-8') as file:
        reader = csv.reader(file)
        next(reader) # Skip headers
        try:
            next(reader) # Try to read a data row
            assert False, "CSV file should be empty after header creation."
        except StopIteration:
            # This is expected, means no data rows after header
            pass

# To run these tests, navigate to the project root in your terminal and run:
# python -m pytest
# Ensure pytest is installed (pip install pytest) and MONGO_URI is set if config.py is imported by utils.py directly or indirectly in a way that triggers MongoDB connection.
# The current setup with the fixture overriding CHAT_LOG_DIR within utils.py before create_chat_log_file is called should be fine.
# The print statement from config.py related to CHAT_LOG_DIR creation will still run when config is first imported,
# but utils.create_chat_log_file will use the monkeypatched TEST_CHAT_LOG_DIR.
