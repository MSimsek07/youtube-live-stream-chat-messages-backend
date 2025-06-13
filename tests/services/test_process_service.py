import pytest
import os
import signal
from unittest.mock import patch, MagicMock, ANY
from fastapi import HTTPException

# Functions/module to test
from services import process_service

# --- Fixtures ---
@pytest.fixture(autouse=True) # Automatically use this fixture for all tests in this module
def reset_collector_processes_state():
    """Cleans up the global collector_processes dictionary before and after each test."""
    original_processes = process_service.collector_processes.copy()
    process_service.collector_processes.clear()
    yield
    process_service.collector_processes = original_processes # Restore if needed, though usually want clear state

@pytest.fixture
def temp_chat_dir(tmp_path):
    d = tmp_path / "test_process_chat_logs"
    d.mkdir()
    return str(d)

# --- Tests for start_collector_process ---
@patch('subprocess.Popen')
@patch('os.path.exists')
@patch('os.makedirs') # To mock out directory creation attempts for log finding
@patch('os.listdir')   # To mock out listing files for log finding
def test_start_collector_process_success(mock_listdir, mock_makedirs, mock_os_exists, mock_popen, temp_chat_dir):
    video_id = "vid_start_ok"
    mock_os_exists.return_value = True # Assume collector.py exists

    mock_process_instance = MagicMock()
    mock_process_instance.pid = 12345
    mock_popen.return_value = mock_process_instance

    mock_listdir.return_value = [f"chat_log_{video_id}_sometime.csv"] # Simulate a log file found

    result = process_service.start_collector_process(video_id, temp_chat_dir)

    assert result["status"] == "started"
    assert result["pid"] == 12345
    assert result["filename"] is not None
    assert video_id in process_service.collector_processes
    assert process_service.collector_processes[video_id] == 12345

    script_path_expected_1 = os.path.join(os.path.dirname(os.path.abspath(process_service.__file__)), "..", "collector.py")
    # script_path_expected_2 is harder to predict without knowing where test is run from
    # so we check the first attempt is good enough
    mock_os_exists.assert_any_call(script_path_expected_1)
    mock_popen.assert_called_once_with(["python", ANY, video_id]) # ANY for script_path due to complex construction
    mock_listdir.assert_called_once_with(temp_chat_dir)


@patch('os.path.exists', return_value=False) # collector.py does not exist
def test_start_collector_process_script_not_found(mock_os_exists, temp_chat_dir):
    video_id = "vid_script_missing"
    with pytest.raises(HTTPException) as exc_info:
        process_service.start_collector_process(video_id, temp_chat_dir)
    assert exc_info.value.status_code == 500
    assert "collector.py script not found" in exc_info.value.detail


@patch('os.path.exists', return_value=True)
@patch('subprocess.Popen', side_effect=Exception("Popen failed"))
def test_start_collector_process_popen_fails(mock_popen, mock_os_exists, temp_chat_dir):
    video_id = "vid_popen_fail"
    with pytest.raises(HTTPException) as exc_info:
        process_service.start_collector_process(video_id, temp_chat_dir)
    assert exc_info.value.status_code == 500
    assert "Failed to start collector process" in exc_info.value.detail


# --- Tests for stop_collector_process ---
@patch('psutil.Process')
def test_stop_collector_process_success(mock_psutil_process):
    video_id = "vid_stop_ok"
    pid = 12345
    process_service.collector_processes[video_id] = pid

    mock_proc_obj = MagicMock()
    mock_psutil_process.return_value = mock_proc_obj

    result = process_service.stop_collector_process(video_id)

    assert result["status"] == "stopped"
    assert video_id not in process_service.collector_processes
    mock_psutil_process.assert_called_once_with(pid)
    mock_proc_obj.send_signal.assert_called_once_with(signal.SIGINT)
    mock_proc_obj.wait.assert_called_once_with(timeout=5)


def test_stop_collector_process_not_running():
    video_id = "vid_not_running"
    with pytest.raises(HTTPException) as exc_info:
        process_service.stop_collector_process(video_id)
    assert exc_info.value.status_code == 404
    assert "not found or not running" in exc_info.value.detail


@patch('psutil.Process', side_effect=psutil.NoSuchProcess(123))
def test_stop_collector_process_no_such_process(mock_psutil_process):
    video_id = "vid_no_such_proc"
    process_service.collector_processes[video_id] = 123 # Assume it was running

    with pytest.raises(HTTPException) as exc_info:
        process_service.stop_collector_process(video_id)
    assert exc_info.value.status_code == 404 # Service converts NoSuchProcess to 404
    assert "was already stopped or not found" in exc_info.value.detail
    assert video_id not in process_service.collector_processes # Should be cleaned up


@patch('psutil.Process')
def test_stop_collector_process_timeout_and_killed(mock_psutil_process):
    video_id = "vid_timeout"
    pid = 12345
    process_service.collector_processes[video_id] = pid

    mock_proc_obj = MagicMock()
    mock_psutil_process.return_value = mock_proc_obj
    mock_proc_obj.wait.side_effect = [psutil.TimeoutExpired(seconds=5), None] # First wait times out, second (after kill) is fine

    result = process_service.stop_collector_process(video_id)

    assert result["status"] == "killed"
    assert "forcefully killed" in result["detail"]
    assert video_id not in process_service.collector_processes
    mock_proc_obj.send_signal.assert_called_once_with(signal.SIGINT)
    mock_proc_obj.kill.assert_called_once()
    assert mock_proc_obj.wait.call_count == 2


@patch('psutil.Process')
def test_stop_collector_process_timeout_kill_fails_no_such_process(mock_psutil_process):
    video_id = "vid_timeout_kill_fail_nsp"
    pid = 12345
    process_service.collector_processes[video_id] = pid

    mock_proc_obj = MagicMock()
    mock_psutil_process.return_value = mock_proc_obj
    mock_proc_obj.wait.side_effect = psutil.TimeoutExpired(seconds=5)
    mock_proc_obj.kill.side_effect = psutil.NoSuchProcess(pid) # Process dies before kill completes

    with pytest.raises(HTTPException) as exc_info:
        process_service.stop_collector_process(video_id)
    assert exc_info.value.status_code == 404
    assert "disappeared during kill attempt" in exc_info.value.detail
    assert video_id not in process_service.collector_processes


@patch('psutil.Process')
def test_stop_collector_process_timeout_kill_fails_other_exception(mock_psutil_process):
    video_id = "vid_timeout_kill_fail_other"
    pid = 12345
    process_service.collector_processes[video_id] = pid

    mock_proc_obj = MagicMock()
    mock_psutil_process.return_value = mock_proc_obj
    mock_proc_obj.wait.side_effect = psutil.TimeoutExpired(seconds=5)
    mock_proc_obj.kill.side_effect = RuntimeError("Kill error")

    with pytest.raises(HTTPException) as exc_info:
        process_service.stop_collector_process(video_id)
    assert exc_info.value.status_code == 500
    assert "Error forcefully stopping process" in exc_info.value.detail
    # In this specific error case, the PID might remain in collector_processes
    # depending on the desired robustness vs. cleanup. The current code
    # does not remove it if kill() itself raises an unexpected error.
    assert video_id in process_service.collector_processes


# --- Test for get_running_processes ---
def test_get_running_processes():
    process_service.collector_processes = {"vid1": 123, "vid2": 456}
    assert process_service.get_running_processes() == {"vid1": 123, "vid2": 456}
    # Ensure it's a copy
    assert process_service.get_running_processes() is not process_service.collector_processes
