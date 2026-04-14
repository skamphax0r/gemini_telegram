import os
import json
import subprocess
import re
from typing import Dict, Any, Optional

class GeminiAgent:
    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id

    def _get_last_session_uuid(self) -> Optional[str]:
        """Call gemini --list-sessions and get the last UUID."""
        try:
            result = subprocess.run(["gemini", "--list-sessions"], capture_output=True, text=True)
            lines = result.stdout.strip().split('\n')
            if not lines:
                return None
            
            # The last session is usually at the bottom
            # Format: "  N. Prompt... (time) [UUID]"
            for line in reversed(lines):
                match = re.search(r'\[([a-f0-9-]{36})\]', line)
                if match:
                    return match.group(1)
        except Exception as e:
            print(f"Error getting last session UUID: {e}")
        return None

    def process_message(self, message: str) -> Dict[str, Any]:
        """Call the gemini CLI to process a message."""
        # Define system instructions for tools
        system_instructions = (
            "You are a helpful AI assistant. You have access to the following tools via shell commands:\n"
            "1. Web Search: `python /app/tools/web_search.py \"your query\"` - Use this to find information on the web.\n"
            "2. Web Fetch: `python /app/tools/web_fetch.py \"url\"` - Use this to get the full text content of a specific URL.\n"
            "Always prefer using these tools when you need up-to-date information.\n\n"
        )
        
        full_prompt = system_instructions + "User Message: " + message
        
        # Note: In the container, we have the host's OAuth credentials mounted
        # and the gemini CLI installed.
        cmd = [
            "gemini", 
            "-p", full_prompt, 
            "--approval-mode", "yolo", 
            "--output-format", "json"
        ]
        
        if self.session_id:
            cmd.extend(["--resume", self.session_id])
            
        try:
            # We run the command and capture the JSON output
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=290)
            
            if result.returncode == 0:
                output = result.stdout
                # The CLI might have some preamble, we look for the JSON part
                start_idx = output.find('{')
                
                # After execution, get the new/updated session ID
                new_session_id = self._get_last_session_uuid()

                if start_idx != -1:
                    json_str = output[start_idx:]
                    data = json.loads(json_str)
                    
                    return {
                        "status": "success",
                        "response": data.get("response", "No response in JSON."),
                        "session_id": new_session_id,
                        "metadata": data
                    }
                else:
                    return {
                        "status": "success",
                        "response": output,
                        "session_id": new_session_id
                    }
            else:
                return {
                    "status": "error",
                    "error": result.stderr or "CLI error",
                    "stdout": result.stdout
                }
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "Gemini CLI timed out"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

def main():
    prompt = os.environ.get("AGENT_PROMPT")
    session_id = os.environ.get("GEMINI_SESSION_ID")
    
    if not prompt:
        print(json.dumps({"status": "error", "error": "AGENT_PROMPT not set"}))
        return

    agent = GeminiAgent(session_id=session_id if session_id else None)
    result = agent.process_message(prompt)
    print(json.dumps(result))

if __name__ == "__main__":
    main()
