import subprocess
import os
import signal
import psutil
from fastapi import HTTPException # Import HTTPException
# CHAT_LOG_DIR will be passed as an argument

# This dictionary will store the PIDs of running collector processes.
# Key: video_id (str), Value: PID (int)
collector_processes = {}

def start_collector_process(video_id: str, chat_log_dir: str) -> dict:
    """
    Launches the collector.py script as a subprocess for the given video_id.
    Manages the collector_processes dictionary.
    Uses the provided chat_log_dir to find the latest log file.
    """
    if video_id in collector_processes:
        # Optionally, handle cases where collection is already running
        # For now, let's assume we can try to start another or this is an error
        # Depending on desired behavior, one might return an error or stop the old one.
        print(f"Warning: Collector process for {video_id} may already be running or was not cleaned up.")

    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "collector.py")

    # Ensure the script path is correct relative to this service file
    if not os.path.exists(script_path):
        # Attempt to find collector.py relative to the project root if started from elsewhere
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        script_path_alt = os.path.join(project_root, "collector.py")
        if os.path.exists(script_path_alt):
            script_path = script_path_alt
        else:
            raise HTTPException(status_code=500, detail=f"collector.py script not found at expected locations: {script_path} or {script_path_alt}")

    try:
        proc = subprocess.Popen(["python", script_path, video_id])
        collector_processes[video_id] = proc.pid
    except Exception as e:
        # Log the full error server-side for debugging
        print(f"Critical error starting collector process for {video_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start collector process for {video_id}. Reason: {str(e)}")

    # Try to find the latest log file created by the collector.
    # This logic might be a bit racy if the collector takes time to create the file.
    # Consider if the collector script itself should report the filename upon successful start.
    # The collector.py itself now depends on MessageWriterService which creates the file,
    # so the file should exist shortly after Popen if collector.py starts quickly.
    try:
        # Ensure chat_log_dir exists before listing (though config.py should handle initial creation)
        os.makedirs(chat_log_dir, exist_ok=True)
        files = [f for f in os.listdir(chat_log_dir) if f.startswith(f"chat_log_{video_id}_") and f.endswith(".csv")]
        if files: # Check if files list is not empty
            latest_file = max(files, key=lambda f: os.path.getctime(os.path.join(chat_log_dir, f)))
        else:
            latest_file = None
    except FileNotFoundError: # Should be less likely if os.makedirs is called
        print(f"Warning: chat_log_dir {chat_log_dir} not found during latest file check.")
        latest_file = None
    except Exception as e: # Other potential errors listing files
        print(f"Error finding latest log file for {video_id} in {chat_log_dir}: {e}")
        latest_file = None

    return {"status": "started", "pid": proc.pid, "filename": latest_file}

def stop_collector_process(video_id: str) -> dict:
    """
    Stops the collector.py subprocess for the given video_id.
    Manages the collector_processes dictionary.
    """
    pid = collector_processes.get(video_id)
    if not pid:
        raise HTTPException(status_code=404, detail=f"Collector process for video_id '{video_id}' not found or not running.")

    try:
        p = psutil.Process(pid)
        p.send_signal(signal.SIGINT)  # Send SIGINT for graceful shutdown
        p.wait(timeout=5)  # Wait for the process to terminate

        # Successfully terminated
        if video_id in collector_processes: # Ensure key exists before deleting
            del collector_processes[video_id]
        return {"status": "stopped", "video_id": video_id}

    except psutil.NoSuchProcess:
        # Process was already gone
        if video_id in collector_processes:
            del collector_processes[video_id]
        # This is effectively a "not found" or "already stopped" situation.
        # Re-raising as 404 is consistent with it not being actively running.
        raise HTTPException(status_code=404, detail=f"Collector process for video_id '{video_id}' (PID {pid}) was already stopped or not found.")

    except psutil.TimeoutExpired:
        print(f"Process {pid} for {video_id} did not terminate gracefully, attempting to kill.")
        try:
            p.kill()
            p.wait(timeout=2) # Shorter wait for kill
            if video_id in collector_processes:
                del collector_processes[video_id]
            return {"status": "killed", "detail": f"Process for video_id '{video_id}' (PID {pid}) timed out on SIGINT and was forcefully killed."}
        except psutil.NoSuchProcess: # Process died during kill attempt
            if video_id in collector_processes:
                del collector_processes[video_id]
            raise HTTPException(status_code=404, detail=f"Collector process for video_id '{video_id}' (PID {pid}) disappeared during kill attempt.")
        except Exception as e_kill:
            # Error during the kill attempt itself
            # Log e_kill for server-side diagnostics
            print(f"Error during forceful kill of process {pid} for {video_id}: {e_kill}")
            raise HTTPException(status_code=500, detail=f"Error forcefully stopping process for video_id '{video_id}'. PID: {pid}. Reason: {str(e_kill)}")

    except Exception as e:
        # Other unexpected errors (e.g., permission issues with psutil)
        print(f"Unexpected error when trying to stop process {pid} for {video_id}: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred while stopping collector for video_id '{video_id}'. PID: {pid}. Reason: {str(e)}")

def get_running_processes() -> dict:
    """Returns a copy of the collector_processes dictionary."""
    return dict(collector_processes)
