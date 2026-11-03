import json
import os
import sys
from datetime import datetime


def delegate_subagent(prompt: str, workspace_dir: str = "/workspace") -> dict:
    queue_file = os.path.join(workspace_dir, ".subagent_tasks.jsonl")
    task = {
        "prompt": prompt,
        "created_at": datetime.now().isoformat(),
    }
    with open(queue_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(task) + "\n")
    return {
        "status": "queued",
        "message": (
            "Task has been queued for an isolated background subagent container "
            "(30-minute timeout, non-blocking). You may now immediately reply to "
            "the user to let them know the background subagent is working on it "
            "and will message them on Telegram as soon as it finishes."
        ),
        "task": task,
    }


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(json.dumps({"status": "error", "error": "Usage: python delegate_subagent.py \"<task prompt>\""}))
        sys.exit(1)
    task_prompt = " ".join(sys.argv[1:]).strip()
    workspace = os.environ.get("WORKSPACE_DIR", "/workspace")
    if not os.path.isdir(workspace):
        workspace = os.getcwd()
    res = delegate_subagent(task_prompt, workspace)
    print(json.dumps(res, indent=2))
