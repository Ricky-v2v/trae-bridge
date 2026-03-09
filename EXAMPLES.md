# Trae Bridge - Usage Examples

This document provides practical examples for using the Trae Bridge REST API.

## Quick Start

1. **Start Trae with CDP enabled:**
   ```bash
   ./scripts/start_trae.sh
   ```

2. **Start the Bridge API server:**
   ```bash
   python scripts/bridge.py
   ```

3. **Test the connection:**
   ```bash
   curl http://127.0.0.1:8765/health
   ```

## API Endpoints

### 1. Health Check

Check if the bridge is connected to Trae:

```bash
curl http://127.0.0.1:8765/health
```

**Response:**
```json
{
  "status": "healthy",
  "connected": true
}
```

### 2. Synchronous Chat

Send a message and wait for the response:

```bash
curl -X POST http://127.0.0.1:8765/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, Trae!"}'
```

**With custom timeout:**
```bash
curl -X POST http://127.0.0.1:8765/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Write a Python function", "timeout": 300}'
```

**Response:**
```json
{
  "response": "Hello! I'm Trae, your AI coding assistant...",
  "success": true
}
```

### 3. Asynchronous Chat

Send a message and get a task ID for polling:

```bash
curl -X POST http://127.0.0.1:8765/async \
  -H "Content-Type: application/json" \
  -d '{"message": "Explain quantum computing"}'
```

**Response:**
```json
{
  "task_id": "task_1",
  "status": "pending"
}
```

### 4. Check Task Status

Poll for async task results:

```bash
curl http://127.0.0.1:8765/task/task_1
```

**Response (pending):**
```json
{
  "task_id": "task_1",
  "status": "processing",
  "response": null,
  "error": null
}
```

**Response (completed):**
```json
{
  "task_id": "task_1",
  "status": "completed",
  "response": "Quantum computing is...",
  "error": null
}
```

**Response (failed):**
```json
{
  "task_id": "task_1",
  "status": "failed",
  "response": null,
  "error": "Timeout after 180s"
}
```

### 5. Start New Chat

Clear the conversation context:

```bash
curl -X POST http://127.0.0.1:8765/new
```

**Response:**
```json
{
  "status": "success",
  "message": "New chat started"
}
```

### 6. Get Chat History

Retrieve the current conversation:

```bash
curl http://127.0.0.1:8765/history
```

**Response:**
```json
{
  "messages": [
    {
      "text": "Hello, Trae!",
      "className": "message user"
    },
    {
      "text": "Hello! How can I help you today?",
      "className": "message assistant"
    }
  ]
}
```

### 7. List Available Models

Get a list of available AI models:

```bash
curl http://127.0.0.1:8765/models
```

**Response:**
```json
{
  "models": [
    "claude-3-5-sonnet",
    "claude-3-opus",
    "claude-3-haiku",
    "gpt-4",
    "gpt-4-turbo",
    "gpt-3.5-turbo"
  ]
}
```

### 8. Switch Model

Change the active AI model:

```bash
curl -X POST http://127.0.0.1:8765/model \
  -H "Content-Type: application/json" \
  -d '{"model": "claude-3-opus"}'
```

**Response:**
```json
{
  "status": "success",
  "message": "Model switched to claude-3-opus",
  "model": "claude-3-opus"
}
```

## Python Examples

### Basic Chat

```python
import requests

API_URL = "http://127.0.0.1:8765"

# Send a message
response = requests.post(
    f"{API_URL}/chat",
    json={"message": "Write a hello world function in Python"}
)

result = response.json()
if result["success"]:
    print(result["response"])
else:
    print("Error:", result)
```

### Async Chat with Polling

```python
import requests
import time

API_URL = "http://127.0.0.1:8765"

# Start async task
task_response = requests.post(
    f"{API_URL}/async",
    json={
        "message": "Explain the theory of relativity",
        "timeout": 300
    }
)

task_id = task_response.json()["task_id"]

# Poll for results
while True:
    status_response = requests.get(f"{API_URL}/task/{task_id}")
    status = status_response.json()

    if status["status"] == "completed":
        print("Response:", status["response"])
        break
    elif status["status"] == "failed":
        print("Error:", status["error"])
        break
    else:
        print(f"Status: {status['status']}")
        time.sleep(2)
```

### Streaming Chat with History

```python
import requests

API_URL = "http://127.0.0.1:8765"

def chat_with_history(messages):
    # Start new chat
    requests.post(f"{API_URL}/new")

    responses = []
    for msg in messages:
        # Send message
        response = requests.post(
            f"{API_URL}/chat",
            json={"message": msg}
        )
        result = response.json()
        if result["success"]:
            responses.append(result["response"])

    # Get full history
    history = requests.get(f"{API_URL}/history").json()
    return history["messages"]

# Example usage
messages = [
    "What is Python?",
    "Can you show me an example?",
    "How do I install it?"
]

conversation = chat_with_history(messages)
for msg in conversation:
    print(f"- {msg['text'][:100]}...")
```

