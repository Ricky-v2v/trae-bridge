"""
CDP Client for Trae Bridge
Handles Chrome DevTools Protocol connection to Trae Electron app
"""

import asyncio
import json
import logging
from typing import Any, Callable, Optional
import aiohttp
import websockets

logger = logging.getLogger(__name__)


class CDPClient:
    """Client for Chrome DevTools Protocol connection to Trae"""

    def __init__(self, cdp_port: int = 9230):
        self.cdp_port = cdp_port
        self.ws = None  # websockets connection (ClientConnection in v16+)
        self.message_id = 0
        self.pending_commands: dict[int, asyncio.Future] = {}
        self._listener_task: Optional[asyncio.Task] = None
        self._event_callbacks: dict[str, list[Callable]] = {}

    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected (compatible with websockets 14-16+)"""
        if self.ws is None:
            return False
        # websockets 16.0+: use .state
        if hasattr(self.ws, 'state'):
            try:
                from websockets.protocol import State
                return self.ws.state == State.OPEN
            except ImportError:
                pass
        # websockets < 16: use .closed
        if hasattr(self.ws, 'closed'):
            return not self.ws.closed
        # websockets 14+: use .open
        if hasattr(self.ws, 'open'):
            return self.ws.open
        return False

    async def connect(self) -> None:
        """Connect to Trae's CDP endpoint"""
        try:
            # Get the WebSocket debugger URL
            async with aiohttp.ClientSession() as session:
                async with session.get(f'http://localhost:{self.cdp_port}/json/list') as resp:
                    if resp.status != 200:
                        raise ConnectionError(f"Cannot connect to CDP port {self.cdp_port}")

                    pages = await resp.json()

                    if not pages:
                        raise ConnectionError("No Trae pages found. Is Trae running?")

                    # Use the first available page (usually the main window)
                    ws_url = pages[0].get('webSocketDebuggerUrl')

                    if not ws_url:
                        raise ConnectionError("No WebSocket debugger URL found in Trae response")

            logger.info(f"Connecting to CDP WebSocket: {ws_url}")

            # Connect to WebSocket
            self.ws = await websockets.connect(ws_url)

            # Start listening for messages
            self._listener_task = asyncio.create_task(self._message_listener())

            # Enable runtime domain
            await self.execute("Runtime.enable")

            logger.info("CDP connection established successfully")

        except Exception as e:
            logger.error(f"Failed to connect to CDP: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from CDP"""
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass

        if self.ws:
            await self.ws.close()
            self.ws = None

        logger.info("CDP connection closed")

    async def execute(
        self,
        method: str,
        params: Optional[dict[str, Any]] = None,
        timeout: float = 30.0
    ) -> dict[str, Any]:
        """
        Execute a CDP command

        Args:
            method: CDP method name (e.g., "Runtime.evaluate")
            params: Method parameters
            timeout: Command timeout in seconds

        Returns:
            Command result
        """
        if not self.ws:
            raise ConnectionError("Not connected to CDP")

        self.message_id += 1
        cmd_id = self.message_id

        command = {
            "id": cmd_id,
            "method": method,
            "params": params or {}
        }

        # Create a future for the response
        future: asyncio.Future[dict[str, Any]] = asyncio.Future()
        self.pending_commands[cmd_id] = future

        try:
            # Send command
            await self.ws.send(json.dumps(command))

            # Wait for response with timeout
            result = await asyncio.wait_for(future, timeout=timeout)

            # Check for CDP errors
            if "error" in result:
                raise CDPError(result["error"].get("message", "Unknown CDP error"))

            return result.get("result", {})

        except asyncio.TimeoutError:
            del self.pending_commands[cmd_id]
            raise TimeoutError(f"CDP command '{method}' timed out after {timeout}s")

        finally:
            # Clean up the future
            if cmd_id in self.pending_commands:
                del self.pending_commands[cmd_id]

    async def evaluate(self, expression: str, return_by_value: bool = True) -> Any:
        """
        Evaluate JavaScript expression in Trae context

        Args:
            expression: JavaScript code to evaluate
            return_by_value: Whether to return the result by value

        Returns:
            Evaluation result
        """
        result = await self.execute(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": return_by_value,
                "awaitPromise": True
            }
        )

        # Handle CDP response structure: {result: {type: ..., value: ..., description: ...}}
        if "result" in result:
            inner_result = result["result"]
            if isinstance(inner_result, dict):
                if "value" in inner_result:
                    return inner_result["value"]
                elif "description" in inner_result:
                    return inner_result["description"]

        return None

    async def _message_listener(self) -> None:
        """Listen for incoming CDP messages"""
        try:
            async for message in self.ws:
                try:
                    data = json.loads(message)

                    # Handle command responses
                    if "id" in data:
                        cmd_id = data["id"]
                        if cmd_id in self.pending_commands:
                            future = self.pending_commands[cmd_id]
                            if not future.done():
                                future.set_result(data)

                    # Handle events (could be used for DOM events)
                    elif "method" in data:
                        await self._handle_event(data)

                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON message: {message}")
                except Exception as e:
                    logger.error(f"Error processing message: {e}")

        except websockets.exceptions.ConnectionClosed:
            logger.warning("CDP WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error in message listener: {e}")

    async def _handle_event(self, event: dict[str, Any]) -> None:
        """Handle CDP events"""
        method = event.get("method", "")
        params = event.get("params", {})

        # Log console messages for debugging
        if method == "Runtime.consoleAPICalled":
            args = params.get("args", [])
            text = " ".join([str(arg.get("value", "")) for arg in args if "value" in arg])
            logger.debug(f"CDP Console [{params.get('type')}]: {text}")

        # Dispatch event to callbacks
        for callback in self._event_callbacks.get(method, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(params)
                else:
                    callback(params)
            except Exception as e:
                logger.error(f"Error in event callback for {method}: {e}")

        logger.debug(f"CDP Event: {method}")

    def add_event_listener(self, method: str, callback: Callable) -> None:
        """Register a callback for a CDP event"""
        if method not in self._event_callbacks:
            self._event_callbacks[method] = []
        
        self._event_callbacks[method].append(callback)


class CDPError(Exception):
    """CDP command error"""
    pass
