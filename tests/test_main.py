import pytest
from fastapi.testclient import TestClient
from main import app # Assuming your FastAPI app instance is named 'app' in main.py
import os # Keep os for path manipulation if needed, but CHAT_LOG_DIR_TEST might not be necessary
from unittest.mock import patch, MagicMock
from fastapi import HTTPException # To test for raised HTTPExceptions

client = TestClient(app)

# CHAT_LOG_DIR from config is now passed as a dependency to services.
# Tests for endpoints will mock the service calls, so direct interaction
# with CHAT_LOG_DIR_TEST by main.py is less of a concern.
# We can remove CHAT_LOG_DIR_TEST if no test directly causes main.py to use it.
# For now, let's comment it out as it's not used by the updated tests.
# CHAT_LOG_DIR_TEST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "chat_csv_files")
# if not os.path.exists(CHAT_LOG_DIR_TEST):
#     os.makedirs(CHAT_LOG_DIR_TEST)

def test_read_main_root_should_return_not_found():
    """
    The root path isn't defined, so it should return 404.
    This is a basic test to ensure the TestClient is working.
    """
    response = client.get("/")
    assert response.status_code == 404

# Updated tests for /chat_logs
@patch('services.chat_data_service.list_log_files')
def test_list_chat_logs_empty(mock_list_log_files):
    """
    Test the /chat_logs endpoint when the service returns an empty list.
    """
    mock_list_log_files.return_value = []

    response = client.get("/chat_logs")
    assert response.status_code == 200
    assert response.json() == []
    mock_list_log_files.assert_called_once() # CHAT_LOG_DIR is passed from main

@patch('services.chat_data_service.list_log_files')
def test_list_chat_logs_with_files(mock_list_log_files):
    """
    Test the /chat_logs endpoint when the service returns a list of files.
    """
    mock_files = ["chat_log_video1.csv", "chat_log_video2.csv"]
    mock_list_log_files.return_value = mock_files

    response = client.get("/chat_logs")
    assert response.status_code == 200
    assert response.json() == mock_files
    mock_list_log_files.assert_called_once()

# Tests for /start_chat/{video_id}
# The following two tests are redundant due to improved CHAT_LOG_DIR handling in the subsequent tests.
# @patch('services.process_service.start_collector_process')
# def test_start_chat_collection_success(mock_start_collector):
#     video_id = "testvideo123"
#     expected_response = {"status": "started", "pid": 12345, "filename": f"chat_log_{video_id}_timestamp.csv"}
#     mock_start_collector.return_value = expected_response

#     response = client.post(f"/start_chat/{video_id}")
#     assert response.status_code == 200
#     assert response.json() == expected_response
#     # This assertion for chat_log_dir was problematic
#     # mock_start_collector.assert_called_once_with(video_id, chat_log_dir=app.dependency_overrides.get('CHAT_LOG_DIR', None) or os.environ.get('CHAT_LOG_DIR_FROM_CONFIG_NOT_ACCESSIBLE_DIRECTLY_IN_TEST_UNLESS_CONFIG_IS_IMPORTED_AND_USED_FOR_DEFAULT'))

# @patch('services.process_service.start_collector_process')
# def test_start_chat_collection_service_error(mock_start_collector):
#     video_id = "testvideo_error"
#     mock_start_collector.side_effect = HTTPException(status_code=500, detail="Failed to start collector")

#     response = client.post(f"/start_chat/{video_id}")
#     assert response.status_code == 500
#     assert response.json() == {"detail": "Failed to start collector"}
#     # This assertion for chat_log_dir was problematic
#     # mock_start_collector.assert_called_once_with(video_id, chat_log_dir=app.dependency_overrides.get('CHAT_LOG_DIR', None) or os.environ.get('CHAT_LOG_DIR_FROM_CONFIG_NOT_ACCESSIBLE_DIRECTLY_IN_TEST_UNLESS_CONFIG_IS_IMPORTED_AND_USED_FOR_DEFAULT'))

