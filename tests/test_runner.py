import unittest
import os
import shutil
from src.runner import ContainerRunner

class TestContainerRunner(unittest.TestCase):
    def setUp(self):
        self.workspace_base = "/home/anelson/gitwork/gemini/test_workspaces"
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
        # Use a prompt that doesn't strictly require Gemini Pro response 
        # but just confirms CLI execution if possible. 
        # Given we have OAuth mounted, this SHOULD work.
        prompt = "ping" 
        env_vars = {"GEMINI_SESSION_ID": ""}
        
        result = self.runner.run_agent(chat_id, prompt, env_vars)
        
        if result["status"] == "error":
            print(f"\nError running agent: {result}")
        
        self.assertEqual(result["status"], "success")
        self.assertIn("response", result)
        
        # Verify GEMINI.md was created
        workspace_path = self.runner._get_workspace_path(chat_id)
        self.assertTrue(os.path.exists(os.path.join(workspace_path, "GEMINI.md")))

if __name__ == "__main__":
    unittest.main()
