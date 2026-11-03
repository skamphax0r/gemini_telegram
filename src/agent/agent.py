import os
import json
import subprocess
import re
import time
from typing import Dict, Any, Optional

class AGYAgent:
    def __init__(self, session_id: Optional[str] = None, timeout: Optional[int] = None):
        self.session_id = session_id
        env_timeout = os.environ.get("AGY_AGENT_TIMEOUT")
        self.timeout = timeout or (int(env_timeout) if env_timeout and env_timeout.isdigit() else 590)

    def _get_brain_dirs(self):
        home_dir = os.path.expanduser("~")
        candidates = [
            os.path.join(home_dir, ".gemini", "antigravity-cli", "brain"),
            "/root/.gemini/antigravity-cli/brain",
        ]
        return [d for d in candidates if os.path.isdir(d)]

    def _sanitize_session_messages(self):
        """Remove 0-byte or corrupt message files and stale undelivered markers that block AGY background task / subagent wakeups."""
        for brain_dir in self._get_brain_dirs():
            session_dirs = (
                [os.path.join(brain_dir, self.session_id)]
                if self.session_id and os.path.isdir(os.path.join(brain_dir, self.session_id))
                else [os.path.join(brain_dir, d) for d in os.listdir(brain_dir)]
            )
            for sdir in session_dirs:
                msg_dir = os.path.join(sdir, ".system_generated", "messages")
                if not os.path.isdir(msg_dir):
                    continue
                undelivered_dir = os.path.join(msg_dir, "undelivered")
                # 1. Remove any 0-byte or invalid JSON message files
                for fname in os.listdir(msg_dir):
                    if not fname.endswith(".json") or fname == "read.json":
                        continue
                    fpath = os.path.join(msg_dir, fname)
                    if not os.path.isfile(fpath):
                        continue
                    msg_id = fname[:-5]
                    corrupt = False
                    try:
                        if os.path.getsize(fpath) == 0:
                            corrupt = True
                        else:
                            with open(fpath, "r", encoding="utf-8") as f:
                                json.load(f)
                    except Exception:
                        corrupt = True
                    if corrupt:
                        try:
                            os.remove(fpath)
                        except OSError:
                            pass
                        marker = os.path.join(undelivered_dir, msg_id)
                        if os.path.exists(marker):
                            try:
                                os.remove(marker)
                            except OSError:
                                pass
                # 2. Clear stale undelivered markers left over from previous terminated runs
                if self.session_id and os.path.isdir(undelivered_dir):
                    for marker_name in os.listdir(undelivered_dir):
                        marker_path = os.path.join(undelivered_dir, marker_name)
                        if os.path.isfile(marker_path):
                            try:
                                os.remove(marker_path)
                            except OSError:
                                pass

    def _recover_partial_response(self, start_time: float) -> Optional[str]:
        """If AGY CLI times out, check transcript.jsonl for the latest planner response generated during this run."""
        if not self.session_id:
            return None
        for brain_dir in self._get_brain_dirs():
            transcript_path = os.path.join(
                brain_dir, self.session_id, ".system_generated", "logs", "transcript.jsonl"
            )
            if not os.path.isfile(transcript_path):
                continue
            try:
                with open(transcript_path, "rb") as f:
                    f.seek(0, os.SEEK_END)
                    size = f.tell()
                    f.seek(max(0, size - 65536))
                    lines = f.read().decode("utf-8", errors="replace").splitlines()
                for line in reversed(lines):
                    if not line.strip().startswith("{"):
                        continue
                    entry = json.loads(line)
                    if (
                        entry.get("type") == "PLANNER_RESPONSE"
                        and entry.get("content")
                        and entry.get("content").strip()
                    ):
                        return entry["content"].strip()
            except Exception:
                continue
        return None

    def process_message(self, message: str) -> Dict[str, Any]:
        """Call the agy CLI to process a message."""
        self._sanitize_session_messages()
        run_start = time.time()

        # Define system instructions for tools and subagent delegation
        system_instructions = (
            "You are a helpful AI assistant. You have access to the following tools via shell commands:\n"
            "1. Web Search: `python /app/tools/web_search.py \"your query\"` - Use this to find information on the web.\n"
            "2. Web Fetch: `python /app/tools/web_fetch.py \"url\"` - Use this to get the full text content of a specific URL.\n"
            "3. Detached Background Subagent: `python /app/tools/delegate_subagent.py \"detailed task instructions\"` - "
            "Use this to offload long-running tasks (e.g., OS/package installations, large batch email/API jobs, multi-site scans, builds) "
            "to an isolated background subagent container (30-minute timeout) so you can reply to the user immediately without timing out. "
            "You can also use the native `invoke_subagent` tool for in-turn subagent delegation.\n"
            "Always prefer using these tools when you need up-to-date information or need to run long tasks without timing out.\n\n"
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
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=self.timeout)
            
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
            partial = self._recover_partial_response(run_start)
            if partial:
                return {
                    "status": "success",
                    "response": f"{partial}\n\n_(Note: Background work reached the turn time limit; send a follow-up or use `/subagent` if more steps remain.)_",
                    "session_id": self.session_id,
                }
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
