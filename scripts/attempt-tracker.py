#!/usr/bin/env python3
"""
Attempt Tracker — persistent loop detection for OpenClaw agents.

Usage:
  # Log a failure
  python3 scripts/attempt-tracker.py log --task "push frr config to P1" --error "vtysh: command not found"

  # Check if should escalate (returns exit code 1 if threshold reached)
  python3 scripts/attempt-tracker.py check --task "push frr config to P1"

  # Mark a task as resolved (resets counter)
  python3 scripts/attempt-tracker.py resolve --task "push frr config to P1"

  # Show recent failures (for context when switching models)
  python3 scripts/attempt-tracker.py history --task "push frr config to P1"

  # Show all active (unresolved) tasks
  python3 scripts/attempt-tracker.py active

DB stored at ~/.openclaw/attempt-tracker.db
"""

import argparse
import hashlib
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone

DB_PATH = os.path.expanduser("~/.openclaw/attempt-tracker.db")
ESCALATION_THRESHOLD = 3
AGENT_ID = "openclaw"


def get_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_key TEXT NOT NULL,
            task_description TEXT NOT NULL,
            error_message TEXT,
            agent TEXT NOT NULL DEFAULT 'openclaw',
            model TEXT,
            timestamp TEXT NOT NULL,
            resolved INTEGER NOT NULL DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_task_key_resolved
        ON attempts(task_key, resolved)
    """)
    conn.commit()
    return conn


def task_key(task: str) -> str:
    """Normalize task description to a stable key for grouping."""
    normalized = task.strip().lower()
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def cmd_log(args):
    conn = get_db()
    key = task_key(args.task)
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO attempts (task_key, task_description, error_message, agent, model, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
        (key, args.task, args.error, AGENT_ID, args.model or "", now),
    )
    conn.commit()

    # Return current count
    count = conn.execute(
        "SELECT COUNT(*) FROM attempts WHERE task_key = ? AND resolved = 0", (key,)
    ).fetchone()[0]

    result = {
        "logged": True,
        "task": args.task,
        "attempt_count": count,
        "threshold": ESCALATION_THRESHOLD,
        "should_escalate": count >= ESCALATION_THRESHOLD,
    }

    if count >= ESCALATION_THRESHOLD:
        result["action"] = "SWITCH MODEL: run /model deepseek-v4-flash:cloud"
        result["reason"] = f"Failed {count} times on this task. Escalating to stronger model."

    print(json.dumps(result, indent=2))
    conn.close()


def cmd_check(args):
    conn = get_db()
    key = task_key(args.task)
    count = conn.execute(
        "SELECT COUNT(*) FROM attempts WHERE task_key = ? AND resolved = 0", (key,)
    ).fetchone()[0]

    should_escalate = count >= ESCALATION_THRESHOLD
    result = {
        "task": args.task,
        "attempt_count": count,
        "threshold": ESCALATION_THRESHOLD,
        "should_escalate": should_escalate,
    }

    if should_escalate:
        result["action"] = "SWITCH MODEL: run /model deepseek-v4-flash:cloud"

    print(json.dumps(result, indent=2))
    conn.close()
    sys.exit(1 if should_escalate else 0)


def cmd_resolve(args):
    conn = get_db()
    key = task_key(args.task)
    conn.execute(
        "UPDATE attempts SET resolved = 1 WHERE task_key = ? AND resolved = 0", (key,)
    )
    conn.commit()
    print(json.dumps({"resolved": True, "task": args.task}))
    conn.close()


def cmd_history(args):
    conn = get_db()
    key = task_key(args.task)
    rows = conn.execute(
        "SELECT task_description, error_message, model, timestamp FROM attempts WHERE task_key = ? AND resolved = 0 ORDER BY timestamp DESC LIMIT 10",
        (key,),
    ).fetchall()

    history = []
    for row in rows:
        history.append({
            "task": row[0],
            "error": row[1],
            "model": row[2],
            "timestamp": row[3],
        })

    print(json.dumps({"task": args.task, "attempts": len(history), "history": history}, indent=2))
    conn.close()


def cmd_active(args):
    conn = get_db()
    rows = conn.execute("""
        SELECT task_key, task_description, COUNT(*) as attempts, MAX(timestamp) as last_attempt
        FROM attempts
        WHERE resolved = 0
        GROUP BY task_key
        ORDER BY attempts DESC
    """).fetchall()

    tasks = []
    for row in rows:
        tasks.append({
            "task": row[1],
            "attempts": row[2],
            "last_attempt": row[3],
            "should_escalate": row[2] >= ESCALATION_THRESHOLD,
        })

    print(json.dumps({"active_tasks": tasks, "total": len(tasks)}, indent=2))
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Track agent task attempts for loop detection")
    sub = parser.add_subparsers(dest="command")

    log_p = sub.add_parser("log", help="Log a failed attempt")
    log_p.add_argument("--task", required=True, help="Description of the task being attempted")
    log_p.add_argument("--error", default="", help="Error message from the failure")
    log_p.add_argument("--model", default="", help="Model that was active during failure")

    check_p = sub.add_parser("check", help="Check if escalation threshold reached")
    check_p.add_argument("--task", required=True, help="Task to check")

    resolve_p = sub.add_parser("resolve", help="Mark a task as resolved")
    resolve_p.add_argument("--task", required=True, help="Task to resolve")

    history_p = sub.add_parser("history", help="Show failure history for a task")
    history_p.add_argument("--task", required=True, help="Task to show history for")

    sub.add_parser("active", help="Show all active unresolved tasks")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    {"log": cmd_log, "check": cmd_check, "resolve": cmd_resolve, "history": cmd_history, "active": cmd_active}[args.command](args)
