import unittest
from unittest.mock import MagicMock
from src.orchestrator import Orchestrator
from src.database import Database
from src.channels.base import BaseChannel
import os

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
        self.orchestrator = Orchestrator(self.db, [self.channel], allowed_user_id="123")

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_unauthorized_message(self):
        self.channel.on_message("chat1", "unknown_user", {"text": "/status"})
        self.assertEqual(len(self.channel.sent_messages), 1)
        self.assertEqual(self.channel.sent_messages[0][1], "Unauthorized.")

    def test_authorized_status_command(self):
        self.channel.on_message("chat1", "123", {"text": "/status"})
        self.assertEqual(len(self.channel.sent_messages), 1)
        self.assertEqual(self.channel.sent_messages[0][1], "System ready.")
        
        # Verify message was stored in DB
        messages = self.db.get_messages("chat1")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["content"], "/status")

    def test_general_message_response(self):
        self.channel.on_message("chat1", "123", {"text": "hello bot"})
        self.assertEqual(len(self.channel.sent_messages), 1)
        self.assertTrue("Received: hello bot" in self.channel.sent_messages[0][1])

if __name__ == "__main__":
    unittest.main()
