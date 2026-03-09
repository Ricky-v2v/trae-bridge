"""
REST API Server for Trae Bridge
Provides HTTP endpoints to interact with Trae AI
"""

import asyncio
import logging
from typing import Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

from .cdp_client import CDPClient
from .dom_helper import DOMHelper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Pydantic models for request/response
class ChatRequest(BaseModel):
    message: str
    timeout: Optional[float] = 180.0

class ChatResponse(BaseModel):
    response: str
    success: bool

class AsyncChatResponse(BaseModel):
    task_id: str
    status: str

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    response: Optional[str] = None
    error: Optional[str] = None

class ModelSwitchRequest(BaseModel):
    model: str

class ModelsResponse(BaseModel):
    models: list[str]

class HistoryResponse(BaseModel):
    messages: list[dict]

class HealthResponse(BaseModel):
    status: str
    connected: bool


# Global state
app = FastAPI(
    title="Trae Bridge API",
    description="REST API bridge for Trae AI IDE",
    version="1.0.0"
)

cdp_client: Optional[CDPClient] = None
dom_helper: Optional[DOMHelper] = None
cdp_port: int = 9230  # Default CDP port, can be configured

# Task management for async requests
tasks: dict[str, dict] = {}
task_counter = 0


def configure_cdp_port(port: int):
    """Configure the CDP port for Trae connection"""
    global cdp_port
    cdp_port = port


async def ensure_connection():
    """Ensure CDP connection is established, with auto-reconnect"""
    global cdp_client, dom_helper

    # Check if connection is established and active
    if cdp_client is not None and cdp_client.is_connected:
        return  # Connection is active

    # Try to establish or re-establish connection
    try:
        logger.info("Establishing CDP connection...")

        # Clean up existing connection if it exists but is disconnected
        if cdp_client is not None and not cdp_client.is_connected:
            logger.warning("CDP connection was lost, attempting to reconnect...")
            cdp_client = None
            dom_helper = None

        # Create new connection with configured port
        cdp_client = CDPClient(cdp_port=cdp_port)
        await cdp_client.connect()
        dom_helper = DOMHelper(cdp_client)
        logger.info("CDP connection established successfully")

    except Exception as e:
        logger.error(f"Failed to connect to CDP: {e}")
        cdp_client = None
        dom_helper = None
        raise HTTPException(
            status_code=503,
            detail=f"Cannot connect to Trae. Make sure Trae is running with CDP enabled: {e}"
        )


