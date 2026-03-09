# Trae Bridge

REST API bridge for [Trae AI IDE](https://www.trae.ai/), allowing you to interact with Trae's AI models via HTTP requests.

## Overview

Trae Bridge connects to the Trae Electron app using Chrome DevTools Protocol (CDP) and provides a REST API to send messages, receive responses, and manage conversations. It handles the complexity of Trae's internal DOM structure and provides a clean, stable API for external tools.

## Features

- 🌉 **REST API** interface to Trae's AI models
- ⚡ **Synchronous and Asynchronous** chat modes
- 🔄 **Session Management**: Start new chats or switch models
- 📊 **Chat History**: Retrieve full conversation history with role detection
- 🔍 **Health Monitoring**: Real-time CDP connection status
- 🧪 **Complete Test Suite**: Unit, integration, system, and E2E tests
- 🛠️ **Developer Tools**: DOM inspector and interactive client

## Architecture

```
┌─────────────┐      CDP       ┌─────────────┐
│ Trae Bridge │◄──────────────►│  Trae App   │
│  (REST API) │   WebSocket    │  (Electron) │
└─────────────┘                └─────────────┘
       ▲
       │
       │ HTTP (JSON)
       │
┌──────┴──────┐      Example:
│   Client    │      - curl
│  (OpenClaw) │      - python-requests
└─────────────┘      - scripts/client.py
```

## Installation

1. Clone this repository:
```bash
git clone https://github.com/Ricky-v2v/trae-bridge.git
cd trae-bridge
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

## Usage

### 1. Start Trae with CDP Enabled

Launch Trae with Chrome DevTools Protocol enabled:

```bash
./scripts/start_trae.sh
```

### 2. Start the Bridge Server

Start the bridge server in another terminal:

```bash
python scripts/bridge.py --log-level INFO
```

The API will be available at `http://127.0.0.1:8765` by default.

### 3. Quick Test (Interactive Client)

Use the built-in interactive client for debugging:

```bash
python scripts/client.py chat
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/chat` | Synchronous chat - sends message and waits for response |
| `POST` | `/async` | Asynchronous chat - returns `task_id` immediately |
| `GET` | `/task/{id}` | Get the status/result of an async task |
| `POST` | `/new` | Start a new chat session (clears context) |
| `GET` | `/history` | Get current chat history with role detection |
| `GET` | `/health` | Check bridge/CDP connection status |
| `GET` | `/models` | List available models in Trae |
| `POST` | `/model` | Switch the active model |

## Testing

Trae Bridge includes a comprehensive testing suite:

- **Integration tests**: `python scripts/test_integration.py` (No Trae required)
- **System tests**: `python scripts/test_system.py` (Verifies server startup)
- **Bridge tests**: `python scripts/test_bridge.py` (Requires Trae running)
- **E2E tests**: `python scripts/test_e2e.py` (Full flow verification)

Run all tests with:
```bash
./scripts/test_all.sh  # (If implemented) or run manually
```

## Advanced: DOM Search

If Trae updates its UI and the bridge stops working, use the DOM inspector to find new selectors:

```bash
python scripts/inspect_dom.py
```

Update `src/dom_helper.py` with the findings.

## Documentation

- [QUICKSTART.md](QUICKSTART.md) - Get started in 5 minutes
- [EXAMPLES.md](EXAMPLES.md) - Common code patterns and API usage
- [SKILL.md](SKILL.md) - How to use as an OpenClaw skill

## License

MIT License. See [LICENSE](LICENSE) for details.
