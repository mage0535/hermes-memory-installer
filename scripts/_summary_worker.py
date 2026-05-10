#!/usr/bin/env python3
"""Summary worker for Memory 2.0

Generates a concise summary for a single finished session using Hermes'
configured LLM provider (via OpenAI-compatible API from config.yaml).

Usage:
  python3 _summary_worker.py <session_id>

Exits 0 on success, 1 on failure (stderr contains error details).
"""
import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
HERMES_HOME = Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser()
STATE_DB = HERMES_HOME / "state.db"
SUMMARY_TIMEOUT = 45  # seconds per session
MAX_CONTEXT_CHARS = 8000  # cap context sent to LLM

# ---------------------------------------------------------------------------
# Hermes provider detection (from config.yaml or .env)
# ---------------------------------------------------------------------------

def load_provider():
    """Detect LLM provider from config.yaml or env vars."""
    # Try config.yaml
    yaml_path = HERMES_HOME / "config.yaml"
    if yaml_path.exists():
        try:
            import yaml
            with open(yaml_path) as f:
                config = yaml.safe_load(f) or {}
            model = config.get("model", "")
            provider = config.get("provider", "")
            if model and provider:
                return model, provider
        except Exception:
            pass

    # Fallback: env vars
    base_url = os.environ.get("OPENAI_BASE_URL", "")
    api_key = os.environ.get("OPENAI_API_KEY", "")
    model = os.environ.get("MODEL", "")
    if base_url and model:
        return model, base_url

    # Last resorts — try Ollama
    ollama_model = "qwen2.5:3b"
    ollama_url = "http://localhost:11434/v1"
    ollama_key = "ollama"
    return ollama_model, ollama_url


def call_llm(model, provider, prompt, max_tokens=400):
    """Call LLM via OpenAI-compatible API. Returns string or raises."""
    try:
        import urllib.request
        # Find API key
        api_key = os.environ.get("OPENAI_API_KEY", "ollama")
        base_url = provider if provider else "http://localhost:11434/v1"

        payload = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.3,
        }).encode()

        req = urllib.request.Request(
            f"{base_url}/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
        )

        with urllib.request.urlopen(req, timeout=SUMMARY_TIMEOUT) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"].strip()

    except Exception as e:
        print(f"[summary_worker] LLM call failed: {e}", file=sys.stderr)
        raise


# ---------------------------------------------------------------------------
# Session extraction
# ---------------------------------------------------------------------------

def get_session_messages(db_path, session_id, max_msgs=80):
    """Extract messages for a session, newest first for context."""
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Get session meta
    cur = conn.execute(
        "SELECT title, source, model, started_at, ended_at, message_count "
        "FROM sessions WHERE id = ?",
        (session_id,),
    )
    session = cur.fetchone()
    if not session:
        conn.close()
        raise ValueError(f"Session {session_id} not found")

    # Get messages (newest first for better recency in truncation)
    cur = conn.execute(
        "SELECT role, content, timestamp FROM messages "
        "WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
        (session_id, max_msgs),
    )
    messages = [dict(row) for row in cur]
    conn.close()

    return dict(session), messages


def build_context(session, messages):
    """Build a compact context string for the LLM prompt."""
    lines = []
    title = session.get("title") or "Untitled"
    lines.append(f"Session: {title}")
    if session.get("source"):
        lines.append(f"Source: {session['source']}")
    if session.get("model"):
        lines.append(f"Model: {session['model']}")
    lines.append("")

    # Format messages (truncated to fit MAX_CONTEXT_CHARS)
    buf = []
    for msg in messages:
        role = msg.get("role", "?")
        content = (msg.get("content") or "")[:300]
        if role == "user":
            buf.append(f"**User:** {content}")
        elif role == "assistant":
            buf.append(f"**AI:** {content}")
        else:
            buf.append(f"**{role}:** {content}")
        buf.append("")

    context = "\n".join(buf)
    if len(context) > MAX_CONTEXT_CHARS:
        context = context[:MAX_CONTEXT_CHARS] + "\n... (truncated)"

    return title, "\n".join(lines) + "\n--- Conversation Excerpt ---\n" + context


PROMPT_TEMPLATE = """\
You are a session summarizer for an AI assistant. Your job is to produce a concise, factual summary of the following conversation.

Guidelines:
- 3-5 sentences maximum
- Focus on key decisions, actions taken, and outcomes
- Mention specific technical details, file names, or tools used
- If the conversation was trivial or had no real content, say "No significant discussion"
- Do NOT include pleasantries or filler
- Write in the same language as the conversation (auto-detect)

Return ONLY the summary text, nothing else.

{context}

Summary:"""


def generate_summary(session_id, db_path):
    """Main entry: generate summary for a session."""
    session, messages = get_session_messages(db_path, session_id)
    title, context = build_context(session, messages)

    model, provider = load_provider()
    prompt = PROMPT_TEMPLATE.format(context=context)

    summary = call_llm(model, provider, prompt, max_tokens=300)
    print(f"[summary_worker] Summarized '{title}': {summary[:100]}...")
    return summary


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def write_summary(db_path, session_id, summary):
    """Write summary back to state.db sessions table."""
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        "UPDATE sessions SET summary = ? WHERE id = ?",
        (summary, session_id),
    )
    conn.commit()
    conn.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate LLM summary for a session")
    parser.add_argument("session_id", help="Session ID to summarize")
    parser.add_argument("--dry-run", action="store_true", help="Print summary without saving")
    args = parser.parse_args()

    if not STATE_DB.exists():
        print(f"[summary_worker] state.db not found at {STATE_DB}", file=sys.stderr)
        sys.exit(1)

    try:
        summary = generate_summary(args.session_id, STATE_DB)
        print(summary)

        if not args.dry_run:
            write_summary(STATE_DB, args.session_id, summary)
            print("[summary_worker] Summary written to state.db", file=sys.stderr)

        sys.exit(0)

    except Exception as e:
        print(f"[summary_worker] ERROR: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
