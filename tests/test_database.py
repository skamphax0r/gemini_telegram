import os
import unittest
from datetime import datetime, timedelta
from src.database import Database

class TestDatabase(unittest.TestCase):
    def setUp(self):
        self.db_path = "test_gemini_bot.db"
        self.db = Database(self.db_path)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_store_and_get_messages(self):
        chat_jid = "test_chat"
        self.db.store_message(chat_jid, "user1", "Hello", datetime.now().isoformat(), False, False)
        self.db.store_message(chat_jid, "bot", "Hi there", datetime.now().isoformat(), True, True)
        
        messages = self.db.get_messages(chat_jid)
        self.assertEqual(len(messages), 2)
        self.assertEqual(messages[0]["content"], "Hello")
        self.assertEqual(messages[1]["content"], "Hi there")

    def test_session_management(self):
        chat_jid = "test_session_chat"
        session_id = "uuid-1234"
        self.db.set_session(chat_jid, session_id)
        
        retrieved_session = self.db.get_session(chat_jid)
        self.assertEqual(retrieved_session, session_id)
        
        # Test update
        new_session_id = "uuid-5678"
        self.db.set_session(chat_jid, new_session_id)
        self.assertEqual(self.db.get_session(chat_jid), new_session_id)

    def test_task_scheduling(self):
        chat_jid = "task_chat"
        now = datetime.now()
        past = (now - timedelta(minutes=5)).isoformat()
        future = (now + timedelta(minutes=5)).isoformat()
        
        self.db.add_task(chat_jid, "run ls", "once", past)
        self.db.add_task(chat_jid, "run uptime", "once", future)
        
        pending = self.db.get_pending_tasks()
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["prompt"], "run ls")

    def test_chat_registration(self):
        chat_jid = "group_123"
        self.db.register_chat(chat_jid, "My Group", True, "/tmp/group_123", "telegram")
        
        registered = self.db.get_registered_chats()
        self.assertEqual(len(registered), 1)
        self.assertEqual(registered[0]["name"], "My Group")
        self.assertEqual(registered[0]["chat_jid"], chat_jid)

if __name__ == "__main__":
    unittest.main()
