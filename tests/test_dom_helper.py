import unittest
from unittest.mock import AsyncMock, patch
import asyncio
import os
import sys

# Add parent directory to path to import src modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.dom_helper import DOMHelper
from src.cdp_client import CDPClient


class TestDOMHelperSwitchModel(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Create a mock CDP client with AsyncMock for async methods
        self.mock_cdp = AsyncMock(spec=CDPClient)
        # We need to mock the evaluate method as it's the main point of interaction
        self.dom_helper = DOMHelper(cdp_client=self.mock_cdp)

    async def test_switch_model_success(self):
        """Test successful model switching scenario"""
        # Set up mock behavior for evaluate:
        # First call: opening dropdown -> returns True
        # Second call: finding and clicking model in list -> returns True
        self.mock_cdp.evaluate.side_effect = [True, True]

        # Call the method
        result = await self.dom_helper.switch_model("Claude 3.5 Sonnet")
        
        # Verify result is True for success
        self.assertTrue(result)
        
        # Verify evaluate was called exactly twice
        self.assertEqual(self.mock_cdp.evaluate.call_count, 2)
        
        # Verify first call script structure (looking for trigger)
        first_call_script = self.mock_cdp.evaluate.call_args_list[0][0][0]
        self.assertIn("icd-model-select-trigger", first_call_script)
        
        # Verify second call script structure (searching for cleaned model name)
        second_call_script = self.mock_cdp.evaluate.call_args_list[1][0][0]
        # Should have lowercased and stripped spaces
        self.assertIn("claude3.5sonnet", second_call_script)

    async def test_switch_model_trigger_not_found(self):
        """Test failure when the model selector dropdown trigger isn't found"""
        # First call evaluates to False
        self.mock_cdp.evaluate.return_value = False

        # Call the method
        result = await self.dom_helper.switch_model("GPT-4")
        
        # Verify result is False
        self.assertFalse(result)
        
        # Verify evaluate was only called once
        self.assertEqual(self.mock_cdp.evaluate.call_count, 1)

    async def test_switch_model_not_found_in_list(self):
        """Test failure when model isn't in the dropdown list, and ensure fallback cleanup occurs"""
        # First call (open dropdown): True
        # Second call (find model): False
        # Third call (cleanup modal click): None
        self.mock_cdp.evaluate.side_effect = [True, False, None]

        # Call the method
        result = await self.dom_helper.switch_model("Nonexistent Model XYZ")

        # Verify result is False
        self.assertFalse(result)
        
        # Verify evaluate was called three times (including the fallback body click)
        self.assertEqual(self.mock_cdp.evaluate.call_count, 3)

        # Check the cleanup script
        third_call_script = self.mock_cdp.evaluate.call_args_list[2][0][0]
        self.assertEqual("document.body.click();", third_call_script)

    async def test_switch_model_unexpected_exception(self):
        """Test handling of unexpected exceptions raised during CDP operations"""
        # Make evaluate raise an arbitrary Exception
        self.mock_cdp.evaluate.side_effect = Exception("CDP Disconnected")

        result = await self.dom_helper.switch_model("Claude")

        # The method should catch the exception and return False safely
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()
