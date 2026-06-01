#!/usr/bin/env python3
import sys
import json
import urllib.request
import urllib.error
import argparse
from pathlib import Path
import uuid

def load_config():
    """Loads configuration, falling back to default localhost if missing."""
    config_path = Path.home() / ".config" / "tickertape" / "config.json"
    if config_path.exists():
        try:
            with open(config_path) as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Warning: Could not parse {config_path}")
            return {"server_url": "http://127.0.0.1:8000"}
    return {"server_url": "http://127.0.0.1:8000"}

def main():
    parser = argparse.ArgumentParser(description="Tickertape CLI Client")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Print Echo Command
    echo_parser = subparsers.add_parser("echo", help="Print a simple text note")
    echo_parser.add_argument("text", nargs="?", help="Text to print (or read from stdin)")
    echo_parser.add_argument("-t", "--title", help="Optional title")
    echo_parser.add_argument('--no-save', action='store_false', dest='save_to_history', default=True, help="Do not save to history")
    echo_parser.add_argument('--save', action='store_true', dest='save_to_history', help="Save to history (default)")

    # Print List Command
    list_parser = subparsers.add_parser("list", help="Print a structured list")
    list_parser.add_argument("items", nargs="*", help="List items")
    list_parser.add_argument("-t", "--title", required=True, help="List title")
    list_parser.add_argument("-s", "--style", choices=["bullet", "checkbox", "numbered"], default="checkbox", help="List style")
    list_parser.add_argument('--no-save', action='store_false', dest='save_to_history', default=True, help="Do not save to history")
    list_parser.add_argument('--save', action='store_true', dest='save_to_history', help="Save to history (default)")

    args = parser.parse_args()
    config = load_config()
    server_url = config.get("server_url", "http://127.0.0.1:8000")
    api_endpoint = f"{server_url}/api/print"

    payload = {
        "idempotency_key": str(uuid.uuid4()),
        "save_to_history": args.save_to_history
    }

    if args.command == "echo":
        text = args.text
        if not text:
            # Read from stdin if no text provided
            text = sys.stdin.read().strip()
        
        if not text:
            print("Error: No text provided to echo.", file=sys.stderr)
            sys.exit(1)
            
        payload.update({
            "type": "echo",
            "text": text
        })
        if args.title:
            payload["title"] = args.title

    elif args.command == "list":
        if not args.items:
            # Read from stdin if no items provided
            args.items = [line.strip() for line in sys.stdin if line.strip()]
            
        if not args.items:
            print("Error: No items provided for the list.", file=sys.stderr)
            sys.exit(1)
            
        payload.update({
            "type": "list",
            "title": args.title,
            "style": args.style,
            "items": args.items
        })

    # Send the request
    req = urllib.request.Request(
        api_endpoint, 
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST'
    )

    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 202:
                resp_data = json.loads(response.read().decode('utf-8'))
                print(f"Success! Job queued with ID: {resp_data.get('job_id')}")
            else:
                print(f"Failed. Status code: {response.status}")
    except urllib.error.URLError as e:
        print(f"Failed to connect to tickertape server at {api_endpoint}: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
