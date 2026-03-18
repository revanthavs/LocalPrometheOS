import sys
import json
import subprocess
import time

def main():
    cmd = ["python", "tools/mcp_server.py"]
    process = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )

    # Initialize
    req = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "initialize",
        "params": {}
    }
    process.stdin.write(json.dumps(req) + "\n")
    process.stdin.flush()
    
    print("Sent initialize")

    # Read response
    while True:
        line = process.stdout.readline()
        if not line:
            break
        print(f"Received: {line.strip()}")
        try:
            resp = json.loads(line)
            if resp.get("id") == "1":
                break
        except:
            pass

    # Call web_search
    req = {
        "jsonrpc": "2.0",
        "id": "2",
        "method": "tools/call",
        "params": {
            "name": "web_search",
            "arguments": {"query": "amazon deals"}
        }
    }
    process.stdin.write(json.dumps(req) + "\n")
    process.stdin.flush()
    print("Sent web_search call")

    # Read response
    while True:
        line = process.stdout.readline()
        if not line:
            break
        print(f"Received: {line.strip()}")
        try:
            resp = json.loads(line)
            if resp.get("id") == "2":
                print("Result:", json.dumps(resp, indent=2))
                break
        except:
            pass

    process.terminate()

if __name__ == "__main__":
    main()
