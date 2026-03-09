# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Trae Bridge is a REST API bridge for [Trae AI IDE](https://github.com/Trae-ai/trae). It connects to the Trae Electron app via Chrome DevTools Protocol (CDP) and exposes HTTP endpoints to send messages, receive AI responses, and manage conversations.

**Architecture**: The bridge uses CDP to execute JavaScript in Trae's context, manipulating DOM elements to inject messages and polling for AI responses.

## Common Commands

### Start Trae with CDP
```bash
./scripts/start_trae.sh
```
This launches Trae with `--remote-debugging-port=9230`. Verify with:
```bash
curl http://localhost:9230/json/list
```

### Start the Bridge Server
```bash
python scripts/bridge.py
```
Default: `http://127.0.0.1:8765`

With custom options:
```bash
python scripts/bridge.py --host 127.0.0.1 --port 8765 --cdp-port 9230 --log-level INFO
```

### Run Tests

**Integration tests** (no Trae required):
```bash
python scripts/test_integration.py
```

**Component tests** (requires Trae running with CDP):
```bash
python scripts/test_bridge.py
```

**System tests** (server startup, CLI, requirements):
```bash
python scripts/test_system.py
```

### DOM Inspection
To find/update Trae's DOM selectors:
```bash
python scripts/inspect_dom.py
```

## Architecture

### Three-Layer Design

1. **CDP Client** (`src/cdp_client.py`)
   - Manages WebSocket connection to Trae's CDP endpoint
   - Executes JavaScript via `Runtime.evaluate`
   - Handles async command/response pattern with futures

2. **DOM Helper** (`src/dom_helper.py`)
   - Contains Trae-specific DOM selectors
   - Implements message sending and response polling logic
   - Auto-detects selectors with fallback strategies

3. **API Server** (`src/api_server.py`)
   - FastAPI REST endpoints
   - Connection pooling with auto-reconnect
   - Background task management for async requests

### Key Data Flow

```
HTTP Request → API Server → DOM Helper → CDP Client → Trae (JavaScript execution)
                                    ↓
Poll DOM for response ← CDP Client ← DOM Helper ← Trae UI updates
```

## DOM Selector Patterns

The DOM helper uses cascading selector strategies. When Trae's UI changes, update selectors in `DOMHelper` class:

- **Input**: `[contenteditable="true"]`, `textarea`, `[role="textbox"]`
- **Send button**: `button[type="submit"]`, `[aria-label*="send" i]`
- **Messages**: `[class*="message"]`, `[role="log"] > div`
- **Loading indicators**: `[class*="thinking"]`, `[class*="loading"]`

Use `inspect_dom.py` to find current selectors in Trae's DOM.

## CDP Connection Details

- **Default port**: 9230 (configurable via `--cdp-port`)
- **Connection flow**: Fetch `http://localhost:9230/json/list` → extract WebSocket URL → connect via `websockets`
- **Command pattern**: Each CDP command has an ID, response matched via `pending_commands` dict with futures
- **Auto-reconnect**: `ensure_connection()` in API server reconnects if WebSocket is closed

## API Endpoints

- `POST /chat` - Synchronous chat (default 180s timeout)
- `POST /async` - Start async task, returns task_id
- `GET /task/{id}` - Poll async task status
- `POST /new` - Start new chat session
- `GET /health` - Check CDP connection status
- `GET /history` - Get current conversation
- `GET /models` - List available models (placeholder)
- `POST /model` - Switch model (placeholder)

## Important Implementation Notes

### Message Sending
Uses `document.execCommand('insertText')` for contenteditable or direct `.value` assignment for textarea, then clicks send button or dispatches Enter key event.

### Response Polling
Polls every 1s (configurable) checking:
1. Last message element exists
2. No loading/thinking indicators present
3. Returns message text when complete

### Error Handling
- CDP errors raise `CDPError` exception
- Timeouts raise `TimeoutError` with context
- API errors return HTTP 503 when CDP connection fails

### Dependencies
- `websockets` - CDP WebSocket connection
- `aiohttp` - HTTP client for fetching CDP endpoint info
- `fastapi` + `uvicorn` - REST API server
- `pydantic` - Request/response validation

## Testing Strategy

Three test levels with increasing Trae dependency:

1. **Integration tests** - Module imports and initialization only
2. **Component tests** - Full CDP connection and DOM operations
3. **System tests** - Server startup and HTTP endpoints

Always run integration tests first to verify basic setup before requiring Trae to be running.
