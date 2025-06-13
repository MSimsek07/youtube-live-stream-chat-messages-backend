import pytest
import os
import csv
from unittest import mock
from unittest.mock import MagicMock, patch
from fastapi import HTTPException

# Functions to test
from services import chat_data_service

# --- Fixtures ---
@pytest.fixture
def mock_db_client():
    """Provides a MagicMock for the database client."""
    return MagicMock()

@pytest.fixture
def temp_chat_log_dir(tmp_path):
    """Creates a temporary chat log directory for tests."""
    d = tmp_path / "test_chat_logs"
    d.mkdir()
    return str(d)

# --- Tests for list_log_files ---
def test_list_log_files_empty(temp_chat_log_dir):
    with patch('os.listdir', return_value=[]):
        assert chat_data_service.list_log_files(temp_chat_log_dir) == []

def test_list_log_files_with_files(temp_chat_log_dir):
    mock_files = ["chat_log_video1.csv", "other_file.txt", "chat_log_video2.csv"]
    expected_files = ["chat_log_video1.csv", "chat_log_video2.csv"]
    with patch('os.listdir', return_value=mock_files):
        assert chat_data_service.list_log_files(temp_chat_log_dir) == expected_files

def test_list_log_files_os_error(temp_chat_log_dir):
    with patch('os.listdir', side_effect=OSError("Test OS error")):
        # Should return empty list and print error (not easily testable for print without more setup)
        assert chat_data_service.list_log_files(temp_chat_log_dir) == []


# --- Tests for get_log_file_messages ---
def test_get_log_file_messages_success(temp_chat_log_dir):
    filename = "test_log.csv"
    filepath = os.path.join(temp_chat_log_dir, filename)
    # Create a dummy CSV file
    with open(filepath, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['datetime', 'author', 'message', 'superChat'])
        writer.writerow(['2023-01-01 10:00:00', 'UserA', 'Hello', ''])
        writer.writerow(['2023-01-01 10:00:05', 'UserB', 'Hi there', '$1.00'])

    result = chat_data_service.get_log_file_messages(filename, temp_chat_log_dir)
    assert len(result['messages']) == 2
    assert result['messages'][0]['author'] == 'UserA'
    assert result['messages'][1]['superChat'] == '$1.00'

def test_get_log_file_messages_not_found(temp_chat_log_dir):
    with pytest.raises(HTTPException) as exc_info:
        chat_data_service.get_log_file_messages("non_existent.csv", temp_chat_log_dir)
    assert exc_info.value.status_code == 404

def test_get_log_file_messages_read_error(temp_chat_log_dir):
    filename = "error_log.csv"
    filepath = os.path.join(temp_chat_log_dir, filename)
    with open(filepath, 'w') as f: # Create file but maybe make it unreadable or bad format
        f.write("this is not a csv")

    # This specific setup won't make csv.reader fail in a way that causes an Exception
    # that isn't already handled by Python's file reading.
    # A more direct way to test the generic Exception catch:
    with patch('csv.reader', side_effect=Exception("CSV Read Error")):
        with pytest.raises(HTTPException) as exc_info:
            chat_data_service.get_log_file_messages(filename, temp_chat_log_dir)
        assert exc_info.value.status_code == 500
        assert "Error reading file" in exc_info.value.detail


# --- Tests for get_db_messages ---
def test_get_db_messages_success(mock_db_client):
    video_id = "vid1"
    mock_collection = MagicMock()
    mock_db_client.__getitem__.return_value = mock_collection
    mock_messages = [{"author": "A", "message": "Msg1"}, {"author": "B", "message": "Msg2"}]
    mock_collection.find.return_value = mock_messages # find returns a cursor-like object, list() is called on it

    result = chat_data_service.get_db_messages(video_id, mock_db_client)
    assert result == {"messages": mock_messages}
    mock_db_client.__getitem__.assert_called_once_with(f"messages_{video_id}")
    mock_collection.find.assert_called_once_with({}, {"_id": 0})

def test_get_db_messages_db_error(mock_db_client):
    video_id = "vid_err"
    mock_collection = MagicMock()
    mock_db_client.__getitem__.return_value = mock_collection
    mock_collection.find.side_effect = Exception("DB Connection Error")

    with pytest.raises(HTTPException) as exc_info:
        chat_data_service.get_db_messages(video_id, mock_db_client)
    assert exc_info.value.status_code == 500
    assert "Error fetching messages from database" in exc_info.value.detail


# --- Tests for _get_latest_chat_log_file_path (internal helper) ---
# We test this indirectly via services that use it, or directly if made public
# For this example, let's test it directly for clarity, though it's an internal function.
def test_get_latest_chat_log_file_path_success(temp_chat_log_dir):
    video_id = "vid_latest"
    # Create some dummy files with different timestamps
    path1 = os.path.join(temp_chat_log_dir, f"chat_log_{video_id}_20230101_100000.csv")
    path2 = os.path.join(temp_chat_log_dir, f"chat_log_{video_id}_20230101_120000.csv") # newest
    path3 = os.path.join(temp_chat_log_dir, f"chat_log_{video_id}_20230101_080000.csv")
    open(path1, 'w').close()
    open(path2, 'w').close()
    open(path3, 'w').close()
    # Adjust ctime to ensure recency matches filename for this test
    os.utime(path1, (os.path.getatime(path1), os.path.getmtime(path1) - 100))
    os.utime(path3, (os.path.getatime(path3), os.path.getmtime(path3) - 200))

    # Ensure the ctime of path2 is the latest
    # This part of the test is a bit fragile due to relying on filesystem time manipulation
    # A better mock would involve patching os.listdir and os.path.getctime

    with patch('os.listdir') as mock_listdir, \
         patch('os.path.getctime') as mock_getctime:

        mock_listdir.return_value = [os.path.basename(path1), os.path.basename(path2), os.path.basename(path3)]

        def ctime_side_effect(p):
            if p == path1: return 100
            if p == path2: return 300 # Newest
            if p == path3: return 50
            return 0
        mock_getctime.side_effect = ctime_side_effect

        latest_path = chat_data_service._get_latest_chat_log_file_path(video_id, temp_chat_log_dir)
        assert latest_path == path2

