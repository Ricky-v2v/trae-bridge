#!/usr/bin/env python3
"""
Example client for Trae Bridge API
Demonstrates basic usage of all API endpoints
"""

import sys
import time
import requests
import json

API_URL = "http://127.0.0.1:8765"


def print_section(title):
    """Print a formatted section header"""
    print("\n" + "="*60)
    print(title)
    print("="*60)


def check_health():
    """Check if the API is healthy and connected to Trae"""
    print_section("Health Check")

    try:
        response = requests.get(f"{API_URL}/health", timeout=5)
        data = response.json()

        print(f"Status: {data['status']}")
        print(f"Connected: {data['connected']}")

        if not data['connected']:
            print("\n⚠ Warning: Not connected to Trae")
            print("Make sure Trae is running with CDP enabled:")
            print("  ./scripts/start_trae.sh")
            return False

        return True
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to API server")
        print("Make sure the bridge server is running:")
        print("  python scripts/bridge.py")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def send_sync_message(message):
    """Send a message and wait for response"""
    print_section("Synchronous Chat")

    print(f"Sending: {message[:100]}...")

    try:
        response = requests.post(
            f"{API_URL}/chat",
            json={"message": message},
            timeout=200
        )

        data = response.json()

        if data.get("success"):
            print(f"\n✓ Response received:")
            print("-" * 60)
            print(data["response"])
            print("-" * 60)
            return True
        else:
            print(f"✗ Failed: {data}")
            return False

    except requests.exceptions.Timeout:
        print("✗ Request timed out")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def send_async_message(message):
    """Send a message asynchronously and poll for result"""
    print_section("Asynchronous Chat")

    print(f"Sending: {message[:100]}...")

    try:
        # Start async task
        response = requests.post(
            f"{API_URL}/async",
            json={"message": message, "timeout": 180}
        )

        task_data = response.json()
        task_id = task_data["task_id"]
        print(f"Task ID: {task_id}")
        print(f"Status: {task_data['status']}\n")

        # Poll for results
        print("Polling for response...")
        while True:
            status_response = requests.get(f"{API_URL}/task/{task_id}")
            status = status_response.json()

            current_status = status["status"]

            if current_status == "completed":
                print(f"\n✓ Task completed!")
                print("-" * 60)
                print(status["response"])
                print("-" * 60)
                return True
            elif current_status == "failed":
                print(f"\n✗ Task failed: {status.get('error', 'Unknown error')}")
                return False
            else:
                print(f"  Status: {current_status}...")
                time.sleep(2)

    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def get_chat_history():
    """Get the current chat history"""
    print_section("Chat History")

    try:
        response = requests.get(f"{API_URL}/history")
        data = response.json()

        messages = data["messages"]
        print(f"Total messages: {len(messages)}\n")

        for i, msg in enumerate(messages, 1):
            text = msg.get("text", "")
            className = msg.get("className", "")
            print(f"{i}. [{className}]")
            print(f"   {text[:100]}...")
            print()

        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def start_new_chat():
    """Start a new chat session"""
    print_section("New Chat")

    try:
        response = requests.post(f"{API_URL}/new")
        data = response.json()

        if data.get("status") == "success":
            print("✓ New chat started successfully")
            return True
        else:
            print(f"✗ Failed: {data}")
            return False

    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def switch_model(model_name: str) -> bool:
    """Switch the active AI model"""
    print_section(f"Switching Model ({model_name})")

    try:
        response = requests.post(f"{API_URL}/model", json={"model": model_name})
        data = response.json()

        if response.status_code == 200:
            print(f"✓ Model switched successfully: {data['model']}")
            return True
        else:
            print(f"✗ Failed to switch model:")
            print(f"  {data.get('detail', data)}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"✗ Connection error: {e}")
        return False


def list_models():
    """List available AI models"""
    print_section("Available Models")

    try:
        response = requests.get(f"{API_URL}/models")
        data = response.json()

        models = data["models"]
        print(f"Available models ({len(models)}):\n")

        for model in models:
            print(f"  - {model}")

        return True
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


def interactive_mode():
    """Run an interactive chat session"""
    print_section("Interactive Mode")
    print("Type your messages to chat with Trae")
    print("Commands: /new, /history, /quit\n")

    while True:
        try:
            user_input = input("You> ").strip()

            if not user_input:
                continue

            if user_input == "/quit":
                print("Goodbye!")
                break
            elif user_input == "/new":
                start_new_chat()
            elif user_input == "/history":
                get_chat_history()
            else:
                # Send as sync message
                response = requests.post(
                    f"{API_URL}/chat",
                    json={"message": user_input},
                    timeout=180
                )

                data = response.json()
                if data.get("success"):
                    print(f"\nTrae> {data['response']}\n")
                else:
                    print(f"Error: {data}\n")

        except KeyboardInterrupt:
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}\n")


def main():
    """Main example client"""
    print("""
╔═══════════════════════════════════════════════════════════╗
║           Trae Bridge - Example Client                   ║
╚═══════════════════════════════════════════════════════════╝
""")

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "health":
            check_health()
        elif command == "chat":
            if len(sys.argv) > 2:
                send_sync_message(" ".join(sys.argv[2:]))
            else:
                print("Usage: python client.py chat <message>")
        elif command == "async":
            if len(sys.argv) > 2:
                send_async_message(" ".join(sys.argv[2:]))
            else:
                print("Usage: python client.py async <message>")
        elif command == "history":
            get_chat_history()
        elif command == "new":
            start_new_chat()
        elif command == "models":
            list_models()
        elif command == "model":
            if len(sys.argv) > 2:
                switch_model(" ".join(sys.argv[2:]))
            else:
                print("Usage: python client.py model <model_name>")
        elif command == "interactive":
            if check_health():
                interactive_mode()
        else:
            print(f"Unknown command: {command}")
            print_help()
    else:
        # Run demo sequence
        print("Running demo sequence...\n")

        # Check health
        if not check_health():
            print("\n✗ Cannot proceed without connection to Trae")
            sys.exit(1)

        # List models
        list_models()

        # Start new chat
        start_new_chat()

        # Send sync message
        send_sync_message("Hello! Can you write a simple Python function to add two numbers?")

        # Get history
        get_chat_history()

        print("\n" + "="*60)
        print("Demo complete!")
        print("="*60)
        print("\nTry interactive mode:")
        print("  python scripts/client.py interactive")
        print()


def print_help():
    """Print usage help"""
    print("""
Usage: python scripts/client.py [command] [arguments]

Commands:
  health              - Check API health and connection status
  chat <message>      - Send a synchronous message
  async <message>     - Send an asynchronous message
  history             - Get chat history
  new                 - Start a new chat session
  models              - List available models
  model <name>        - Switch to a specific model
  interactive         - Start interactive chat mode

Examples:
  python scripts/client.py health
  python scripts/client.py chat "Hello, Trae!"
  python scripts/client.py model "Claude 3.5 Sonnet"
  python scripts/client.py async "Explain quantum computing"
  python scripts/client.py interactive
    """)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(0)
