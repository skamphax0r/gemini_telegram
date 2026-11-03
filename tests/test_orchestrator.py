import unittest
from unittest.mock import MagicMock, patch
from src.orchestrator import Orchestrator
from src.database import Database
from src.channels.base import BaseChannel
from src.agent.agent import AGYAgent
from src.agent.tools.delegate_subagent import delegate_subagent
import json
import os
import shutil
import tempfile
import time

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
        self.orchestrator.executor.shutdown(wait=True)
        if os.path.exists(self.db_path):
            os.remove(self.db_path)

    def _wait_for_messages(self, count=1, timeout=2.0):
        start = time.time()
        while len(self.channel.sent_messages) < count and time.time() - start < timeout:
            time.sleep(0.01)

    def test_unauthorized_message(self):
        self.channel.on_message("chat1", "unknown_user", {"text": "/status"})
        time.sleep(0.05)
        self.assertEqual(len(self.channel.sent_messages), 0)

    def test_authorized_status_command(self):
        self.channel.on_message("chat1", "123", {"text": "/status"})
        self._wait_for_messages(1)
        self.assertEqual(len(self.channel.sent_messages), 1)
        self.assertIn("AGY Bot Status", self.channel.sent_messages[0][1])
        self.assertIn("Python", self.channel.sent_messages[0][1])
        self.assertIn("Uptime", self.channel.sent_messages[0][1])
        
        # Verify message was stored in DB
        messages = self.db.get_messages("chat1")
        self.assertEqual(len(messages), 1)
        self.assertEqual(messages[0]["content"], "/status")

    def test_general_message_response(self):
        # Mock successful runner response
        self.runner.run_agent.return_value = {"status": "success", "response": "Hello from AGY", "session_id": "new-uuid"}
        
        self.channel.on_message("chat1", "123", {"text": "hello bot"})
        self._wait_for_messages(1)
        self.assertEqual(len(self.channel.sent_messages), 1)
        self.assertEqual(self.channel.sent_messages[0][1], "Hello from AGY")
        
        # Verify session ID stored
        self.assertEqual(self.db.get_session("chat1"), "new-uuid")

    def test_memory_command(self):
        self.runner._get_workspace_path.return_value = "/tmp/test_workspace"
        os.makedirs("/tmp/test_workspace", exist_ok=True)
        
        # Test write
        self.channel.on_message("chat1", "123", {"text": "/memory This is my memory"})
        self._wait_for_messages(1)
        self.assertEqual(self.channel.sent_messages[0][1], "Memory updated successfully.")
        
        # Test read
        self.channel.on_message("chat1", "123", {"text": "/memory"})
        self._wait_for_messages(2)
        self.assertIn("This is my memory", self.channel.sent_messages[1][1])
        
        shutil.rmtree("/tmp/test_workspace")

    def test_subagent_command_and_queue_drain(self):
        self.runner._get_workspace_path.return_value = "/tmp/test_subagent_ws"
        os.makedirs("/tmp/test_subagent_ws", exist_ok=True)
        try:
            self.runner.run_agent.return_value = {"status": "success", "response": "Subagent finished work"}
            self.channel.on_message("chat1", "123", {"text": "/subagent install packages"})
            self._wait_for_messages(2)
            self.assertEqual(len(self.channel.sent_messages), 2)
            self.assertIn("Delegated to a background subagent", self.channel.sent_messages[0][1])
            self.assertEqual(self.channel.sent_messages[1][1], "Subagent finished work")
            # Verify isolated session (empty conversation ID) and 1800s timeout
            args, kwargs = self.runner.run_agent.call_args
            self.assertEqual(args[2]["AGY_CONVERSATION_ID"], "")
            self.assertEqual(kwargs.get("timeout"), 1800)
        finally:
            shutil.rmtree("/tmp/test_subagent_ws", ignore_errors=True)

    def test_autonomous_subagent_queue_drain(self):
        ws_dir = tempfile.mkdtemp(prefix="test_auto_subagent_")
        self.runner._get_workspace_path.return_value = ws_dir
        try:
            def side_effect(chat_id, prompt, env_vars, timeout=600):
                if prompt == "do heavy work":
                    delegate_subagent("background compilation task", workspace_dir=ws_dir)
                    return {"status": "success", "response": "Started background compilation!", "session_id": "main-sess"}
                else:
                    return {"status": "success", "response": f"Completed: {prompt}"}

            self.runner.run_agent.side_effect = side_effect
            self.channel.on_message("chat1", "123", {"text": "do heavy work"})
            self._wait_for_messages(2)
            self.assertEqual(len(self.channel.sent_messages), 2)
            self.assertEqual(self.channel.sent_messages[0][1], "Started background compilation!")
            self.assertEqual(self.channel.sent_messages[1][1], "Completed: background compilation task")
            self.assertFalse(os.path.exists(os.path.join(ws_dir, ".subagent_tasks.jsonl")))
        finally:
            shutil.rmtree(ws_dir, ignore_errors=True)

    def test_agent_sanitize_and_partial_recovery(self):
        brain_dir = tempfile.mkdtemp(prefix="test_brain_")
        session_id = "test-session-123"
        msg_dir = os.path.join(brain_dir, session_id, ".system_generated", "messages")
        undelivered_dir = os.path.join(msg_dir, "undelivered")
        logs_dir = os.path.join(brain_dir, session_id, ".system_generated", "logs")
        os.makedirs(undelivered_dir, exist_ok=True)
        os.makedirs(logs_dir, exist_ok=True)
        try:
            # Create a 0-byte corrupt message file and undelivered marker
            corrupt_json = os.path.join(msg_dir, "bad-msg.json")
            valid_json = os.path.join(msg_dir, "good-msg.json")
            marker = os.path.join(undelivered_dir, "bad-msg")
            open(corrupt_json, "w").close()
            open(marker, "w").close()
            with open(valid_json, "w") as f:
                json.dump({"id": "good-msg"}, f)

            # Create a transcript with a PLANNER_RESPONSE
            transcript_path = os.path.join(logs_dir, "transcript.jsonl")
            with open(transcript_path, "w") as f:
                f.write(json.dumps({"type": "PLANNER_RESPONSE", "content": "Interim progress message"}) + "\n")

            agent = AGYAgent(session_id=session_id)
            with patch.object(agent, "_get_brain_dirs", return_value=[brain_dir]):
                agent._sanitize_session_messages()
                self.assertFalse(os.path.exists(corrupt_json))
                self.assertFalse(os.path.exists(marker))
                self.assertTrue(os.path.exists(valid_json))

                recovered = agent._recover_partial_response(time.time())
                self.assertEqual(recovered, "Interim progress message")
        finally:
            shutil.rmtree(brain_dir, ignore_errors=True)

if __name__ == "__main__":
    unittest.main()
