# OpenClaw Skill Integration

This document describes how to integrate Trae Bridge as an OpenClaw Skill.

## Skill Configuration

Add this to your OpenClaw skills configuration:

```yaml
skills:
  - name: trae-bridge
    display_name: Trae AI
    description: Access Trae AI models via REST API
    version: 1.0.0
    author: Trae Bridge Contributors
    enabled: true
    settings:
      api_base_url: http://127.0.0.1:8765
      timeout: 180
      max_retries: 3
      retry_delay: 1.0
```

## Usage Examples

### Basic Chat

```python
import requests

API_BASE = "http://127.0.0.1:8765"

def chat_with_trae(message: str) -> str:
    """Send a message to Trae and get response"""
    response = requests.post(
        f"{API_BASE}/chat",
        json={"message": message},
        timeout=200
    )
    response.raise_for_status()
    return response.json()["response"]

# Usage
result = chat_with_trae("Explain quantum computing in simple terms")
print(result)
```

### Async Chat Pattern

```python
import requests
import time

API_BASE = "http://127.0.0.1:8765"

def async_chat_with_trae(message: str, poll_interval: float = 2.0) -> str:
    """Send a message asynchronously and poll for result"""
    # Start async request
    response = requests.post(
        f"{API_BASE}/async",
        json={"message": message}
    )
    response.raise_for_status()
    task_id = response.json()["task_id"]

    # Poll for completion
    while True:
        status_response = requests.get(f"{API_BASE}/task/{task_id}")
        status_response.raise_for_status()
        data = status_response.json()

        if data["status"] == "completed":
            return data["response"]
        elif data["status"] == "failed":
            raise Exception(f"Task failed: {data.get('error')}")

        time.sleep(poll_interval)

# Usage
result = async_chat_with_trae("Write a Python function to sort a list")
print(result)
```

### New Chat Session

```python
import requests

API_BASE = "http://127.0.0.1:8765"

def start_new_chat():
    """Start a new chat session"""
    response = requests.post(f"{API_BASE}/new")
    response.raise_for_status()
    return response.json()

# Usage
start_new_chat()
```

### Get Chat History

```python
import requests

API_BASE = "http://127.0.0.1:8765"

def get_chat_history():
    """Retrieve current chat history"""
    response = requests.get(f"{API_BASE}/history")
    response.raise_for_status()
    return response.json()["messages"]

# Usage
history = get_chat_history()
for msg in history:
    print(f"{msg['text'][:100]}...")
```

## OpenClow Skill Interface

### Skill Class Implementation

```python
import requests
from typing import Optional, Dict, Any

class TraeBridgeSkill:
    """OpenClaw skill for Trae AI Bridge"""

    def __init__(self, config: Dict[str, Any]):
        self.api_base = config.get("api_base_url", "http://127.0.0.1:8765")
        self.timeout = config.get("timeout", 180)
        self.max_retries = config.get("max_retries", 3)
        self.retry_delay = config.get("retry_delay", 1.0)

    def chat(self, message: str, timeout: Optional[float] = None) -> str:
        """Send a message and get response"""
        timeout = timeout or self.timeout

        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    f"{self.api_base}/chat",
                    json={"message": message, "timeout": timeout},
                    timeout=timeout + 10  # Extra buffer for HTTP
                )
                response.raise_for_status()
                return response.json()["response"]

            except requests.exceptions.Timeout:
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(self.retry_delay)

            except requests.exceptions.RequestException as e:
                if attempt == self.max_retries - 1:
                    raise
                time.sleep(self.retry_delay)

    def async_chat(self, message: str) -> str:
        """Send message asynchronously and wait for result"""
        # Start task
        response = requests.post(
            f"{self.api_base}/async",
            json={"message": message, "timeout": self.timeout}
        )
        response.raise_for_status()
        task_id = response.json()["task_id"]

        # Poll for completion
        while True:
            status = requests.get(f"{self.api_base}/task/{task_id}")
            status.raise_for_status()
            data = status.json()

            if data["status"] == "completed":
                return data["response"]
            elif data["status"] == "failed":
                raise Exception(data.get("error", "Task failed"))

            time.sleep(1.0)

    def new_chat(self) -> None:
        """Start a new chat session"""
        response = requests.post(f"{self.api_base}/new")
        response.raise_for_status()

    def get_history(self) -> list:
        """Get chat history"""
        response = requests.get(f"{self.api_base}/history")
        response.raise_for_status()
        return response.json()["messages"]

    def health_check(self) -> bool:
        """Check if the bridge is healthy"""
        try:
            response = requests.get(f"{self.api_base}/health", timeout=5)
            response.raise_for_status()
            return response.json()["connected"]
        except:
            return False

    def list_models(self) -> list:
        """List available models"""
        response = requests.get(f"{self.api_base}/models")
        response.raise_for_status()
        return response.json()["models"]

    def switch_model(self, model: str) -> None:
        """Switch active model"""
        response = requests.post(
            f"{self.api_base}/model",
            json={"model": model}
        )
        response.raise_for_status()
```

