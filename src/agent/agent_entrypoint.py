import os
import json

def main():
    prompt = os.environ.get("AGENT_PROMPT", "No prompt provided")
    
    # Simulate some work
    print(f"Agent received: {prompt}")
    
    # Check if we can see the workspace
    if os.path.exists("GEMINI.md"):
        with open("GEMINI.md", "r") as f:
            content = f.read()
            print(f"Reading GEMINI.md, size: {len(content)}")
    
    # Return a JSON result
    result = {
        "status": "success",
        "response": f"Processed: {prompt}",
        "workspace_check": os.path.exists("GEMINI.md")
    }
    
    print(json.dumps(result))

if __name__ == "__main__":
    main()
