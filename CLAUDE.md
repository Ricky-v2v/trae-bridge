# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Trae Bridge is a REST API bridge for [Trae AI IDE](https://www.trae.ai/). It connects to the Trae Electron app via Chrome DevTools Protocol (CDP) and exposes HTTP endpoints to send messages, receive AI responses, and manage conversations.

**Key Architecture Features**:
- **WebSocket Compatibility**: Works with `websockets 13.x` to `16.x` (monitored via `CDPClient.is_connected`).
- **Stable DOM Search**: Uses specific Trae selectors for `input-v2`, `assistant-chat-turn`, and `stop-button` detection.
- **Async Execution**: Support for long-running AI tasks with status polling.

## Common Commands

### 1. Launch Environment
```bash
./scripts/start_trae.sh     # Launch Trae with CDP
python scripts/bridge.py    # Start the API server
```

### 2. Interactive Client
```bash
python scripts/client.py chat    # CLI interactive chat mode
python scripts/client.py history # View current logs
```

### 3. Testing (Hierarchical)
```bash
python scripts/test_integration.py  # Level 1: Modules & Imports
python scripts/test_system.py       # Level 2: Server startup & CLI
python scripts/test_bridge.py       # Level 3: CDP & DOM (Requires Trae)
python scripts/test_e2e.py          # Level 4: Full flow (Requires Trae)
```

### 4. DOM Debugging
```bash
python scripts/inspect_dom.py    # Dump Trae's DOM for selector research
```

## Architecture

1. **CDP Client** (`src/cdp_client.py`)
   - Manages WebSocket lifecycle.
   - Handles `websockets 16.0+` compatibility (checks `.state` vs `.closed`).
   - Executes JS via `Runtime.evaluate` (using IIFE syntax).

2. **DOM Helper** (`src/dom_helper.py`)
   - **Send Strategy**: Clear input → pre-inject MutationObserver → `execCommand('insertText')` → wait for enabled send button → Click.
   - **Wait Strategy**: Injects a MutationObserver to watch for the "stop generating" button disappearance, firing a JS console event (`TRAE_BRIDGE:FINISHED`) for O(1) detection, with a polling fallback.
   - **History**: Extracts from `chat-turn assistant` and `chat-turn user`.

3. **API Server** (`src/api_server.py`)
   - FastAPI based.
   - `ensure_connection()` handles auto-reconnect on every entry point.
   - Async tasks are managed in a background task queue with `task_counter`.

## Implementation Rules & Patterns

### JS Execution
Always use the IIFE pattern for `Runtime.evaluate`:
```python
await cdp.evaluate("((() => { /* code */ return result; })())")
```

### Event-Driven Completion (MutationObserver)
Instead of polling the DOM constantly, the bridge injects a `MutationObserver` that emits a `console.log` event when the "stop generating" button disappears. The `CDPClient` intercepts this console log and resolves the wait immediately. Polling is only used as a fallback if the event times out.

### CDP Versioning
If `websockets` library is updated, check `CDPClient.is_connected` property for compatibility.

## Selectors (As of 2026-03)
- **Input**: `div.chat-input-v2-input-box-editable[role="textbox"]`
- **Send**: `.chat-input-v2-send-button`
- **Message Turns**: `section.chat-turn`
- **Thinking/Generating**: `[class*="stop-button"]`, `[class*="pending"]`
