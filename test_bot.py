import unittest
from unittest.mock import patch, MagicMock
import json
import os
import time
from queue import Queue

# Mock environment before import
os.environ["TELEGRAM_BOT_TOKEN"] = "test_token"
os.environ["ALLOWED_USER_ID"] = "12345"

import telegram_bot

class TestGeminiBotAsync(unittest.TestCase):

    def setUp(self):
        telegram_bot.user_sessions = {}
        # Clear queues
        while not telegram_bot.update_queue.empty():
            telegram_bot.update_queue.get()
        while not telegram_bot.task_queue.empty():
            telegram_bot.task_queue.get()

    @patch("telegram_bot.requests.post")
    def test_send_message(self, mock_post):
        telegram_bot.send_message(123, "hello")
        mock_post.assert_called_once()

    @patch("telegram_bot.call_gemini")
    def test_update_processor_scheduling(self, mock_call):
        # Mock Gemini to return a scheduled intent
        mock_call.return_value = json.dumps({
            "is_scheduled": True,
            "delay_seconds": 0.1,
            "is_command": False,
            "extracted_task": "Delayed Task",
            "confirmation_response": "Scheduling..."
        })
        
        test_update = {
            "message": {
                "chat": {"id": 123},
                "from": {"id": 12345},
                "text": "remind me in 0.1s"
            }
        }
        
        # We manually call a part of the processor logic or run it in a controlled way
        # Since update_processor is an infinite loop, we test the logic inside it
        with patch("telegram_bot.schedule_task") as mock_schedule:
            telegram_bot.update_queue.put(test_update)
            
            # Start a temporary processor thread that we can stop
            t = threading.Thread(target=telegram_bot.update_processor)
            t.daemon = True
            t.start()
            
            # Give it a moment to process
            time.sleep(0.5)
            
            mock_schedule.assert_called_once()
            args = mock_schedule.call_args[0]
            self.assertEqual(args[2], 0.1)
            self.assertEqual(args[3], "Delayed Task")

    @patch("telegram_bot.call_gemini")
    def test_worker_thread_execution(self, mock_call):
        mock_call.return_value = "Gemini Response"
        task = telegram_bot.Task(chat_id=123, user_id="12345", prompt="Hello")
        telegram_bot.task_queue.put(task)
        
        with patch("telegram_bot.send_message") as mock_send:
            # Run one iteration of worker_thread logic
            # We can't easily stop the worker_thread loop, so we'll mock ensure_workers 
            # and run a single worker thread that will exit when queue is empty
            telegram_bot.worker_thread(1)
            
            mock_send.assert_called_with(123, "Gemini Response")

if __name__ == "__main__":
    import threading
    unittest.main()
