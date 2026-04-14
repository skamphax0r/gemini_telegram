import sys
import json
from duckduckgo_search import DDGS

def search(query: str, max_results: int = 5) -> str:
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
            if not results:
                return "No results found."
            
            output = []
            for r in results:
                output.append(f"Title: {r['title']}\nURL: {r['href']}\nBody: {r['body']}\n")
            
            return "\n---\n".join(output)
    except Exception as e:
        return f"Error performing search: {str(e)}"

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python web_search.py <query>")
        sys.exit(1)
    
    query = " ".join(sys.argv[1:])
    print(search(query))
