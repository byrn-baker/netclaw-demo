#!/usr/bin/env python3
"""Relay OpenClaw session activity to a Slack channel."""

import json
import os
import sys
import time
import urllib.request

SLACK_TOKEN = os.environ.get("SLACK_BOT_TOKEN", "")
SLACK_CHANNEL = os.environ.get("SLACK_CHANNEL_ID", "")
SESSION_DIR = os.path.expanduser("~/.openclaw/agents/main/sessions")
POLL_INTERVAL = 2

# Skip these messages
SKIP_PATTERNS = ["[OpenClaw heartbeat", "HEARTBEAT_OK", "Sender (untrusted metadata)"]


def post_to_slack(text):
    payload = json.dumps({"channel": SLACK_CHANNEL, "text": text}).encode()
    req = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=payload,
        headers={
            "Authorization": f"Bearer {SLACK_TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        data = json.loads(resp.read())
        if not data.get("ok"):
            print(f"Slack error: {data.get('error')}", file=sys.stderr)
    except Exception as e:
        print(f"Slack post failed: {e}", file=sys.stderr)


def get_latest_session():
    if not os.path.isdir(SESSION_DIR):
        return None
    files = [f for f in os.listdir(SESSION_DIR) if f.endswith(".jsonl") and "trajectory" not in f and "reset" not in f]
    if not files:
        return None
    return os.path.join(SESSION_DIR, max(files, key=lambda f: os.path.getmtime(os.path.join(SESSION_DIR, f))))


def parse_user_content(content):
    """Extract the actual user message, stripping the sender metadata prefix."""
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, dict):
                parts.append(p.get("text", ""))
            else:
                parts.append(str(p))
        content = " ".join(parts)

    # Strip the "Sender (untrusted metadata):\n```json\n{...}\n```\n\n" prefix
    if "```" in content:
        parts = content.split("```")
        # The actual message is after the second ```
        if len(parts) >= 3:
            content = parts[2].strip()
        elif len(parts) >= 2:
            content = parts[-1].strip()

    return content.strip()


def tail_session(path, offset=0):
    messages = []
    try:
        with open(path, "r") as f:
            f.seek(offset)
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    if entry.get("type") != "message":
                        continue
                    msg = entry.get("message", {})
                    role = msg.get("role", "")
                    content = msg.get("content", "")
                    if not role or not content:
                        continue

                    if role == "user":
                        text = parse_user_content(content)
                    elif isinstance(content, list):
                        text = " ".join(p.get("text", "") for p in content if isinstance(p, dict))
                    else:
                        text = str(content)

                    # Skip noise
                    if any(skip in text for skip in SKIP_PATTERNS):
                        continue
                    if not text.strip():
                        continue

                    messages.append((role, text[:3000]))
                except (json.JSONDecodeError, TypeError):
                    pass
            new_offset = f.tell()
    except (FileNotFoundError, PermissionError):
        return messages, offset
    return messages, new_offset


def main():
    post_to_slack(":lobster: *NetClaw Demo Session Relay Started*\nForwarding TUI session activity to this channel.")
    print(f"Watching {SESSION_DIR} — posting to #{SLACK_CHANNEL}", file=sys.stderr)

    current_file = None
    offset = 0

    while True:
        latest = get_latest_session()
        if latest != current_file:
            current_file = latest
            if current_file:
                offset = os.path.getsize(current_file)
                print(f"Tracking: {current_file}", file=sys.stderr)

        if current_file:
            messages, offset = tail_session(current_file, offset)
            for role, content in messages:
                if role == "user":
                    post_to_slack(f":bust_in_silhouette: *User:*\n{content}")
                elif role == "assistant":
                    post_to_slack(f":lobster: *NetClaw:*\n{content}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
