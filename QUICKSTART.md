# Trae Bridge - Quick Start Guide

Get up and running with Trae Bridge in 5 minutes.

## Prerequisites

- Python 3.8 or higher
- Trae AI IDE installed
- pip (Python package manager)

## Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/trae-bridge.git
   cd trae-bridge
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Verify installation:**
   ```bash
   python scripts/test_integration.py
   ```

## Usage

### Step 1: Start Trae with CDP

Launch Trae with Chrome DevTools Protocol enabled:

```bash
./scripts/start_trae.sh
```

This starts Trae with remote debugging on port 9230.

**Verify Trae is running:**
```bash
curl http://localhost:9230/json/list
```

You should see JSON output with Trae's page information.

### Step 2: Start the Bridge Server

In a new terminal, start the API server:

```bash
python scripts/bridge.py
```

The server will start on `http://127.0.0.1:8765`

**Customize settings:**
```bash
python scripts/bridge.py --host 0.0.0.0 --port 9000 --cdp-port 9231
```

### Step 3: Test the Connection

```bash
curl http://127.0.0.1:8765/health
```

Expected response:
```json
{
  "status": "healthy",
  "connected": true
}
```

## Your First Chat

### Using the Example Client

```bash
python scripts/client.py chat "Hello, Trae! Write a hello world function in Python"
```

### Using curl

```bash
curl -X POST http://127.0.0.1:8765/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, Trae!"}'
```

### Using Python

```python
import requests

response = requests.post(
    "http://127.0.0.1:8765/chat",
    json={"message": "Hello, Trae!"}
)

result = response.json()
print(result["response"])
```

## Interactive Mode

Start an interactive chat session:

```bash
python scripts/client.py interactive
```

Commands in interactive mode:
- Type your message to chat
- `/new` - Start new chat
- `/history` - Show chat history
- `/quit` - Exit

## API Documentation

Once the server is running, visit the interactive API docs:

```
http://127.0.0.1:8765/docs
```

This provides a Swagger UI where you can test all endpoints.

## Common Commands

### Health Check
```bash
curl http://127.0.0.1:8765/health
```

### Send Message (Sync)
```bash
curl -X POST http://127.0.0.1:8765/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Your message here"}'
```

### Send Message (Async)
```bash
curl -X POST http://127.0.0.1:8765/async \
  -H "Content-Type: application/json" \
  -d '{"message": "Your message here"}'
```

### Check Async Task
```bash
curl http://127.0.0.1:8765/task/task_1
```

### New Chat
```bash
curl -X POST http://127.0.0.1:8765/new
```

### Get History
```bash
curl http://127.0.0.1:8765/history
```

### List Models
```bash
curl http://127.0.0.1:8765/models
```

## Testing

Run all tests to verify your setup:

```bash
# Integration tests (no Trae required)
python scripts/test_integration.py

# System tests (server startup)
python scripts/test_system.py

# Component tests (requires Trae with CDP)
python scripts/test_bridge.py

# E2E tests (verify full flow)
python scripts/test_e2e.py
```

## Troubleshooting

### "Cannot connect to Trae"

1. Make sure Trae is running with CDP:
   ```bash
   curl http://localhost:9230/json/list
   ```

2. Restart Trae with CDP:
   ```bash
   ./scripts/start_trae.sh
   ```

3. Check the CDP port matches (default: 9230)

### "Cannot connect to API server"

1. Make sure the bridge server is running:
   ```bash
   python scripts/bridge.py
   ```

2. Check the server port (default: 8765)

### "Timeout waiting for response"

1. Increase timeout value:
   ```bash
   curl -X POST http://127.0.0.1:8765/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "...", "timeout": 300}'
   ```

2. Use async mode for long tasks:
   ```bash
   curl -X POST http://127.0.0.1:8765/async \
     -H "Content-Type: application/json" \
     -d '{"message": "..."}'
   ```

### DOM Elements Not Found

If message sending fails, Trae's UI may have changed. Run the DOM inspector:

```bash
python scripts/inspect_dom.py
```

This will help identify the correct DOM selectors for Trae's chat interface.

## Next Steps

- Read [EXAMPLES.md](EXAMPLES.md) for detailed usage examples
- Check [CLAUDE.md](CLAUDE.md) for architecture details
- Explore the API documentation at `http://127.0.0.1:8765/docs`

## Support

For issues and questions:
- Check existing GitHub issues
- Review the troubleshooting section above
- Run the test suite to diagnose problems

## Security Notes

- The API server binds to `127.0.0.1` by default (localhost only)
- Do not expose the API server to the internet without authentication
- Trae's CDP port should not be accessible from untrusted networks
- Consider adding API keys or OAuth for production use
