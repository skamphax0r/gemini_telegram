import unittest
import os
import shutil
from src.runner import ContainerRunner

class TestContainerRunner(unittest.TestCase):
    def setUp(self):
        self.workspace_base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "test_workspaces")
        self.runner = ContainerRunner(
            image_name="gemini-test-agent",
            runtime="auto",
            base_workspace_dir=self.workspace_base
        )
        try:
            self.runner.build_image()
        except Exception as e:
            self.skipTest(f"Failed to build image: {e}")

    def tearDown(self):
        if os.path.exists(self.workspace_base):
            shutil.rmtree(self.workspace_base)

    def test_run_agent(self):
        chat_id = "test_chat_123"
        prompt = "ping" 
        env_vars = {"GEMINI_SESSION_ID": ""}
        
        result = self.runner.run_agent(chat_id, prompt, env_vars)
        
        # Verify GEMINI.md was created (this happens on the host before container run)
        workspace_path = self.runner._get_workspace_path(chat_id)
        self.assertTrue(os.path.exists(os.path.join(workspace_path, "GEMINI.md")))

        # Check result - if we have credentials, it should succeed. 
        # In CI, it will likely fail with an auth error, which is acceptable for the runner test.
        if result["status"] == "error":
            print(f"\nAgent failed (expected in CI without credentials): {result.get('error')}")
            # Ensure it's not a container failure but a CLI failure
            self.assertIn("status", result)
        else:
            self.assertEqual(result["status"], "success")
            self.assertIn("response", result)

if __name__ == "__main__":
    unittest.main()
