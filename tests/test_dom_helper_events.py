import unittest
from unittest.mock import AsyncMock, patch
import asyncio
import os
import sys

# Add parent directory to path to import src modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.dom_helper import DOMHelper
from src.cdp_client import CDPClient

class TestDOMHelperEvents(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_cdp = AsyncMock(spec=CDPClient)
        self.dom_helper = DOMHelper(cdp_client=self.mock_cdp)

    async def test_handle_console_event_completion_signal(self):
        """Test that TRAE_BRIDGE:FINISHED sets the completion event"""
        # Initially, the event is clear
        self.assertFalse(self.dom_helper._response_finished_event.is_set())

        # Simulate console event params with the completion string
        mock_params = {
            "args": [
                {"value": "TRAE_BRIDGE:FINISHED"}
            ]
        }
        
        # Call the private handler directly
        await self.dom_helper._handle_console_event(mock_params)
        
        # Verify the event got set
        self.assertTrue(self.dom_helper._response_finished_event.is_set())

    async def test_handle_console_event_ignore_other(self):
        """Test that random console logs do not set the completion event"""
        self.assertFalse(self.dom_helper._response_finished_event.is_set())

        mock_params = {
            "args": [
                {"value": "Some other debug log"}
            ]
        }
        
        await self.dom_helper._handle_console_event(mock_params)
        
        self.assertFalse(self.dom_helper._response_finished_event.is_set())

    async def test_wait_for_response_resolves_on_event(self):
        """Test that wait_for_response returns when event is set without needing polling"""
        # Mock finding elements to be fast so we only test the wait logic
        self.dom_helper.find_input_element = AsyncMock(return_value="input-selector")
        self.dom_helper.get_last_ai_message = AsyncMock(return_value={"text": "Hello User"})
        
        # We need a task that will call wait_for_response
        wait_task = asyncio.create_task(self.dom_helper.wait_for_response())
        
        # It shouldn't finish immediately (it waits for the event)
        await asyncio.sleep(0.01)
        self.assertFalse(wait_task.done())
        
        # Now trigger the event as if a console log arrived
        self.dom_helper._response_finished_event.set()
        
        # Wait task should now resolve (maybe after a brief inner loop fallback)
        result = await asyncio.wait_for(wait_task, timeout=1.0)
        self.assertTrue(result)

if __name__ == '__main__':
    unittest.main()
