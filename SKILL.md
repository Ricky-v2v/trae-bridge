# OpenClaw Skill Integration

This document describes how to integrate Trae Bridge as an OpenClaw Skill.

## Skill Configuration

Add this to your OpenClaw skills configuration:

```yaml
skills:
  - name: trae-bridge
    display_name: Trae AI
    description: Access Trae AI models via REST API
    version: 1.1.0
    author: Ricky-v2v
    enabled: true
    settings:
      api_base_url: http://127.0.0.1:8765
      timeout: 300
      max_retries: 3
      retry_delay: 1.0
```

## Setup Sequence

1. **Launch Trae with CDP**
   ```bash
   ./scripts/start_trae.sh
   ```

2. **Start the Bridge**
   ```bash
   python scripts/bridge.py --log-level INFO
   ```

3. **Verify Connection**
   ```bash
   curl http://127.0.0.1:8765/health
   # Response should show {"connected": true}
   ```

## Skill Class Template (OpenClaw)

```python
import requests
import time
from typing import Optional, Dict, List, Any

class TraeBridgeSkill:
    """OpenClaw skill for Trae AI Bridge interaction"""

    def __init__(self, config: Dict[str, Any]):
        self.api_base = config.get("api_base_url", "http://127.0.0.1:8765")
        self.timeout = config.get("timeout", 300)

    def chat_sync(self, message: str) -> str:
        """Simple synchronous chat request"""
        resp = requests.post(
            f"{self.api_base}/chat",
            json={"message": message, "timeout": self.timeout},
            timeout=self.timeout + 10
        )
        resp.raise_for_status()
        return resp.json()["response"]

    def chat_async(self, message: str) -> str:
        """Recommended: Asynchronous chat with polling (best for long tasks)"""
        # 1. Initiate task
        resp = requests.post(
            f"{self.api_base}/async",
            json={"message": message, "timeout": self.timeout}
        )
        resp.raise_for_status()
        task_id = resp.json()["task_id"]

        # 2. Poll status
        while True:
            status_resp = requests.get(f"{self.api_base}/task/{task_id}")
            status_resp.raise_for_status()
            data = status_resp.json()
            
            if data["status"] == "completed":
                return data["response"]
            elif data["status"] == "failed":
                raise RuntimeError(f"Trae task failed: {data.get('error')}")
            
            time.sleep(2)  # Polling interval

    def reset_chat(self) -> bool:
        """Start a fresh chat session without history"""
        resp = requests.post(f"{self.api_base}/new")
        return resp.status_code == 200

    def get_history(self) -> List[Dict[str, str]]:
        """Retrieve full conversation logs"""
        resp = requests.get(f"{self.api_base}/history")
        resp.raise_for_status()
        return resp.json()["messages"]
```

## Performance & Stability Tips

### ⚡ Polling vs Sync
Small queries (like greeting or simple questions) are fine with `/chat`. For complex coding tasks or deep reasoning, always use `/async` to prevent HTTP timeout issues between the client and bridge.

### 🛡️ Connection Management
The bridge automatically handles re-connections if Trae restarts. However, always check `/health` before starting a long task if the system has been idle.

### 🧩 UI Changes
If Trae updates its interface and the skill fails to send/receive, run `python scripts/inspect_dom.py` to diagnose selector changes.

## Security Considerations

- **Localhost Only**: The bridge binds to `127.0.0.1` by default. Do not expose this port on public networks without authentication/encryption.
- **CDP Debugging**: Running Trae with `--remote-debugging-port` allows anything on localhost to control the IDE. Ensure your local environment is secured.

## Troubleshooting

- **No response**: Ensure Trae is not in a blocking dialogue (e.g., save file confirmation) or modal window.
- **CDP Disconnected**: Check if Trae is running. Restart Trae using `./scripts/start_trae.sh` if needed.
- **Bridge Error 503**: The bridge is up but cannot connect to Trae's CDP WebSocket.
