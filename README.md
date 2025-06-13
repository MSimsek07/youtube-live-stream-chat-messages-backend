# YouTube Live Chat Collector & Analyzer

This project provides tools to collect live chat messages from YouTube video streams and store them for analysis. It consists of a Python script (`collector.py`) for fetching and storing messages, and a FastAPI backend (`main.py`) to manage collection and expose chat data via an API. Chat messages are stored in both CSV files and a MongoDB database. The backend is designed with a service layer to separate concerns, making the API handlers lean and business logic more modular and testable.

## Features

*   Collects live chat messages from any public YouTube video stream.
*   Stores messages in CSV files (in `chat_csv_files/`) and a MongoDB database.
*   FastAPI backend to start/stop collection and retrieve chat data.
*   Configurable CORS policy for the API.

## Project Structure

```
.
├── chat_csv_files/     # Directory for CSV chat logs (gitignored by default)
├── collector.py        # Script to collect chat messages
├── main.py             # FastAPI backend application (API layer)
├── services/           # Business logic layer
│   ├── __init__.py
│   ├── chat_data_service.py    # Service for chat data operations (CSV, MongoDB)
│   ├── message_writer_service.py # Service for writing messages (used by collector.py)
│   └── process_service.py      # Service for managing collector subprocesses
├── utils.py            # Utility functions (e.g., creating chat log files)
├── config.py           # Configuration settings (MongoDB URI, paths)
├── tests/              # Unit and integration tests
│   ├── __init__.py
│   ├── services/       # Service layer tests
│   │   ├── __init__.py
│   │   ├── test_chat_data_service.py
│   │   ├── test_message_writer_service.py
│   │   └── test_process_service.py
│   ├── test_main.py    # API layer tests
│   └── test_utils.py   # Utility function tests
├── requirements.txt    # Python dependencies
├── README.md           # This file
└── .gitignore          # Specifies intentionally untracked files
```

## Setup Instructions

### 1. Clone the Repository

```bash
git clone <repository_url>
cd <repository_directory>
```

### 2. Create and Activate a Virtual Environment

It's highly recommended to use a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Set Environment Variables

This application requires a MongoDB connection URI. You also need to configure allowed origins for the API. Create a file named `.env` in the project root (it will be ignored by git) or set these environment variables in your system:

```
MONGO_URI="your_mongodb_connection_string"
ALLOWED_ORIGINS="http://localhost:3000,http://your.frontend.domain.com" # Optional: comma-separated list of allowed frontend origins
```

*   **`MONGO_URI`**: Your MongoDB connection string.
    *   Example: `mongodb+srv://<username>:<password>@<cluster-url>/<database_name>?retryWrites=true&w=majority`
*   **`ALLOWED_ORIGINS`**: A comma-separated list of origins that are allowed to make requests to the FastAPI backend. If not set, no cross-origin requests will be allowed by default. For local development with a frontend on port 3000, you might set it to `http://localhost:3000`.

**Important Security Note:** The previous version of this code contained a default MongoDB URI with credentials. If you ever used or saw these credentials (`developer_mu:2kGjFiHrnTXOLsRe`), please ensure they are changed or the user/database is secured immediately, as they were publicly visible. Always use strong, unique credentials for your database and manage them securely via environment variables.

### 5. Initialize `chat_csv_files` Directory
The `config.py` script will attempt to create the `chat_csv_files` directory if it doesn't exist when the application starts.

## Running the Application

### Collecting Chat Messages (`collector.py`)

The `collector.py` script is used to fetch chat messages for a specific YouTube video ID.

```bash
python collector.py <youtube_video_id>
```

*   Replace `<youtube_video_id>` with the actual ID of the YouTube video (e.g., `dQw4w9WgXcQ`).
*   Messages will be printed to the console and saved to a CSV file in `chat_csv_files/` and to the MongoDB database.
*   Press `Ctrl+C` to stop the collector.

### Running the FastAPI Backend (`main.py`)

The FastAPI backend provides an API to manage chat collection and access data.

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

*   The API will be available at `http://localhost:8000`.
*   You can access the auto-generated API documentation at `http://localhost:8000/docs`.

## Running Tests

To run the automated tests:

1.  Ensure you have installed the development dependencies (including `pytest` and `httpx`), which are listed in `requirements.txt`:
    ```bash
    pip install -r requirements.txt
    ```
2.  Make sure the `MONGO_URI` environment variable is set, as some tests that involve service initialization (which might import `config.py`) could attempt a MongoDB connection. For tests that mock external services (like database interactions), this might not be strictly necessary, but it's good practice for a consistent test environment.
3.  Navigate to the project root directory in your terminal.
4.  Run pytest:
    ```bash
    python -m pytest
    ```
    or simply:
    ```bash
    pytest
    ```

## API Endpoints

The following are the main API endpoints provided by `main.py`:

*   **`POST /start_chat/{video_id}`**: Starts collecting chat messages for the given `video_id`.
    *   Launches `collector.py` as a background subprocess.
    *   Returns: `{"status": "started", "filename": "chat_log_VIDEOID_TIMESTAMP.csv"}`
*   **`POST /stop_chat/{video_id}`**: Stops chat collection for the given `video_id`.
    *   Terminates the corresponding `collector.py` subprocess.
    *   Returns: `{"status": "stopped"}` or `{"status": "not running"}`
*   **`GET /chat_logs`**: Lists all available CSV chat log files.
    *   Returns: `["chat_log_VIDEOID_TIMESTAMP_1.csv", ...]`
*   **`GET /chat_log/{filename}`**: Retrieves messages from a specific CSV chat log file.
    *   Returns: `{"messages": [{"datetime": "...", "author": "...", "message": "...", "superChat": "..."}]}`
*   **`GET /messages/{video_id}`**: Retrieves all messages for a `video_id` from MongoDB.
    *   Returns: `{"messages": [{"video_id": "...", "datetime": "...", "author": "...", "message": "...", "superChat": "..."}]}`
*   **`POST /import_csv_to_mongo/{video_id}`**: Imports messages from the latest CSV for a `video_id` into MongoDB (skips duplicates).
    *   Returns: `{"inserted": COUNT, "message": "Imported COUNT new messages to MongoDB."}`
*   **`GET /chat_log_messages/{video_id}`**: Retrieves all messages from the latest chat log CSV file for a `video_id` as JSON, including a numeric timestamp.
    *   Returns: `{"messages": [{"datetime": "...", "author": "...", "message": "...", "superChat": "...", "video_id": "...", "timestamp": 167...}]}`

*(Placeholder: `POST /analyze/{video_id}` endpoint exists but currently returns a placeholder message.)*

## MongoDB Schema

Chat messages are stored in MongoDB collections named `messages_<video_id>`. Each document in the collection represents a single chat message and has the following structure:

```json
{
  "video_id": "string",    // YouTube video ID
  "datetime": "string",    // Timestamp of the message (e.g., "2023-10-27 10:30:00")
  "author": "string",      // Author's name
  "message": "string",     // Chat message content
  "superChat": "string"    // SuperChat amount string, if applicable (e.g., "$5.00")
                           // This field might be null or an empty string if not a SuperChat.
}
```

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue for any bugs, feature requests, or improvements.
