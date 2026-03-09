#!/usr/bin/env python3
"""
Test API Server Startup
Verifies that the API server can start up and respond to health checks
"""

import sys
import os
import time
import subprocess
import requests
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_server_startup():
    """Test that the API server can start up"""

    logger.info("="*60)
    logger.info("API SERVER STARTUP TEST")
    logger.info("="*60)
    logger.info("")

    # Start the server
    logger.info("Starting API server...")
    server_process = subprocess.Popen(
        [sys.executable, "scripts/bridge.py", "--port", "8766"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    # Give server time to start
    logger.info("Waiting for server to start...")
    time.sleep(3)

    try:
        # Test health endpoint
        logger.info("Testing health endpoint...")
        response = requests.get("http://127.0.0.1:8766/health", timeout=5)

        if response.status_code == 200:
            data = response.json()
            logger.info(f"✓ Health check successful")
            logger.info(f"  Status: {data.get('status')}")
            logger.info(f"  Connected: {data.get('connected')}")

            # Test OpenAPI docs endpoint
            logger.info("Testing OpenAPI docs endpoint...")
            docs_response = requests.get("http://127.0.0.1:8766/docs", timeout=5)

            if docs_response.status_code == 200:
                logger.info("✓ OpenAPI docs available")
            else:
                logger.warning("✗ OpenAPI docs not available")

            logger.info("")
            logger.info("="*60)
            logger.info("✓ API SERVER STARTUP TEST PASSED")
            logger.info("="*60)
            logger.info("")
            logger.info("Server is running and responding to requests.")
            logger.info("")
            logger.info("Available endpoints:")
            logger.info("  POST /chat           - Synchronous chat")
            logger.info("  POST /async          - Asynchronous chat")
            logger.info("  GET  /task/{id}      - Get async task status")
            logger.info("  POST /new            - Start new chat")
            logger.info("  GET  /health         - Health check")
            logger.info("  GET  /models         - List available models")
            logger.info("  POST /model          - Switch model")
            logger.info("  GET  /history        - Get chat history")
            logger.info("")
            logger.info("API documentation: http://127.0.0.1:8766/docs")
            logger.info("="*60)

            return True
        else:
            logger.error(f"✗ Health check failed with status {response.status_code}")
            return False

    except requests.exceptions.ConnectionError:
        logger.error("✗ Cannot connect to API server")
        logger.error("  Server may have failed to start")
        return False
    except requests.exceptions.Timeout:
        logger.error("✗ Request timed out")
        return False
    except Exception as e:
        logger.error(f"✗ Test failed: {e}")
        return False
    finally:
        # Stop the server
        logger.info("Stopping server...")
        server_process.terminate()
        try:
            server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server_process.kill()
        logger.info("Server stopped")


def test_cli_arguments():
    """Test that CLI arguments are properly handled"""

    logger.info("")
    logger.info("="*60)
    logger.info("CLI ARGUMENTS TEST")
    logger.info("="*60)
    logger.info("")

    # Test help
    logger.info("Testing --help argument...")
    result = subprocess.run(
        [sys.executable, "scripts/bridge.py", "--help"],
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        logger.info("✓ --help works")

        # Check for expected arguments
        expected_args = ["--host", "--port", "--cdp-port", "--log-level"]
        for arg in expected_args:
            if arg in result.stdout:
                logger.info(f"  ✓ {arg} documented")
            else:
                logger.warning(f"  ✗ {arg} not documented")
    else:
        logger.error("✗ --help failed")
        return False

    logger.info("")
    logger.info("="*60)
    logger.info("✓ CLI ARGUMENTS TEST PASSED")
    logger.info("="*60)

    return True


def test_requirements():
    """Test that all required packages are installed"""

    logger.info("")
    logger.info("="*60)
    logger.info("REQUIREMENTS TEST")
    logger.info("="*60)
    logger.info("")

    required_packages = [
        "websockets",
        "aiohttp",
        "fastapi",
        "uvicorn",
        "pydantic"
    ]

    all_installed = True
    for package in required_packages:
        try:
            __import__(package)
            logger.info(f"✓ {package}")
        except ImportError:
            logger.error(f"✗ {package} not installed")
            all_installed = False

    logger.info("")
    if all_installed:
        logger.info("="*60)
        logger.info("✓ REQUIREMENTS TEST PASSED")
        logger.info("="*60)
    else:
        logger.info("="*60)
        logger.error("✗ REQUIREMENTS TEST FAILED")
        logger.error("  Install missing packages:")
        logger.error("  pip install -r requirements.txt")
        logger.info("="*60)

    return all_installed


if __name__ == "__main__":
    logger.info("TRAE BRIDGE SYSTEM TESTS")
    logger.info("")

    results = []

    # Run tests
    results.append(test_requirements())
    results.append(test_cli_arguments())
    results.append(test_server_startup())

    # Overall summary
    logger.info("")
    logger.info("="*60)
    logger.info("OVERALL TEST SUMMARY")
    logger.info("="*60)

    total = len(results)
    passed = sum(results)
    failed = total - passed

    logger.info(f"Total Tests: {total}")
    logger.info(f"Passed: {passed}")
    logger.info(f"Failed: {failed}")
    logger.info(f"Success Rate: {(passed/total*100):.1f}%")

    if failed == 0:
        logger.info("")
        logger.info("✓ ALL SYSTEM TESTS PASSED!")
        logger.info("")
        logger.info("The Trae Bridge system is ready to use.")
        logger.info("")
        logger.info("To start using the bridge:")
        logger.info("1. Start Trae with CDP: ./scripts/start_trae.sh")
        logger.info("2. Start API server: python scripts/bridge.py")
        logger.info("3. Test API: curl http://127.0.0.1:8765/health")
    else:
        logger.info("")
        logger.error("✗ SOME SYSTEM TESTS FAILED")
        logger.error("Please check the errors above.")

    logger.info("="*60)

    sys.exit(0 if all(results) else 1)
