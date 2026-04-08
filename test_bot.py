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

    @patch("telegram_bot.requests.post")
    def test_send_message_truncation(self, mock_post):
        long_text = "a" * 5000
        telegram_bot.send_message(123, long_text)
        args, kwargs = mock_post.call_args
        self.assertTrue(len(kwargs["data"]["text"]) <= 4000)
        self.assertTrue(kwargs["data"]["text"].endswith("..."))

    @patch("telegram_bot.subprocess.run")
    def test_call_gemini_success(self, mock_run):
        # Mock successful JSON response from Gemini CLI
        mock_output = json.dumps({"response": "Hello from Gemini"})
        mock_run.return_value = MagicMock(stdout=mock_output, stderr="", returncode=0)
        
        response = telegram_bot.call_gemini("hi")
        self.assertEqual(response, "Hello from Gemini")

    @patch("telegram_bot.subprocess.run")
    def test_call_gemini_no_json(self, mock_run):
        # Mock non-JSON response
        mock_run.return_value = MagicMock(stdout="Some random text", stderr="error log", returncode=1)
        
        response = telegram_bot.call_gemini("hi")
        self.assertIn("Could not parse Gemini output", response)

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
