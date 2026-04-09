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

    @patch("telegram_bot.subprocess.run")
    def test_call_gemini_with_session(self, mock_run):
        telegram_bot.user_sessions["12345"] = "old-uuid"
        mock_output = json.dumps({"response": "Resumed response"})
        mock_run.return_value = MagicMock(stdout=mock_output, stderr="", returncode=0)
        
        response = telegram_bot.call_gemini("continue", user_id="12345")
        self.assertEqual(response, "Resumed response")

    @patch("telegram_bot.call_gemini")
    def test_parse_intent_scheduled(self, mock_call):
        # Mock Gemini returning a JSON intent
        mock_call.return_value = json.dumps({
            "is_scheduled": True,
            "delay_seconds": 60,
            "is_command": False,
            "extracted_task": "Check oven",
            "confirmation_response": "OK"
        })
        
        intent = telegram_bot.parse_intent("remind me in 1 min to check oven")
        self.assertTrue(intent["is_scheduled"])
        self.assertEqual(intent["delay_seconds"], 60)
        self.assertEqual(intent["extracted_task"], "Check oven")

    @patch("telegram_bot.send_message")
    def test_schedule_task(self, mock_send):
        with patch("threading.Timer") as mock_timer:
            telegram_bot.schedule_task(123, "456", 10, "ls", is_command=True)
            mock_timer.assert_called_once()
            args, kwargs = mock_timer.call_args
            self.assertEqual(args[0], 10)

if __name__ == "__main__":
    unittest.main()
