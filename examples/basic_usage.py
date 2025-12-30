#!/usr/bin/env python3
"""
Basic usage examples for Claude API Layer.

This script demonstrates how to interact with the API from external tools.
"""

import json
import time

import requests

# Configuration
API_BASE = "http://localhost:8000/api/v1"
API_KEY = "change-me-in-production"  # Use your configured API key
HEADERS = {"X-API-Key": API_KEY, "Content-Type": "application/json"}


def check_health():
    """Check if the API is running."""
    response = requests.get("http://localhost:8000/health")
    print(f"Health Status: {response.json()}")
    return response.status_code == 200


def simple_chat():
    """Send a simple chat message."""
    print("\n=== Simple Chat ===")

    response = requests.post(
        f"{API_BASE}/chat",
        headers=HEADERS,
        json={
            "prompt": "What is 2 + 2? Answer in one word.",
            "allowed_tools": [],  # No tools needed for simple questions
            "max_turns": 1,
        },
    )

    if response.status_code == 200:
        data = response.json()
        print(f"Result: {data['result']}")
        print(f"Duration: {data['duration_ms']}ms")
    else:
        print(f"Error: {response.status_code} - {response.text}")


def session_based_conversation():
    """Demonstrate session-based conversation."""
    print("\n=== Session-Based Conversation ===")

    # Create a new session
    print("Creating session...")
    response = requests.post(
        f"{API_BASE}/sessions",
        headers=HEADERS,
        json={
            "name": "example-session",
            "working_directory": ".",
            "allowed_tools": ["Read", "Glob", "Grep"],
        },
    )
    session = response.json()
    session_id = session["id"]
    print(f"Created session: {session_id}")

    # First message
    print("\nSending first message...")
    response = requests.post(
        f"{API_BASE}/chat",
        headers=HEADERS,
        json={
            "prompt": "Remember that my favorite color is blue.",
            "session_id": session_id,
            "allowed_tools": [],
        },
    )
    print(f"Response: {response.json()['result'][:100]}...")

    # Second message - testing memory
    print("\nSending follow-up message...")
    response = requests.post(
        f"{API_BASE}/chat",
        headers=HEADERS,
        json={
            "prompt": "What is my favorite color?",
            "session_id": session_id,
            "allowed_tools": [],
        },
    )
    print(f"Response: {response.json()['result']}")

    # List sessions
    print("\nListing sessions...")
    response = requests.get(f"{API_BASE}/sessions", headers=HEADERS)
    sessions = response.json()
    print(f"Total sessions: {sessions['total']}")

    # Clean up
    print("\nDeleting session...")
    requests.delete(f"{API_BASE}/sessions/{session_id}", headers=HEADERS)
    print("Session deleted.")


def streaming_example():
    """Demonstrate streaming responses."""
    print("\n=== Streaming Response ===")

    response = requests.post(
        f"{API_BASE}/chat/stream",
        headers=HEADERS,
        json={
            "prompt": "Count from 1 to 5, slowly.",
            "allowed_tools": [],
        },
        stream=True,
    )

    print("Streaming response:")
    for line in response.iter_lines():
        if line:
            data = json.loads(line.decode())
            if data["type"] == "text":
                print(data["content"], end="", flush=True)
            elif data["type"] == "done":
                print("\n[Stream complete]")


def code_analysis_example():
    """Demonstrate code analysis with file access."""
    print("\n=== Code Analysis ===")

    response = requests.post(
        f"{API_BASE}/chat",
        headers=HEADERS,
        json={
            "prompt": "List all Python files in the current directory and briefly describe what each one does.",
            "allowed_tools": ["Glob", "Read"],
            "max_turns": 5,
            "working_directory": ".",
        },
    )

    if response.status_code == 200:
        data = response.json()
        print(f"Analysis:\n{data['result']}")
        print(f"\nTools used: {data['tools_used']}")
    else:
        print(f"Error: {response.status_code} - {response.text}")


def self_evolving_example():
    """
    Demonstrate a basic self-evolving code pattern.

    This creates a simple function and asks Claude to improve it iteratively.
    """
    print("\n=== Self-Evolving Code Example ===")

    # Create initial code
    initial_code = '''
def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(0, n-i-1):
            if arr[j] > arr[j+1]:
                arr[j], arr[j+1] = arr[j+1], arr[j]
    return arr
'''

    # First iteration: Analyze
    print("Step 1: Analyzing code...")
    response = requests.post(
        f"{API_BASE}/chat",
        headers=HEADERS,
        json={
            "prompt": f"""Analyze this sorting function and suggest improvements:

```python
{initial_code}
```

Focus on:
1. Performance optimizations
2. Code readability
3. Edge case handling

Provide the improved code.""",
            "allowed_tools": [],
            "max_turns": 1,
        },
    )

    if response.status_code == 200:
        analysis = response.json()
        print(f"Analysis result:\n{analysis['result'][:500]}...")
    else:
        print(f"Error: {response.text}")


def main():
    """Run all examples."""
    print("Claude API Layer - Usage Examples")
    print("=" * 50)

    if not check_health():
        print("API is not running. Please start it first.")
        return

    try:
        simple_chat()
        session_based_conversation()
        streaming_example()
        code_analysis_example()
        self_evolving_example()
    except requests.exceptions.ConnectionError:
        print("Could not connect to API. Is it running?")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    main()
