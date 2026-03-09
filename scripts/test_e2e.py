#!/usr/bin/env python3
"""
End-to-End Test for Trae Bridge
Verifies the complete flow from HTTP API to Trae UI and back.
Requires Trae to be running with CDP enabled.
"""

import sys
import os
import time
import subprocess
import requests
import unittest
import logging
import json
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Test configuration from environment or defaults
TEST_PORT = int(os.environ.get("TRAE_BRIDGE_TEST_PORT", 8769))
BASE_URL = f"http://127.0.0.1:{TEST_PORT}"
CDP_PORT = int(os.environ.get("TRAE_CDP_PORT", 9230))


class TestTraeBridgeE2E(unittest.TestCase):
    # Class attributes for static analysis
    server_process: Optional[subprocess.Popen] = None

    @classmethod
    def setUpClass(cls):
        """Start the API server for E2E testing"""
        logger.info("=" * 60)
        logger.info("STARTING E2E TEST SUITE")
        logger.info("=" * 60)

        # Check if Trae is running on CDP_PORT
        try:
            resp = requests.get(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=2)
            if resp.status_code != 200:
                raise Exception(f"CDP port {CDP_PORT} returned status {resp.status_code}")
            logger.info(f"✓ Trae CDP detected on port {CDP_PORT}")
        except Exception as e:
            print(f"\nERROR: Trae is not running on CDP port {CDP_PORT}.")
            print("Please run: ./scripts/start_trae.sh before running this test.\n")
            sys.exit(1)

        # Start the server
        logger.info(f"Starting API server on port {TEST_PORT}...")
        cls.server_process = subprocess.Popen(
            [sys.executable, "scripts/bridge.py", "--port", str(TEST_PORT), "--cdp-port", str(CDP_PORT)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

        # Wait for server to be ready
        max_retries = 15
        server_ready = False
        for i in range(max_retries):
            # Check if process is still running
            if cls.server_process.poll() is not None:
                stdout, stderr = cls.server_process.communicate()
                raise Exception(f"API server exited unexpectedly with code {cls.server_process.returncode}\nSTDOUT: {stdout}\nSTDERR: {stderr}")

            try:
                resp = requests.get(f"{BASE_URL}/health", timeout=1)
                if resp.status_code == 200:
                    server_ready = True
                    break
            except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
                pass
            
            time.sleep(1)
            logger.info(f"Waiting for server... ({i+1}/{max_retries})")

        if not server_ready:
            cls.server_process.terminate()
            raise Exception(f"API server failed to start on port {TEST_PORT} within {max_retries}s")
        
        logger.info("✓ API server ready")

    @classmethod
    def tearDownClass(cls):
        """Stop the API server"""
        logger.info("=" * 60)
        logger.info("CLEANING UP E2E TESTS")
        logger.info("=" * 60)
        if hasattr(cls, 'server_process'):
            cls.server_process.terminate()
            try:
                cls.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                cls.server_process.kill()
            logger.info("✓ API server stopped")

    def test_01_health_and_connection(self):
        """Check health endpoint and CDP connection status"""
        logger.info("Step 1: Checking health and connection...")
        resp = requests.get(f"{BASE_URL}/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        
        # Connection might be 'connected' or 'disconnected' initially
        # but let's trigger a connection if needed
        if not data.get('connected'):
            logger.info("Triggering initial connection via /history...")
            requests.get(f"{BASE_URL}/history")
            resp = requests.get(f"{BASE_URL}/health")
            data = resp.json()

        self.assertTrue(data.get('connected'), "API should be connected to Trae")
        logger.info("✓ Health and connection OK")

    def test_02_new_chat(self):
        """Test starting a new chat"""
        logger.info("Step 2: Starting new chat...")
        resp = requests.post(f"{BASE_URL}/new")
        self.assertEqual(resp.status_code, 200)
        logger.info("✓ New chat started")

    def test_03_sync_chat(self):
        """Test synchronous chat (send and wait)"""
        logger.info("Step 3: Testing synchronous chat...")
        payload = {
            "message": "Hello Trae! Please reply with 'Trae Bridge represents!'. Only that text.",
            "timeout": 60
        }
        resp = requests.post(f"{BASE_URL}/chat", json=payload, timeout=70)
        self.assertEqual(resp.status_code, 200)
        
        data = resp.json()
        self.assertTrue(data.get('success'))
        response_text = data.get('response', '')
        logger.info(f"AI Response: {response_text}")
        
        self.assertIn("Trae Bridge represents", response_text)
        logger.info("✓ Synchronous chat successful")

    def test_04_async_chat_and_polling(self):
        """Test asynchronous chat and status polling"""
        logger.info("Step 4: Testing asynchronous chat and polling...")
        payload = {
            "message": "Write a short 3-line poem about bridges.",
            "timeout": 60
        }
        resp = requests.post(f"{BASE_URL}/async", json=payload)
        self.assertEqual(resp.status_code, 200)
        
        data = resp.json()
        task_id = data.get('task_id')
        self.assertIsNotNone(task_id)
        logger.info(f"Started async task: {task_id}")

        # Poll for completion
        completed = False
        max_polls = 30
        for i in range(max_polls):
            poll_resp = requests.get(f"{BASE_URL}/task/{task_id}")
            self.assertEqual(poll_resp.status_code, 200)
            status_data = poll_resp.json()
            
            status = status_data.get('status')
            logger.info(f"Task status: {status} ({i+1}/{max_polls})")
            
            if status == 'completed':
                completed = True
                response_text = status_data.get('response')
                self.assertIsNotNone(response_text)
                logger.info(f"Async Response: {response_text[:100]}...")
                break
            elif status == 'failed':
                self.fail(f"Async task failed: {status_data.get('error')}")
            
            time.sleep(2)

        self.assertTrue(completed, "Async task did not complete in time")
        logger.info("✓ Async chat and polling successful")

    def test_05_history(self):
        """Test chat history retrieval"""
        logger.info("Step 5: Checking chat history...")
        resp = requests.get(f"{BASE_URL}/history")
        self.assertEqual(resp.status_code, 200)
        
        data = resp.json()
        messages = data.get('messages', [])
        self.assertGreaterEqual(len(messages), 4) # At least 2 user, 2 assistant

        # Verify we have both user and assistant messages
        roles = [m.get('role') for m in messages]
        user_count = roles.count('user')
        assistant_count = roles.count('assistant')

        logger.info(f"History: {len(messages)} messages ({user_count} user, {assistant_count} assistant)")
        self.assertGreater(user_count, 0, "Should have at least one user message")
        self.assertGreater(assistant_count, 0, "Should have at least one assistant message")

        logger.info("✓ History check successful")


if __name__ == "__main__":
    unittest.main()
