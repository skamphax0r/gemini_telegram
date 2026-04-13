import unittest
from unittest.mock import MagicMock
import os
import time
from datetime import datetime, timedelta
from src.database import Database
from src.scheduler import TaskScheduler

class TestScheduler(unittest.TestCase):
    def setUp(self):
        self.db_path = "test_scheduler.db"
        self.db = Database(self.db_path)
        self.orchestrator = MagicMock()
        self.scheduler = TaskScheduler(self.db, self.orchestrator)

    def tearDown(self):
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def test_run_pending_tasks(self):
        chat_id = "chat123"
        prompt = "run scheduled task"
        # Schedule for the past
        run_at = (datetime.now() - timedelta(minutes=1)).isoformat()
        
        self.db.add_task(chat_id, prompt, "once", run_at)
        
        # Check pending tasks
        pending = self.db.get_pending_tasks()
        self.assertEqual(len(pending), 1)
        
        # Run one iteration of check
        self.scheduler._check_and_run_tasks()
        
        # Verify orchestrator was called
        self.orchestrator.execute_prompt.assert_called_once_with(chat_id, prompt)
        
        # Verify task is no longer pending
        pending_after = self.db.get_pending_tasks()
        self.assertEqual(len(pending_after), 0)
        
        # Verify task status is 'completed'
        with self.db._get_connection() as conn:
            row = conn.execute("SELECT status FROM tasks WHERE chat_jid = ?", (chat_id,)).fetchone()
            self.assertEqual(row["status"], "completed")

if __name__ == "__main__":
    unittest.main()