# Tests for /stop_chat/{video_id}
@patch('services.process_service.stop_collector_process')
def test_stop_chat_collection_success(mock_stop_collector):
    video_id = "testvideo123"
    expected_response = {"status": "stopped", "video_id": video_id}
    mock_stop_collector.return_value = expected_response

    response = client.post(f"/stop_chat/{video_id}")
    assert response.status_code == 200
    assert response.json() == expected_response
    mock_stop_collector.assert_called_once_with(video_id)

@patch('services.process_service.stop_collector_process')
def test_stop_chat_collection_not_found(mock_stop_collector):
    video_id = "testvideo_notfound"
    mock_stop_collector.side_effect = HTTPException(status_code=404, detail=f"Collector process for video_id '{video_id}' not found or not running.")

    response = client.post(f"/stop_chat/{video_id}")
    assert response.status_code == 404
    assert response.json() == {"detail": f"Collector process for video_id '{video_id}' not found or not running."}
    mock_stop_collector.assert_called_once_with(video_id)

@patch('services.process_service.stop_collector_process')
def test_stop_chat_collection_service_error(mock_stop_collector):
    video_id = "testvideo_error_stop"
    mock_stop_collector.side_effect = HTTPException(status_code=500, detail="Error stopping collector")

    response = client.post(f"/stop_chat/{video_id}")
    assert response.status_code == 500
    assert response.json() == {"detail": "Error stopping collector"}
    mock_stop_collector.assert_called_once_with(video_id)

# Placeholder for CHAT_LOG_DIR used in assertions.
# This ideally should come from how main.py gets its config for consistency.
# Since main.py imports CHAT_LOG_DIR from config, we might need to import config here too for the assertion.
try:
    from config import CHAT_LOG_DIR as ACTUAL_CHAT_LOG_DIR
except ImportError: # Should not happen if project structure is correct
    ACTUAL_CHAT_LOG_DIR = "chat_csv_files" # Fallback, less ideal

# Need to adjust the CHAT_LOG_DIR assertion in start_collector_process mock calls
# The app.dependency_overrides.get('CHAT_LOG_DIR', None) is not how FastAPI handles this.
# FastAPI injects dependencies from global scope or defined providers.
# For testing, if main.py uses 'from config import CHAT_LOG_DIR', then the mock_start_collector
# will be called with that value. So, we should assert with that value.

@patch('services.process_service.start_collector_process')
def test_start_chat_collection_success_with_correct_chat_log_dir(mock_start_collector):
    video_id = "testvideo123"
    expected_response = {"status": "started", "pid": 12345, "filename": f"chat_log_{video_id}_timestamp.csv"}
    mock_start_collector.return_value = expected_response

    response = client.post(f"/start_chat/{video_id}")
    assert response.status_code == 200
    assert response.json() == expected_response
    # Assert that the service function was called with the CHAT_LOG_DIR from config
    mock_start_collector.assert_called_once_with(video_id, chat_log_dir=ACTUAL_CHAT_LOG_DIR)


@patch('services.process_service.start_collector_process')
def test_start_chat_collection_service_error_with_correct_chat_log_dir(mock_start_collector):
    video_id = "testvideo_error"
    mock_start_collector.side_effect = HTTPException(status_code=500, detail="Failed to start collector")

    response = client.post(f"/start_chat/{video_id}")
    assert response.status_code == 500
    assert response.json() == {"detail": "Failed to start collector"}
    mock_start_collector.assert_called_once_with(video_id, chat_log_dir=ACTUAL_CHAT_LOG_DIR)

# TODO: Add tests for other data endpoints, mocking services.chat_data_service functions:
# - /chat_log/{filename} -> services.chat_data_service.get_log_file_messages
# - /messages/{video_id} -> services.chat_data_service.get_db_messages
# - /analyze/{video_id} -> services.chat_data_service.analyze_video_messages
# - /chat_log_messages/{video_id} -> services.chat_data_service.get_latest_csv_messages
# - /import_csv_to_mongo/{video_id} -> services.chat_data_service.import_csv_to_db
