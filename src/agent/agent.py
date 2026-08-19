import os
import json
import subprocess
import re
from typing import Dict, Any, Optional

class AGYAgent:
    def __init__(self, session_id: Optional[str] = None):
        self.session_id = session_id

    def process_message(self, message: str) -> Dict[str, Any]:
        """Call the agy CLI to process a message."""
        # Define system instructions for tools
        system_instructions = (
            "You are a helpful AI assistant. You have access to the following tools via shell commands:\n"
            "1. Web Search: `python /app/tools/web_search.py \"your query\"` - Use this to find information on the web.\n"
            "2. Web Fetch: `python /app/tools/web_fetch.py \"url\"` - Use this to get the full text content of a specific URL.\n"
            "Always prefer using these tools when you need up-to-date information.\n\n"
        )
        
        full_prompt = system_instructions + "User Message: " + message
        
        # In the container, we have host credentials mounted and agy installed
        cmd = [
            "agy", 
            "-p", full_prompt, 
            "--dangerously-skip-permissions", 
            "--output-format", "json"
        ]
        
        if self.session_id:
            cmd.extend(["--conversation", self.session_id])
            
        try:
            # We run the command and capture the JSON output
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=590)
            
            if result.returncode == 0:
                output = result.stdout
                start_idx = output.find('{')
                end_idx = output.rfind('}')
                
                if start_idx != -1 and end_idx != -1 and end_idx >= start_idx:
                    json_str = output[start_idx:end_idx + 1]
                    try:
                        data = json.loads(json_str)
                    except json.JSONDecodeError:
                        return {
                            "status": "success",
                            "response": output.strip(),
                            "session_id": self.session_id
                        }
                    
                    conversation_id = data.get("conversation_id") or self.session_id
                    status_str = data.get("status", "SUCCESS")
                    
                    if status_str in ("SUCCESS", "success"):
                        return {
                            "status": "success",
                            "response": data.get("response", "No response in JSON."),
                            "session_id": conversation_id,
                            "metadata": data
                        }
                    else:
                        return {
                            "status": "error",
                            "error": data.get("error") or f"AGY returned status: {status_str}",
                            "response": data.get("response"),
                            "session_id": conversation_id,
                            "metadata": data
                        }
                else:
                    return {
                        "status": "success",
                        "response": output.strip(),
                        "session_id": self.session_id
                    }
            else:
                return {
                    "status": "error",
                    "error": result.stderr or "AGY CLI error",
                    "stdout": result.stdout
                }
        except subprocess.TimeoutExpired:
            return {"status": "error", "error": "AGY CLI timed out"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

# Backward compatibility alias
GeminiAgent = AGYAgent

def main():
    prompt = os.environ.get("AGENT_PROMPT")
    session_id = (
        os.environ.get("AGY_CONVERSATION_ID") or 
        os.environ.get("AGY_SESSION_ID") or 
        os.environ.get("GEMINI_SESSION_ID")
    )
    
    if not prompt:
        print(json.dumps({"status": "error", "error": "AGENT_PROMPT not set"}))
        return

    agent = AGYAgent(session_id=session_id if session_id else None)
    result = agent.process_message(prompt)
    print(json.dumps(result))

if __name__ == "__main__":
    main()
