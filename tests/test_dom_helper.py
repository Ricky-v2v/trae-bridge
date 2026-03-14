import unittest
from unittest.mock import AsyncMock, patch
import time
import os
import sys

# Add parent directory to path to import src modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.dom_helper import DOMHelper
from src.cdp_client import CDPClient


class TestDOMHelperSwitchModel(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_cdp = AsyncMock(spec=CDPClient)
        self.dom_helper = DOMHelper(cdp_client=self.mock_cdp)

    async def test_switch_model_success(self):
        """Successful switch resolves the best match and verifies selected model."""
        self.mock_cdp.evaluate.side_effect = [
            True,   # open trigger
            True,   # dropdown visible
            ["Gemini-3-Pro-Preview", "Gemini-3-Flash-Preview"],  # dropdown options
            True,   # click resolved option
            "Gemini-3-Pro-Preview",  # currently selected
        ]

        result = await self.dom_helper.switch_model("gemini-3-pro")
        self.assertTrue(result)
        self.assertEqual(self.mock_cdp.evaluate.call_count, 5)

    async def test_switch_model_trigger_not_found(self):
        """Fail when model selector trigger cannot be opened."""
        self.mock_cdp.evaluate.return_value = False
        result = await self.dom_helper.switch_model("GPT-4")
        self.assertFalse(result)
        self.assertEqual(self.mock_cdp.evaluate.call_count, 1)

    async def test_switch_model_not_found_in_list(self):
        """No match in available list should return friendly error and cleanup UI."""
        self.mock_cdp.evaluate.side_effect = [
            True,   # open trigger
            True,   # dropdown visible
            ["Gemini-3-Flash-Preview", "Claude-3.5-Sonnet"],  # options
            None,   # body click cleanup
        ]

        result = await self.dom_helper.switch_model("Nonexistent Model XYZ")
        self.assertFalse(result)
        self.assertEqual(self.mock_cdp.evaluate.call_count, 4)

        error = self.dom_helper.get_last_model_switch_error()
        self.assertIsNotNone(error)
        self.assertIn("No model matched", error)

    async def test_switch_model_post_check_rejects_wrong_selected_model(self):
        """Clicking succeeds but wrong final selected model should fail."""
        self.mock_cdp.evaluate.side_effect = [
            True,   # open trigger
            True,   # dropdown visible
            ["Gemini-3-Pro-Preview", "Gemini-3-Flash-Preview"],  # options
            True,   # click resolved option
            "Gemini-3-Flash-Preview",  # selected does not match request
            None,   # body click cleanup after failed verification
        ]

        result = await self.dom_helper.switch_model("gemini-3-pro")
        self.assertFalse(result)
        self.assertEqual(self.mock_cdp.evaluate.call_count, 6)

        error = self.dom_helper.get_last_model_switch_error()
        self.assertIsNotNone(error)
        self.assertIn("verification failed", error)

    async def test_switch_model_unexpected_exception(self):
        """Unexpected CDP error should be handled safely."""
        self.mock_cdp.evaluate.side_effect = Exception("CDP Disconnected")
        result = await self.dom_helper.switch_model("Claude")
        self.assertFalse(result)


class TestModelNameMatching(unittest.TestCase):
    def setUp(self):
        self.mock_cdp = AsyncMock(spec=CDPClient)
        self.dom_helper = DOMHelper(cdp_client=self.mock_cdp)
        self.available = [
            "Gemini-3-Pro-Preview",
            "Gemini-3-Flash-Preview",
            "Claude 3.5 Sonnet",
            "GPT-4o",
        ]

    def test_case_insensitive_and_special_char_agnostic(self):
        for query in ["gemini-3-pro", "GEMINI 3 PRO", "GeMiNi_3@PrO!!!"]:
            matched, error = self.dom_helper.match_model_name(query, self.available)
            self.assertEqual(matched, "Gemini-3-Pro-Preview")
            self.assertIsNone(error)

    def test_prefix_match(self):
        matched, error = self.dom_helper.match_model_name("gemini3pro", self.available)
        self.assertEqual(matched, "Gemini-3-Pro-Preview")
        self.assertIsNone(error)

    def test_alias_map_match(self):
        matched, error = self.dom_helper.match_model_name("g3p", self.available)
        self.assertEqual(matched, "Gemini-3-Pro-Preview")
        self.assertIsNone(error)

    def test_priority_avoids_flash_when_pro_requested(self):
        matched, error = self.dom_helper.match_model_name("gemini pro", self.available)
        self.assertEqual(matched, "Gemini-3-Pro-Preview")
        self.assertIsNone(error)

    def test_friendly_error_when_no_match(self):
        matched, error = self.dom_helper.match_model_name("totally-unknown-model", self.available)
        self.assertIsNone(matched)
        self.assertIsNotNone(error)
        self.assertIn("No model matched", error)

    def test_extreme_input_empty(self):
        matched, error = self.dom_helper.match_model_name("   ", self.available)
        self.assertIsNone(matched)
        self.assertIn("empty", (error or "").lower())

    def test_extreme_input_only_symbols(self):
        matched, error = self.dom_helper.match_model_name("!!!###@@@", self.available)
        self.assertIsNone(matched)
        self.assertIn("invalid", (error or "").lower())

    def test_performance_large_model_list(self):
        large_list = [f"Model-{i}-Preview" for i in range(10000)] + self.available
        t0 = time.perf_counter()
        matched, error = self.dom_helper.match_model_name("gemini-3-pro", large_list)
        elapsed = time.perf_counter() - t0

        self.assertEqual(matched, "Gemini-3-Pro-Preview")
        self.assertIsNone(error)
        self.assertLess(elapsed, 0.8)


class TestDOMHelperInputClearing(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.mock_cdp = AsyncMock(spec=CDPClient)
        self.dom_helper = DOMHelper(cdp_client=self.mock_cdp)

    async def test_clear_input_box_success_with_confirmation(self):
        """Clear should confirm empty input before returning success."""
        self.mock_cdp.evaluate.side_effect = [
            False,  # initial _is_input_empty
            True,   # clear attempt
            True,   # post-clear _is_input_empty
        ]

        result = await self.dom_helper._clear_input_box("div[role='textbox']", retries=2)
        self.assertTrue(result)
        self.assertEqual(self.mock_cdp.evaluate.call_count, 3)

    async def test_clear_input_box_failure_after_retries(self):
        """Clear should fail safely when input cannot be emptied."""
        self.mock_cdp.evaluate.side_effect = [
            False,  # initial _is_input_empty
            True,   # clear attempt 1
            False,  # post-clear check 1
            True,   # clear attempt 2
            False,  # post-clear check 2
        ]

        result = await self.dom_helper._clear_input_box("div[role='textbox']", retries=2)
        self.assertFalse(result)
        self.assertEqual(self.mock_cdp.evaluate.call_count, 5)

    async def test_send_message_aborts_when_input_not_cleared(self):
        """send_message must stop if clear step cannot guarantee empty input."""
        with patch.object(self.dom_helper, "_inject_completion_observer", new=AsyncMock(return_value=True)):
            with patch.object(self.dom_helper, "_clear_input_box", new=AsyncMock(return_value=False)) as clear_mock:
                result = await self.dom_helper.send_message("hello", input_selector="div[role='textbox']")

        self.assertFalse(result)
        clear_mock.assert_called_once()


if __name__ == '__main__':
    unittest.main()