def test_get_latest_chat_log_file_path_no_files(temp_chat_log_dir):
    assert chat_data_service._get_latest_chat_log_file_path("vid_none", temp_chat_log_dir) is None

# --- Tests for import_csv_to_db ---
# This is complex, will mock dependencies heavily.
@patch('services.chat_data_service._get_latest_chat_log_file_path')
def test_import_csv_to_db_no_file(mock_get_latest_path, mock_db_client, temp_chat_log_dir):
    mock_get_latest_path.return_value = None
    with pytest.raises(HTTPException) as exc_info:
        chat_data_service.import_csv_to_db("vid_import_nofile", mock_db_client, temp_chat_log_dir)
    assert exc_info.value.status_code == 404
    mock_get_latest_path.assert_called_once_with("vid_import_nofile", temp_chat_log_dir)

@patch('services.chat_data_service._get_latest_chat_log_file_path')
@patch('builtins.open', new_callable=mock.mock_open)
@patch('csv.reader')
def test_import_csv_to_db_success_new_messages(
    mock_csv_reader, mock_open, mock_get_latest_path, mock_db_client, temp_chat_log_dir
):
    video_id = "vid_import_new"
    mock_log_path = os.path.join(temp_chat_log_dir, "fake_log.csv")
    mock_get_latest_path.return_value = mock_log_path

    # CSV data: header, then two new messages
    mock_csv_reader.return_value = iter([
        ['datetime', 'author', 'message', 'superChat'],
        ['2023-01-01 10:00:00', 'UserA', 'Msg1', ''],
        ['2023-01-01 10:00:05', 'UserB', 'Msg2', '$2']
    ])

    mock_collection = MagicMock()
    mock_db_client.__getitem__.return_value = mock_collection
    mock_collection.find_one.return_value = None # Simulate no duplicates

    result = chat_data_service.import_csv_to_db(video_id, mock_db_client, temp_chat_log_dir)

    assert result["inserted_count"] == 2
    assert mock_collection.insert_one.call_count == 2
    expected_call_1 = {
        "video_id": video_id, "datetime": "2023-01-01 10:00:00",
        "author": "UserA", "message": "Msg1", "superChat": ""
    }
    expected_call_2 = {
        "video_id": video_id, "datetime": "2023-01-01 10:00:05",
        "author": "UserB", "message": "Msg2", "superChat": "$2"
    }
    mock_collection.insert_one.assert_any_call(expected_call_1)
    mock_collection.insert_one.assert_any_call(expected_call_2)


# --- Tests for get_latest_csv_messages ---
@patch('services.chat_data_service._get_latest_chat_log_file_path')
@patch('builtins.open', new_callable=mock.mock_open)
@patch('csv.reader')
def test_get_latest_csv_messages_success(
    mock_csv_reader, mock_open, mock_get_latest_path, temp_chat_log_dir
):
    video_id = "vid_latest_csv"
    mock_log_path = os.path.join(temp_chat_log_dir, "latest_fake.csv")
    mock_get_latest_path.return_value = mock_log_path

    mock_csv_reader.return_value = iter([
        ['datetime', 'author', 'message', 'superChat'],
        ['2023-01-01 10:00:00', 'UserX', 'Hello CSV', ''],
        ['2023-01-01 10:00:05', 'UserY', 'Superchat here', '$5.55']
    ])

    result = chat_data_service.get_latest_csv_messages(video_id, temp_chat_log_dir)
    assert len(result['messages']) == 2
    assert result['messages'][0]['author'] == 'UserX'
    assert result['messages'][0]['timestamp'] > 0 # Check timestamp was added
    assert result['messages'][1]['superChat'] == '$5.55'
    assert result['messages'][1]['video_id'] == video_id


# --- Tests for analyze_video_messages ---
def test_analyze_video_messages_success(mock_db_client):
    video_id = "vid_analyze"
    mock_collection = MagicMock()
    mock_db_client.__getitem__.return_value = mock_collection
    mock_collection.count_documents.return_value = 42

    result = chat_data_service.analyze_video_messages(video_id, mock_db_client)
    assert result["video_id"] == video_id
    assert result["message_count"] == 42
    assert "Placeholder" in result["analysis_status"]
    mock_collection.count_documents.assert_called_once_with({})

def test_analyze_video_messages_db_error(mock_db_client):
    video_id = "vid_analyze_err"
    mock_collection = MagicMock()
    mock_db_client.__getitem__.return_value = mock_collection
    mock_collection.count_documents.side_effect = Exception("DB Count Error")

    with pytest.raises(HTTPException) as exc_info:
        chat_data_service.analyze_video_messages(video_id, mock_db_client)
    assert exc_info.value.status_code == 500
    assert "Error analyzing messages" in exc_info.value.detail
