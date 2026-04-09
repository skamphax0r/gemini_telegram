import unittest
from unittest.mock import patch, MagicMock
import json
import os
import subprocess

# Mock environment variables before importing the bot
os.environ["TELEGRAM_BOT_TOKEN"] = "test_token"
os.environ["ALLOWED_USER_ID"] = "12345"

import telegram_bot

class TestGeminiBot(unittest.TestCase):

    def setUp(self):
        telegram_bot.user_sessions = {}

    def test_task_dataclass(self):
        task = telegram_bot.Task(chat_id=1, user_id="123", prompt="test")
        self.assertEqual(task.status, "pending")
        self.assertEqual(task.prompt, "test")

    @patch("telegram_bot.requests.post")
    def test_send_message(self, mock_post):
        telegram_bot.send_message(123, "hello")
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        self.assertIn("chat_id", kwargs["data"])
        self.assertEqual(kwargs["data"]["text"], "hello")

    @patch("telegram_bot.subprocess.run")
    def test_call_gemini_with_session(self, mock_run):
        # Mock session persistence
        telegram_bot.user_sessions["12345"] = "old-uuid"
        
        mock_output = json.dumps({"response": "Resumed response"})
        mock_run.return_value = MagicMock(stdout=mock_output, stderr="", returncode=0)
        
        response = telegram_bot.call_gemini("continue", user_id="12345")
        self.assertEqual(response, "Resumed response")
        
        # Verify --resume was used
        args, kwargs = mock_run.call_args
        self.assertIn("--resume", args[0])
        self.assertIn("old-uuid", args[0])

    @patch("telegram_bot.subprocess.run")
    def test_call_gemini_new_session_discovery(self, mock_run):
        # 1. First call to gemini
        mock_output_1 = json.dumps({"response": "New response"})
        mock_run_1 = MagicMock(stdout=mock_output_1, stderr="", returncode=0)
        
        # 2. Call to gemini --list-sessions
        mock_output_2 = "1. test [new-uuid]"
        mock_run_2 = MagicMock(stdout=mock_output_2, stderr="", returncode=0)
        
        mock_run.side_effect = [mock_run_1, mock_run_2]
        
        with patch("telegram_bot.save_sessions"): # Avoid writing to disk
            response = telegram_bot.call_gemini("hello", user_id="12345")
        
        self.assertEqual(response, "New response")
        self.assertEqual(telegram_bot.user_sessions["12345"], "new-uuid")

    @patch("telegram_bot.requests.get")
    def test_get_updates(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {"ok": True, "result": []}
        mock_get.return_value = mock_response
        
        updates = telegram_bot.get_updates()
        self.assertTrue(updates["ok"])
        mock_get.assert_called_once()

if __name__ == "__main__":
    unittest.main()