## Skill Manifest

```json
{
  "name": "trae-bridge",
  "version": "1.0.0",
  "description": "Access Trae AI models via REST API",
  "author": "Trae Bridge Contributors",
  "license": "MIT",
  "capabilities": [
    "chat",
    "async_chat",
    "new_chat",
    "get_history",
    "health_check",
    "list_models",
    "switch_model"
  ],
  "requirements": {
    "api_base_url": "http://127.0.0.1:8765",
    "timeout": 180,
    "max_retries": 3
  },
  "endpoints": {
    "chat": "POST /chat",
    "async_chat": "POST /async",
    "task_status": "GET /task/{id}",
    "new_chat": "POST /new",
    "health": "GET /health",
    "models": "GET /models",
    "switch_model": "POST /model",
    "history": "GET /history"
  }
}
```

## Integration Steps

1. **Install Dependencies**
   ```bash
   pip install requests
   ```

2. **Start Trae with CDP**
   ```bash
   ./scripts/start_trae.sh
   ```

3. **Start the Bridge**
   ```bash
   python scripts/bridge.py
   ```

4. **Configure OpenClaw**
   Add the skill configuration to your OpenClaw setup

5. **Test the Integration**
   ```python
   skill = TraeBridgeSkill(config)
   response = skill.chat("Hello, Trae!")
   print(response)
   ```

## Error Handling

```python
import requests
from requests.exceptions import RequestException

def safe_chat(message: str) -> Optional[str]:
    """Chat with error handling"""
    try:
        response = requests.post(
            "http://127.0.0.1:8765/chat",
            json={"message": message},
            timeout=200
        )
        response.raise_for_status()
        return response.json()["response"]

    except requests.exceptions.ConnectionError:
        print("Cannot connect to Trae Bridge. Is it running?")
        return None

    except requests.exceptions.Timeout:
        print("Request timed out")
        return None

    except requests.exceptions.HTTPError as e:
        print(f"HTTP error: {e}")
        return None

    except Exception as e:
        print(f"Unexpected error: {e}")
        return None
```

## Advanced Usage

### Streaming Responses (Future)

Note: Streaming is not currently implemented but could be added via CDP's DOM events:

```python
async def stream_chat(message: str):
    """Stream responses as they arrive (pseudo-code)"""
    # This would require DOM mutation observers via CDP
    # Implementation pending
    pass
```

### Custom Selectors

If Trae's DOM structure changes, you can customize selectors:

```python
# In dom_helper.py, update:
SELECTOR_INPUT = 'your-custom-selector'
SELECTOR_SEND_BUTTON = 'your-send-button-selector'
```

## Performance Tips

1. **Use Async Mode** for long-running requests
2. **Batch Requests** when possible (future feature)
3. **Adjust Timeout** based on query complexity
4. **Monitor Health** before critical operations

## Security Considerations

- The bridge listens on 127.0.0.1 by default (localhost only)
- For remote access, use a reverse proxy with authentication
- Consider adding API keys for production use
- Monitor Trae's rate limits and quota

## Support

For issues or questions:
- GitHub Issues: [trae-bridge/issues](https://github.com/yourusername/trae-bridge/issues)
- Documentation: See README.md

## License

MIT License - See LICENSE file for details.
