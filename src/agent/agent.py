import os
import json
import google.generativeai as genai
from typing import List, Dict, Any, Optional
import subprocess

class GeminiAgent:
    def __init__(self, api_key: str, model_name: str = "gemini-1.5-pro", system_instruction: str = None):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_instruction
        )
        self.chat = None

    def start_chat(self, history: List[Dict] = None):
        self.chat = self.model.start_chat(history=history or [])

    def run_command(self, command: str) -> str:
        """Execute a shell command in the container and return output."""
        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
            return f"Stdout: {result.stdout}\nStderr: {result.stderr}\nExit Code: {result.returncode}"
        except subprocess.TimeoutExpired:
            return "Error: Command timed out after 30 seconds."
        except Exception as e:
            return f"Error executing command: {str(e)}"

    def process_message(self, message: str) -> Dict[str, Any]:
        if not self.chat:
            self.start_chat()
            
        # For now, we do a simple prompt-response. 
        # In a future commit, we will add full tool-calling support.
        try:
            response = self.chat.send_message(message)
            return {
                "status": "success",
                "response": response.text,
                "usage": response.usage_metadata.to_dict() if hasattr(response, 'usage_metadata') else {}
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }

def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    prompt = os.environ.get("AGENT_PROMPT")
    
    if not api_key:
        print(json.dumps({"status": "error", "error": "GEMINI_API_KEY not set"}))
        return

    system_instruction = "You are an AI assistant running in a secure Linux container. You have access to a workspace via the filesystem."
    if os.path.exists("GEMINI.md"):
        with open("GEMINI.md", "r") as f:
            memory = f.read()
            system_instruction += f"\n\nPersistent Memory (GEMINI.md):\n{memory}"

    agent = GeminiAgent(api_key=api_key, system_instruction=system_instruction)
    result = agent.process_message(prompt)
    print(json.dumps(result))

if __name__ == "__main__":
    main()
