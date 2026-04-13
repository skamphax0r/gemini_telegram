import subprocess
import os
import json
import shutil
from typing import Dict, List, Optional, Any
from datetime import datetime

class ContainerRunner:
    def __init__(self, 
                 image_name: str = "gemini-agent:latest", 
                 runtime: str = "docker",
                 base_workspace_dir: str = "/home/anelson/gitwork/gemini/workspaces"):
        self.image_name = image_name
        self.runtime = self._detect_runtime() if runtime == "auto" else runtime
        self.base_workspace_dir = base_workspace_dir
        os.makedirs(self.base_workspace_dir, exist_ok=True)

    def _detect_runtime(self) -> str:
        if shutil.which("docker"):
            return "docker"
        if shutil.which("podman"):
            return "podman"
        raise RuntimeError("Neither docker nor podman found in PATH")

    def _get_workspace_path(self, chat_jid: str) -> str:
        # Sanitize chat_jid for folder name
        safe_name = "".join(c if c.isalnum() else "_" for c in chat_jid)
        workspace_path = os.path.join(self.base_workspace_dir, safe_name)
        os.makedirs(workspace_path, exist_ok=True)
        return workspace_path

    def _ensure_gemini_md(self, workspace_path: str):
        gemini_md_path = os.path.join(workspace_path, "GEMINI.md")
        if not os.path.exists(gemini_md_path):
            with open(gemini_md_path, "w") as f:
                f.write("# Gemini Workspace Memory\n\nThis file is your persistent memory for this chat. You can read and write to it to store information across turns.")

    def run_agent(self, 
                  chat_jid: str, 
                  prompt: str, 
                  env_vars: Dict[str, str], 
                  timeout: int = 120) -> Dict[str, Any]:
        workspace_path = self._get_workspace_path(chat_jid)
        self._ensure_gemini_md(workspace_path)
        
        # We mount the src/agent directory to /app in the container
        # This allows us to update the agent code on the host and have it reflected in the container
        agent_src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "agent"))
        
        container_name = f"gemini-run-{int(datetime.now().timestamp())}"
        
        cmd = [
            "sudo", self.runtime, "run", "--rm",
            "--name", container_name,
            "-v", f"{workspace_path}:/workspace:Z",
            "-v", f"{agent_src_path}:/app:ro,Z",
            "-w", "/workspace"
        ]
        
        # Add environment variables
        for key, val in env_vars.items():
            cmd.extend(["-e", f"{key}={val}"])
            
        # Pass the prompt as an environment variable or via stdin
        cmd.extend(["-e", f"AGENT_PROMPT={prompt}"])
        
        cmd.append(self.image_name)
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            
            if result.returncode == 0:
                try:
                    # Expecting the agent to output JSON at the end
                    output_lines = result.stdout.strip().split('\n')
                    # Find the last line that looks like JSON
                    for line in reversed(output_lines):
                        if line.startswith('{') and line.endswith('}'):
                            return json.loads(line)
                    return {"status": "success", "response": result.stdout, "raw_output": result.stdout}
                except json.JSONDecodeError:
                    return {"status": "success", "response": result.stdout}
            else:
                return {
                    "status": "error", 
                    "error": result.stderr or "Container exited with non-zero code",
                    "exit_code": result.returncode,
                    "stdout": result.stdout
                }
                
        except subprocess.TimeoutExpired:
            # Cleanup: kill the container if it timed out
            subprocess.run([self.runtime, "stop", "-t", "2", container_name], capture_output=True)
            return {"status": "error", "error": f"Agent timed out after {timeout} seconds"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def build_image(self):
        agent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "agent"))
        cmd = ["sudo", self.runtime, "build", "-t", self.image_name, agent_dir]
        subprocess.run(cmd, check=True)