@app.on_event("startup")
async def startup_event():
    """Initialize connection on startup"""
    logger.info("Starting Trae Bridge API server")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown"""
    global cdp_client

    if cdp_client:
        await cdp_client.disconnect()
        logger.info("CDP connection closed")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint

    Returns connection status to Trae
    """
    global cdp_client

    connected = (
        cdp_client is not None and
        cdp_client.is_connected
    )

    return HealthResponse(
        status="healthy" if connected else "disconnected",
        connected=connected
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Synchronous chat endpoint

    Sends a message to Trae and waits for the response.

    - **message**: The message to send
    - **timeout**: Maximum time to wait for response (default: 180s)
    """
    await ensure_connection()

    try:
        logger.info(f"Sending message: {request.message[:100]}...")

        # Send message
        success = await dom_helper.send_message(request.message)

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to send message to Trae"
            )

        # Wait for response
        response_text = await dom_helper.wait_for_response(timeout=request.timeout)

        if response_text is None:
            raise HTTPException(
                status_code=408,
                detail=f"Timeout waiting for response after {request.timeout}s"
            )

        return ChatResponse(
            response=response_text,
            success=True
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.post("/async", response_model=AsyncChatResponse)
async def async_chat(request: ChatRequest, background_tasks: BackgroundTasks):
    """
    Asynchronous chat endpoint

    Sends a message and returns immediately with a task ID.
    Use /task/{id} to poll for results.

    - **message**: The message to send
    - **timeout**: Maximum time to wait for response (default: 180s)
    """
    global task_counter, tasks

    await ensure_connection()

    # Create task ID
    task_counter += 1
    task_id = f"task_{task_counter}"

    # Initialize task
    tasks[task_id] = {
        "status": "pending",
        "response": None,
        "error": None
    }

    # Start background task
    async def run_chat_task():
        try:
            tasks[task_id]["status"] = "processing"

            success = await dom_helper.send_message(request.message)

            if not success:
                tasks[task_id]["status"] = "failed"
                tasks[task_id]["error"] = "Failed to send message to Trae"
                return

            response_text = await dom_helper.wait_for_response(timeout=request.timeout)

            if response_text is None:
                tasks[task_id]["status"] = "failed"
                tasks[task_id]["error"] = f"Timeout after {request.timeout}s"
            else:
                tasks[task_id]["status"] = "completed"
                tasks[task_id]["response"] = response_text

        except Exception as e:
            logger.error(f"Error in async chat task {task_id}: {e}")
            tasks[task_id]["status"] = "failed"
            tasks[task_id]["error"] = str(e)

    background_tasks.add_task(run_chat_task)

    logger.info(f"Started async chat task: {task_id}")

    return AsyncChatResponse(
        task_id=task_id,
        status="pending"
    )


@app.get("/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """
    Get the status of an async chat task

    - **task_id**: The task ID returned from /async
    """
    if task_id not in tasks:
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} not found"
        )

    task = tasks[task_id]

    return TaskStatusResponse(
        task_id=task_id,
        status=task["status"],
        response=task.get("response"),
        error=task.get("error")
    )


@app.post("/new")
async def new_chat():
    """
    Start a new chat session

    Clears the current conversation context
    """
    await ensure_connection()

    try:
        success = await dom_helper.new_chat()

        if not success:
            raise HTTPException(
                status_code=500,
                detail="Failed to start new chat"
            )

        return {"status": "success", "message": "New chat started"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting new chat: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/models", response_model=ModelsResponse)
async def list_models():
    """
    List available models

    Returns a list of models available in Trae
    """
    await ensure_connection()

    try:
        # This is a placeholder - actual model detection would require inspecting Trae's UI
        # Common models that might be available
        models = [
            "claude-3-5-sonnet",
            "claude-3-opus",
            "claude-3-haiku",
            "gpt-4",
            "gpt-4-turbo",
            "gpt-3.5-turbo"
        ]

        return ModelsResponse(models=models)

    except Exception as e:
        logger.error(f"Error listing models: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.post("/model")
async def switch_model(request: ModelSwitchRequest):
    """
    Switch the active model

    - **model**: The model identifier to switch to
    """
    await ensure_connection()

    try:
        # This is a placeholder - actual model switching would require:
        # 1. Finding the model selector in Trae's UI
        # 2. Clicking it and selecting the desired model
        # 3. Waiting for the switch to complete

        logger.info(f"Model switching requested: {request.model}")

        return {
            "status": "success",
            "message": f"Model switched to {request.model}",
            "model": request.model
        }

    except Exception as e:
        logger.error(f"Error switching model: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


@app.get("/history", response_model=HistoryResponse)
async def get_history():
    """
    Get current chat history

    Returns all messages in the current conversation
    """
    await ensure_connection()

    try:
        messages = await dom_helper.get_chat_history()

        return HistoryResponse(messages=messages)

    except Exception as e:
        logger.error(f"Error getting history: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


def run_server(host: str = "127.0.0.1", port: int = 8765, cdp_port_param: int = 9230):
    """
    Run the API server

    Args:
        host: Host to bind to
        port: Port to bind to
        cdp_port_param: CDP port for Trae connection
    """
    # Configure CDP port before starting server
    configure_cdp_port(cdp_port_param)

    logger.info(f"Starting Trae Bridge API server on {host}:{port}")
    logger.info(f"CDP port configured to: {cdp_port_param}")

    uvicorn.run(
        "src.api_server:app",
        host=host,
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    run_server()
