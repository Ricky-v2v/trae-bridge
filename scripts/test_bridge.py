#!/usr/bin/env python3
"""
Test Suite for Trae Bridge
Tests all components: CDP connection, DOM operations, and API endpoints
"""

import sys
import os
import asyncio
import json
import time
import logging

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.cdp_client import CDPClient
from src.dom_helper import DOMHelper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TraeBridgeTester:
    """Test suite for Trae Bridge components"""

    def __init__(self, cdp_port: int = 9230):
        self.cdp_port = cdp_port
        self.cdp_client = None
        self.dom_helper = None
        self.test_results = []

    def log_result(self, test_name: str, passed: bool, message: str = ""):
        """Log a test result"""
        status = "✓ PASS" if passed else "✗ FAIL"
        result = f"{status}: {test_name}"
        if message:
            result += f" - {message}"

        logger.info(result)
        self.test_results.append({
            "name": test_name,
            "passed": passed,
            "message": message
        })

    async def test_cdp_connection(self):
        """Test CDP connection to Trae"""
        logger.info("\n" + "="*60)
        logger.info("TEST 1: CDP Connection")
        logger.info("="*60)

        try:
            self.cdp_client = CDPClient(cdp_port=self.cdp_port)
            await self.cdp_client.connect()

            self.log_result(
                "CDP Connection",
                True,
                f"Connected to Trae on port {self.cdp_port}"
            )

            # Test basic JavaScript execution
            result = await self.cdp_client.evaluate("1 + 1")
            if result == 2:
                self.log_result(
                    "CDP JavaScript Execution",
                    True,
                    "Basic JS evaluation works"
                )
            else:
                self.log_result(
                    "CDP JavaScript Execution",
                    False,
                    f"Expected 2, got {result}"
                )

        except Exception as e:
            self.log_result("CDP Connection", False, str(e))
            logger.error(f"CDP connection failed: {e}")
            raise

    async def test_dom_analysis(self):
        """Test DOM element detection"""
        logger.info("\n" + "="*60)
        logger.info("TEST 2: DOM Analysis")
        logger.info("="*60)

        try:
            self.dom_helper = DOMHelper(self.cdp_client)

            # Test input element detection
            input_selector = await self.dom_helper.find_input_element()
            if input_selector:
                self.log_result(
                    "Input Element Detection",
                    True,
                    f"Found input using: {input_selector}"
                )
            else:
                self.log_result(
                    "Input Element Detection",
                    False,
                    "Could not find input element"
                )

            # Test send button detection
            send_selector = await self.dom_helper.find_send_button()
            if send_selector:
                self.log_result(
                    "Send Button Detection",
                    True,
                    f"Found button using: {send_selector}"
                )
            else:
                self.log_result(
                    "Send Button Detection",
                    False,
                    "Could not find send button"
                )

            # Test message container detection
            last_message = await self.dom_helper.get_last_ai_message()
            if last_message:
                self.log_result(
                    "Message Detection",
                    True,
                    f"Found message with {len(last_message.get('text', ''))} chars"
                )
            else:
                self.log_result(
                    "Message Detection",
                    False,
                    "Could not find messages"
                )

        except Exception as e:
            self.log_result("DOM Analysis", False, str(e))
            logger.error(f"DOM analysis failed: {e}")

    async def test_chat_operations(self):
        """Test chat send and receive operations"""
        logger.info("\n" + "="*60)
        logger.info("TEST 3: Chat Operations")
        logger.info("="*60)

        try:
            # Test sending a simple message
            test_message = "Hello, this is a test message from Trae Bridge!"

            logger.info(f"Sending test message: {test_message}")
            success = await self.dom_helper.send_message(test_message)

            if success:
                self.log_result(
                    "Send Message",
                    True,
                    "Message sent successfully"
                )

                # Wait for response (with shorter timeout for testing)
                logger.info("Waiting for response...")
                response = await self.dom_helper.wait_for_response(timeout=60.0)

                if response:
                    self.log_result(
                        "Receive Response",
                        True,
                        f"Got response with {len(response)} characters"
                    )
                    logger.info(f"Response preview: {response[:200]}...")
                else:
                    self.log_result(
                        "Receive Response",
                        False,
                        "No response received (timeout)"
                    )
            else:
                self.log_result(
                    "Send Message",
                    False,
                    "Failed to send message"
                )

        except Exception as e:
            self.log_result("Chat Operations", False, str(e))
            logger.error(f"Chat operations test failed: {e}")

    async def test_chat_history(self):
        """Test chat history retrieval"""
        logger.info("\n" + "="*60)
        logger.info("TEST 4: Chat History")
        logger.info("="*60)

        try:
            messages = await self.dom_helper.get_chat_history()

            if messages:
                self.log_result(
                    "Chat History",
                    True,
                    f"Retrieved {len(messages)} messages"
                )
                logger.info(f"First message preview: {messages[0].get('text', '')[:100]}...")
            else:
                self.log_result(
                    "Chat History",
                    False,
                    "No messages retrieved"
                )

        except Exception as e:
            self.log_result("Chat History", False, str(e))
            logger.error(f"Chat history test failed: {e}")

    async def test_new_chat(self):
        """Test starting a new chat"""
        logger.info("\n" + "="*60)
        logger.info("TEST 5: New Chat")
        logger.info("="*60)

        try:
            success = await self.dom_helper.new_chat()

            if success:
                self.log_result(
                    "New Chat",
                    True,
                    "New chat started successfully"
                )
            else:
                self.log_result(
                    "New Chat",
                    False,
                    "Failed to start new chat"
                )

        except Exception as e:
            self.log_result("New Chat", False, str(e))
            logger.error(f"New chat test failed: {e}")

    async def cleanup(self):
        """Clean up resources"""
        if self.cdp_client:
            await self.cdp_client.disconnect()
            logger.info("CDP connection closed")

    def print_summary(self):
        """Print test summary"""
        logger.info("\n" + "="*60)
        logger.info("TEST SUMMARY")
        logger.info("="*60)

        total = len(self.test_results)
        passed = sum(1 for r in self.test_results if r["passed"])
        failed = total - passed

        logger.info(f"Total Tests: {total}")
        logger.info(f"Passed: {passed}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Success Rate: {(passed/total*100):.1f}%")

        if failed > 0:
            logger.info("\nFailed Tests:")
            for result in self.test_results:
                if not result["passed"]:
                    logger.info(f"  ✗ {result['name']}: {result['message']}")

        logger.info("="*60)

        return failed == 0


async def run_tests():
    """Run all tests"""
    logger.info("="*60)
    logger.info("TRAE BRIDGE TEST SUITE")
    logger.info("="*60)
    logger.info("Make sure Trae is running with CDP enabled!")
    logger.info("Run: ./scripts/start_trae.sh")
    logger.info("="*60)

    tester = TraeBridgeTester(cdp_port=9230)

    try:
        # Run tests
        await tester.test_cdp_connection()
        await tester.test_dom_analysis()

        # Only run chat tests if basic components work
        if tester.cdp_client and tester.dom_helper:
            await tester.test_chat_operations()
            await tester.test_chat_history()
            await tester.test_new_chat()

    except Exception as e:
        logger.error(f"Test suite failed: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await tester.cleanup()
        tester.print_summary()


if __name__ == "__main__":
    try:
        asyncio.run(run_tests())
    except KeyboardInterrupt:
        logger.info("\nTests interrupted by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)