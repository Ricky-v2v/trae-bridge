# Trae Bridge

REST API bridge for [Trae AI IDE](https://github.com/Trae-ai/trae), allowing you to interact with Trae's AI models via HTTP requests.

## Overview

Trae Bridge connects to the Trae Electron app using Chrome DevTools Protocol (CDP) and provides a REST API to send messages, receive responses, and manage conversations.

## Features

- 🌉 REST API interface to Trae's AI models
- ⚡ Synchronous and asynchronous chat modes
- 🔄 New chat/session management
- 📊 Chat history retrieval
- 🔍 Health monitoring
- 🎯 Model switching (placeholder)

## Architecture

```
┌─────────────┐      CDP       ┌─────────────┐
│ Trae Bridge │◄──────────────►│  Trae App   │
│  (REST API) │   WebSocket    │  (Electron) │
└─────────────┘                └─────────────┘
       ▲
       │
       │ HTTP
       │
┌──────┴──────┐
│   Client    │
│  (curl/API) │
└─────────────┘
```

## Installation

1. Clone this repository:
```bash
git clone https://github.com/yourusername/trae-bridge.git
cd trae-bridge
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### 1. Start Trae with CDP Enabled

First, launch Trae with Chrome DevTools Protocol enabled:

```bash
./scripts/start_trae.sh
```

This will start Trae with remote debugging on port 9230.

### 2. Start the Bridge Server

In another terminal, start the bridge server:

```bash
python scripts/bridge.py
```

The API will be available at `http://127.0.0.1:8765`

### 3. Test the API

#### Health Check
```bash
curl http://127.0.0.1:8765/health
```

#### Send a Message (Synchronous)
```bash
curl -X POST http://127.0.0.1:8765/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, Trae!"}'
```

#### Send a Message (Asynchronous)
```bash
# Start async request
curl -X POST http://127.0.0.1:8765/async \
  -H "Content-Type: application/json" \
  -d '{"message": "Explain quantum computing"}'

# Response: {"task_id": "task_1", "status": "pending"}

# Poll for result
curl http://127.0.0.1:8765/task/task_1
```

#### Start New Chat
```bash
curl -X POST http://127.0.0.1:8765/new
```

#### Get Chat History
```bash
curl http://127.0.0.1:8765/history
```

## API Endpoints

### `POST /chat`
Synchronous chat - sends a message and waits for the response.

**Request:**
```json
{
  "message": "Your message here",
  "timeout": 180.0
}
```

**Response:**
```json
{
  "response": "AI response text",
  "success": true
}
```

### `POST /async`
Asynchronous chat - sends a message and returns immediately.

**Request:**
```json
{
  "message": "Your message here",
  "timeout": 180.0
}
```

**Response:**
```json
{
  "task_id": "task_1",
  "status": "pending"
}
```

### `GET /task/{task_id}`
Get the status of an async task.

**Response:**
```json
{
  "task_id": "task_1",
  "status": "completed",
  "response": "AI response text",
  "error": null
}
```

### `POST /new`
Start a new chat session (clears context).

**Response:**
```json
{
  "status": "success",
  "message": "New chat started"
}
```

### `GET /health`
Health check endpoint.

**Response:**
```json
{
  "status": "healthy",
  "connected": true
}
```

### `GET /models`
List available models.

**Response:**
```json
{
  "models": ["claude-3-5-sonnet", "claude-3-opus", "gpt-4", ...]
}
```

### `POST /model`
Switch the active model (placeholder).

**Request:**
```json
{
  "model": "claude-3-5-sonnet"
}
```

### `GET /history`
Get current chat history.

**Response:**
```json
{
  "messages": [
    {"text": "User message", "className": "..."},
    {"text": "AI response", "className": "..."}
  ]
}
```

## Configuration

### Command Line Options

```bash
python scripts/bridge.py --help
```

- `--host`: Host to bind to (default: 127.0.0.1)
- `--port`: Port to bind to (default: 8765)
- `--cdp-port`: Trae CDP port (default: 9230)
- `--log-level`: Log level (DEBUG, INFO, WARNING, ERROR)

## Development

### DOM Inspection

To inspect Trae's DOM structure and find the correct selectors:

```bash
python scripts/inspect_dom.py
```

This will help you identify:
- Chat input element selectors
- Send button selectors
- Message container selectors
- AI response indicators

Update the selectors in `src/dom_helper.py` based on the inspection results.

### Project Structure

```
trae-bridge/
├── README.md
├── requirements.txt
├── scripts/
│   ├── start_trae.sh      # Launch Trae with CDP
│   ├── bridge.py          # Main entry point
│   └── inspect_dom.py     # DOM inspection tool
└── src/
    ├── __init__.py
    ├── cdp_client.py      # CDP connection client
    ├── dom_helper.py      # DOM operation utilities
    └── api_server.py      # FastAPI REST server
```

## How It Works

1. **CDP Connection**: The bridge connects to Trae's Chrome DevTools Protocol endpoint
2. **Message Injection**: Uses CDP's Runtime.evaluate to execute JavaScript that:
   - Finds the chat input element
   - Inserts the message text
   - Clicks the send button or presses Enter
3. **Response Polling**: Periodically checks the DOM for:
   - New messages from AI
   - Completion indicators (end of thinking/loading)
4. **REST API**: FastAPI exposes HTTP endpoints that wrap these operations

## Troubleshooting

### Cannot connect to Trae

Make sure Trae is running with CDP enabled:
```bash
./scripts/start_trae.sh
```

Test CDP connection:
```bash
curl http://localhost:9230/json/list
```

### Messages not sending

Run the DOM inspector to find the correct selectors:
```bash
python scripts/inspect_dom.py
```

Update `DOMHelper` selectors in `src/dom_helper.py`.

### Timeout errors

Increase the timeout parameter:
```bash
curl -X POST http://127.0.0.1:8765/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Your message", "timeout": 300.0}'
```

## Acknowledgments

Inspired by [antigravity-bridge](https://github.com/example/antigravity-bridge), demonstrating CDP-based interaction with Electron applications.

## License

MIT License - See LICENSE file for details.

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.

## Disclaimer

This tool is for educational and personal use. Respect Trae's terms of service and usage limits.
