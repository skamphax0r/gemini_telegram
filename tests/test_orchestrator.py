import unittest
from unittest.mock import MagicMock
from src.orchestrator import Orchestrator
from src.database import Database
from src.channels.base import BaseChannel
import os
import shutil

class MockChannel(BaseChannel):
    def __init__(self):
        self.sent_messages = []
        self.on_message = None

    def connect(self): pass
    def disconnect(self): pass
    def send_message(self, chat_id, text):
        self.sent_messages.append((chat_id, text))
    def set_typing(self, chat_id, is_typing): pass

class TestOrchestrator(unittest.TestCase):
    def setUp(self):
        self.db_path = "test_orch.db"
        self.db = Database(self.db_path)
        self.channel = MockChannel()
        self.runner = MagicMock()
        self.orchestrator = Orchestrator(self.db, [self.channel], self.runner, allowed_user_id="123")

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_unauthorized_message(self):
        self.channel.on_message("chat1", "unknown_user", {"text": "/status"})
        self.assertEqual(len(self.channel.sent_messages), 0)

    def test_authorized_status_command(self):
        self.channel.on_message("chat1", "123", {"text": "/status"})
        self.assertEqual(len(self.channel.sent_messages), 1)
        self.assertIn("Gemini Bot Status", self.channel.sent_messages[0][1])
        self.assertIn("Python", self.channel.sent_messages[0][1])
        self.assertIn("Uptime", self.channel.sent_messages[0][1])
        
        # Verify message was stored in DB
        messages = self.db.get_messages("chat1")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["content"], "/status")

    def test_general_message_response(self):
        # Mock successful runner response
        self.runner.run_agent.return_value = {"status": "success", "response": "Hello from Gemini", "session_id": "new-uuid"}
        
        self.channel.on_message("chat1", "123", {"text": "hello bot"})
        self.assertEqual(len(self.channel.sent_messages), 1)
        self.assertEqual(self.channel.sent_messages[0][1], "Hello from Gemini")
        
        # Verify session ID stored
        self.assertEqual(self.db.get_session("chat1"), "new-uuid")

    def test_memory_command(self):
        self.runner._get_workspace_path.return_value = "/tmp/test_workspace"
        os.makedirs("/tmp/test_workspace", exist_ok=True)
        
        # Test write
        self.channel.on_message("chat1", "123", {"text": "/memory This is my memory"})
        self.assertEqual(self.channel.sent_messages[0][1], "Memory updated successfully.")
        
        # Test read
        self.channel.on_message("chat1", "123", {"text": "/memory"})
        self.assertIn("This is my memory", self.channel.sent_messages[1][1])
        
        shutil.rmtree("/tmp/test_workspace")

if __name__ == "__main__":
    unittest.main()
