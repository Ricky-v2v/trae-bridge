import unittest
from unittest.mock import AsyncMock, patch
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from src.api_server import app
import src.api_server as api_server

class TestAPIServerModelSwitch(unittest.TestCase):
    def setUp(self):
        # We need to mock dom_helper functions used by the API
        self.patcher = patch('src.api_server.dom_helper')
        self.mock_dom_helper = self.patcher.start()
        
        # Also mock the CDP connection checks
        self.conn_patcher = patch('src.api_server.ensure_connection', new_callable=AsyncMock)
        self.mock_ensure_connection = self.conn_patcher.start()

        self.client = TestClient(app)

    def tearDown(self):
        self.patcher.stop()
        self.conn_patcher.stop()

    def test_switch_model_success(self):
        """Test API successfully switching models"""
        # Mock switch_model to return True (success)
        self.mock_dom_helper.switch_model = AsyncMock(return_value=True)

        # Make the request
        response = self.client.post(
            "/model",
            json={"model": "Claude 3.5 Sonnet"}
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["model"], "Claude 3.5 Sonnet")
        self.assertIn("switched to Claude 3.5 Sonnet", data["message"])

        # Verify interaction
        self.mock_dom_helper.switch_model.assert_called_once_with("Claude 3.5 Sonnet")
        self.mock_ensure_connection.assert_called_once()


    def test_switch_model_failure_not_available(self):
        """Test API handles UI failure gracefully (e.g. model not available)"""
        # Mock switch_model to return False (UI failed)
        self.mock_dom_helper.switch_model = AsyncMock(return_value=False)

        response = self.client.post(
            "/model",
            json={"model": "Unknown Model XYZ"}
        )

        self.assertEqual(response.status_code, 400)
        data = response.json()
        self.assertIn("Failed to apply model switch in UI", data["detail"])

    def test_switch_model_internal_error(self):
        """Test handling of unexpected exceptions from dom_helper"""
        # Mock switch_model to raise Exception
        self.mock_dom_helper.switch_model = AsyncMock(side_effect=Exception("Database down"))

        response = self.client.post(
            "/model",
            json={"model": "GPT-4"}
        )

        self.assertEqual(response.status_code, 500)
        data = response.json()
        self.assertIn("Internal server error: Database down", data["detail"])


if __name__ == '__main__':
    unittest.main()
