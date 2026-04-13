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
        # Note: This requires the image to be built. 
        # In a real CI, we'd pre-build. Here we'll try to build in setUp if not present.
        try:
            self.runner.build_image()
        except Exception as e:
            self.skipTest(f"Failed to build image: {e}")

    def tearDown(self):
        if os.path.exists(self.workspace_base):
            shutil.rmtree(self.workspace_base)

    def test_run_agent(self):
        chat_id = "test_chat_123"
        prompt = "Hello from tests"
        env_vars = {"TEST_VAR": "value"}
        
        result = self.runner.run_agent(chat_id, prompt, env_vars)
        
        if result["status"] == "error":
            print(f"\nError running agent: {result}")
        
        self.assertEqual(result["status"], "success")
        self.assertTrue(result["workspace_check"])
        self.assertIn(prompt, result["response"])
        
        # Verify GEMINI.md was created
        workspace_path = self.runner._get_workspace_path(chat_id)
        self.assertTrue(os.path.exists(os.path.join(workspace_path, "GEMINI.md")))

if __name__ == "__main__":
    unittest.main()
