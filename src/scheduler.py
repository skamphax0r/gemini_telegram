import time
import threading
from datetime import datetime
from typing import Optional
from .database import Database

class TaskScheduler:
    def __init__(self, db: Database, orchestrator):
        self.db = db
        self.orchestrator = orchestrator
        self.running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start the scheduler in a background thread."""
        if self.running:
            return
        self.running = True
        self._thread = threading.Thread(target=self._run_loop)
        self._thread.daemon = True
        self._thread.start()

    def stop(self):
        """Stop the scheduler."""
        self.running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _run_loop(self):
        while self.running:
            try:
                self._check_and_run_tasks()
            except Exception as e:
                print(f"Error in scheduler loop: {e}")
            time.sleep(10) # Check every 10 seconds

    def _check_and_run_tasks(self):
        pending_tasks = self.db.get_pending_tasks()
        
        for task in pending_tasks:
            task_id = task["id"]
            chat_id = task["chat_jid"]
            prompt = task["prompt"]
            
            print(f"Executing scheduled task {task_id} for {chat_id}: {prompt}")
            
            # Update status to 'running'
            with self.db._get_connection() as conn:
                conn.execute("UPDATE tasks SET status = 'running', last_run = ? WHERE id = ?", (datetime.now().isoformat(), task_id))
            
            try:
                # Run the prompt via orchestrator
                # Note: This runs in the scheduler thread, which might block other tasks
                # but for simplicity in this commit, we'll do it sequentially.
                self.orchestrator.execute_prompt(chat_id, prompt)
                
                # Update status to 'completed'
                with self.db._get_connection() as conn:
                    conn.execute("UPDATE tasks SET status = 'completed' WHERE id = ?", (task_id,))
            except Exception as e:
                print(f"Failed to execute task {task_id}: {e}")
                with self.db._get_connection() as conn:
                    conn.execute("UPDATE tasks SET status = 'failed' WHERE id = ?", (task_id,))
