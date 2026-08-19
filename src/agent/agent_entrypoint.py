import os
import json

def main():
    prompt = os.environ.get("AGENT_PROMPT", "No prompt provided")
    
    # Simulate some work
    print(f"Agent received: {prompt}")
    
    # Check if we can see the workspace memory file
    memory_file = "AGY.md" if os.path.exists("AGY.md") else ("GEMINI.md" if os.path.exists("GEMINI.md") else None)
    if memory_file:
        with open(memory_file, "r") as f:
            content = f.read()
            print(f"Reading {memory_file}, size: {len(content)}")
    
    # Return a JSON result
    result = {
        "status": "success",
        "response": f"Processed: {prompt}",
        "workspace_check": memory_file is not None
    }
    
    print(json.dumps(result))

if __name__ == "__main__":
    main()
