import pytest
import csv
from unittest import mock # For mock_open and other mocks
from unittest.mock import MagicMock, patch

# Service to test
from services.message_writer_service import MessageWriterService
# For type hinting and potentially direct use if not mocking all dependencies
from config import db as actual_db_client
# utils.create_chat_log_file is a direct dependency of the service's __init__

@patch('utils.create_chat_log_file') # Mock the utility function
def test_message_writer_service_init(mock_create_chat_log_file):
    """
    Test the __init__ method of MessageWriterService.
    Ensures create_chat_log_file is called and MongoDB collection is accessed.
    """
    video_id = "test_video_init"
    test_chat_dir = "/tmp/test_chat_dir"
    mock_csv_filepath = f"{test_chat_dir}/chat_log_{video_id}_timestamp.csv"

    mock_create_chat_log_file.return_value = mock_csv_filepath

    mock_db = MagicMock() # Mock the database client

    writer_service = MessageWriterService(video_id, mock_db, test_chat_dir)

    # Assert that create_chat_log_file was called correctly
    mock_create_chat_log_file.assert_called_once_with(video_id, test_chat_dir)
    assert writer_service.csv_filepath == mock_csv_filepath

    # Assert that the MongoDB collection was accessed correctly
    expected_collection_name = f"messages_{video_id}"
    mock_db.__getitem__.assert_called_once_with(expected_collection_name)
    assert writer_service.mongo_collection_name == expected_collection_name


@patch('utils.create_chat_log_file') # Keep create_chat_log_file mocked for init
@patch('builtins.open', new_callable=mock.mock_open) # Mock the open function for CSV writing
def test_message_writer_service_write_message(mock_open_file, mock_create_chat_log_file):
    """
    Test the write_message method of MessageWriterService.
    Ensures that messages are written to CSV and MongoDB.
    """
    video_id = "test_video_write"
    test_chat_dir = "/tmp/test_chat_write_dir"
    mock_csv_filepath = f"{test_chat_dir}/chat_log_{video_id}_timestamp.csv"

    mock_create_chat_log_file.return_value = mock_csv_filepath # For __init__

    mock_db = MagicMock()
    mock_collection = MagicMock()
    mock_db.__getitem__.return_value = mock_collection # db['collection_name'] will return mock_collection

    # Instantiate the service
    writer_service = MessageWriterService(video_id, mock_db, test_chat_dir)

    # Sample message data
    sample_message = {
        "video_id": video_id, # video_id is usually added by the service if not present
        "datetime": "2023-01-01 12:00:00",
        "author": "TestAuthor",
        "message": "Hello, world!",
        "superChat": "$5.00"
    }

    # Call the method to test
    writer_service.write_message(sample_message)

    # 1. Test CSV writing
    # Assert that open was called correctly (for appending to the CSV)
    mock_open_file.assert_called_once_with(mock_csv_filepath, 'a', newline='', encoding='utf-8')

    # To assert on csv.writer().writerow(), we need to mock csv.writer
    # This can get complex if not done carefully.
    # For simplicity, we're checking if 'open' was called, implying an attempt to write.
    # A more thorough test would involve:
    # with patch('csv.writer') as mock_csv_writer_constructor:
    #     mock_writer_instance = MagicMock()
    #     mock_csv_writer_constructor.return_value = mock_writer_instance
    #     writer_service.write_message(sample_message)
    #     mock_writer_instance.writerow.assert_called_once_with([...])

    # 2. Test MongoDB writing
    # Assert that insert_one was called on the mock collection with the sample message
    mock_collection.insert_one.assert_called_once_with(sample_message)

    # Test message_data without video_id initially (service should add it)
    mock_collection.reset_mock() # Reset mock for the next call
    sample_message_no_vid = {
        "datetime": "2023-01-01 12:00:01",
        "author": "TestAuthor2",
        "message": "Another message",
        "superChat": None
    }
    expected_message_with_vid = sample_message_no_vid.copy()
    expected_message_with_vid["video_id"] = video_id

    # We need to reset mock_open_file if it's expected to be called again
    # For multiple calls to write_message, open is called each time.
    mock_open_file.reset_mock()

    writer_service.write_message(sample_message_no_vid)
    mock_open_file.assert_called_once_with(mock_csv_filepath, 'a', newline='', encoding='utf-8')
    mock_collection.insert_one.assert_called_once_with(expected_message_with_vid)


def test_get_csv_filepath(tmp_path): # Use pytest's tmp_path fixture for a temporary directory
    """ Test the get_csv_filepath method """
    video_id = "test_video_path"
    # Use tmp_path for a clean testing environment for file creation
    test_dir = str(tmp_path / "test_chat_files")

    # We don't need to mock create_chat_log_file if we want to test its integration here
    # but the service calls it in __init__. For this unit test of get_csv_filepath,
    # it's simpler to ensure __init__ can run without side effects or mock create_chat_log_file.
    with patch('utils.create_chat_log_file') as mock_create_chat_log_file_for_path:
        expected_path = os.path.join(test_dir, f"chat_log_{video_id}_dummy.csv")
        mock_create_chat_log_file_for_path.return_value = expected_path

        mock_db = MagicMock()
        service = MessageWriterService(video_id, mock_db, test_dir)

        assert service.get_csv_filepath() == expected_path
        mock_create_chat_log_file_for_path.assert_called_once_with(video_id, test_dir)

# Note: Testing the CSV writer part with mock_open can be tricky due to context managers.
# The above test for write_message primarily checks if 'open' is called and if the DB call is made.
# More robust CSV testing might involve checking the content of a BytesIO stream if 'open' is
# patched to return such a stream, or by allowing the file to be written in a temp dir and reading it back.
# For this exercise, the current level of mocking is a starting point.