## JavaScript/Node.js Examples

### Fetch API

```javascript
const API_URL = 'http://127.0.0.1:8765';

async function sendMessage(message) {
  const response = await fetch(`${API_URL}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ message })
  });

  const result = await response.json();
  if (result.success) {
    console.log(result.response);
  } else {
    console.error('Error:', result);
  }
}

// Usage
sendMessage('Hello from JavaScript!');
```

### Async with Polling

```javascript
const API_URL = 'http://127.0.0.1:8765';

async function sendAsyncMessage(message) {
  // Start task
  const taskResponse = await fetch(`${API_URL}/async`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ message, timeout: 300 })
  });

  const { task_id } = await taskResponse.json();

  // Poll for results
  while (true) {
    const statusResponse = await fetch(`${API_URL}/task/${task_id}`);
    const status = await statusResponse.json();

    if (status.status === 'completed') {
      console.log('Response:', status.response);
      return status.response;
    } else if (status.status === 'failed') {
      console.error('Error:', status.error);
      throw new Error(status.error);
    }

    // Wait before polling again
    await new Promise(resolve => setTimeout(resolve, 2000));
  }
}

// Usage
sendAsyncMessage('Explain async/await in JavaScript')
  .then(response => console.log('Done!'))
  .catch(error => console.error('Failed:', error));
```

## Advanced Usage

### Custom Configuration

Start the server with custom settings:

```bash
python scripts/bridge.py \
  --host 0.0.0.0 \
  --port 9000 \
  --cdp-port 9231 \
  --log-level DEBUG
```

### Multiple Instances

Run multiple bridge instances for different Trae windows:

```bash
# Terminal 1: Trae on CDP port 9230, Bridge on port 8765
./scripts/start_trae.sh
python scripts/bridge.py --port 8765 --cdp-port 9230

# Terminal 2: Trae on CDP port 9231, Bridge on port 8766
./scripts/start_trae.sh --cdp-port 9231
python scripts/bridge.py --port 8766 --cdp-port 9231
```

### Error Handling

```python
import requests
from requests.exceptions import RequestException

API_URL = "http://127.0.0.1:8765"

def safe_chat(message, max_retries=3):
    for attempt in range(max_retries):
        try:
            response = requests.post(
                f"{API_URL}/chat",
                json={"message": message},
                timeout=200  # Slightly longer than max Trae timeout
            )

            if response.status_code == 200:
                return response.json()
            elif response.status_code == 408:
                print(f"Timeout on attempt {attempt + 1}")
            elif response.status_code == 503:
                print("Trae not connected - check if Trae is running")
                break
            else:
                print(f"Error {response.status_code}: {response.text}")

        except RequestException as e:
            print(f"Connection error on attempt {attempt + 1}: {e}")

    return {"success": False, "error": "Max retries exceeded"}

# Usage
result = safe_chat("Hello!")
if result["success"]:
    print(result["response"])
```

## Testing

### Test API with curl

```bash
# Health check
curl http://127.0.0.1:8765/health

# Simple chat
curl -X POST http://127.0.0.1:8765/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Test message"}'

# Async chat
curl -X POST http://127.0.0.1:8765/async \
  -H "Content-Type: application/json" \
  -d '{"message": "Long task"}'

# Check task
curl http://127.0.0.1:8765/task/task_1
```

### Interactive Testing

The API includes automatic OpenAPI documentation. Start the server and visit:

```
http://127.0.0.1:8765/docs
```

This provides an interactive Swagger UI where you can test all endpoints.

## Troubleshooting

### Connection Issues

If you see "Cannot connect to Trae":

1. Verify Trae is running with CDP:
   ```bash
   curl http://localhost:9230/json/list
   ```

2. Check the CDP port matches:
   ```bash
   ps aux | grep -i trae
   ```

3. Restart Trae with the correct CDP port:
   ```bash
   ./scripts/start_trae.sh
   ```

### Timeout Issues

If requests timeout frequently:

1. Increase the timeout value:
   ```bash
   curl -X POST http://127.0.0.1:8765/chat \
     -H "Content-Type: application/json" \
     -d '{"message": "...", "timeout": 600}'
   ```

2. Use async mode for long-running tasks:
   ```bash
   curl -X POST http://127.0.0.1:8765/async \
     -H "Content-Type: application/json" \
     -d '{"message": "...", "timeout": 600}'
   ```

### DOM Selector Issues

If message sending fails:

1. Run DOM inspector to find correct selectors:
   ```bash
   python scripts/inspect_dom.py
   ```

2. Update selectors in `src/dom_helper.py` based on inspection results

## Performance Tips

1. **Use async for long tasks**: Avoid blocking on responses that take more than 30 seconds
2. **Pool connections**: Keep HTTP connections open for multiple requests
3. **Adjust poll interval**: For async tasks, poll less frequently if responses are slow
4. **Monitor history**: Clear chat history periodically with `/new` endpoint
