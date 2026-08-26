#!/usr/bin/env python3
"""
RAG File Indexer — Background daemon that watches directories and indexes files.
Runs as a LaunchAgent, polls every 60 seconds for file changes.
"""
import os
import sys
import time
import signal

# Add parent dir to path so we can import the context store
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from importlib import import_module

# Lazy import to share the module
rag = None

def get_rag():
    global rag
    if rag is None:
        spec = import_module("rag_context_store")
        rag = spec
    return rag


# Directories to index (home dir, skipping large/irrelevant dirs)
INDEX_DIRS = [
    os.path.expanduser("~/.agents"),
    os.path.expanduser("~/.codex"),
    os.path.expanduser("~/.local/bin"),
    os.path.expanduser("~/models"),
]

# Also index any directories that appear in recent Codex/OpenCode sessions
EXTRA_SKIP = {
    'Library', 'Applications', '.Trash', '.cache', '.npm', '.yarn',
    '.cargo', '.rustup', '.pyenv', '.nvm', 'Pictures', 'Music',
    'Movies', 'Downloads',
}

POLL_INTERVAL = 60  # seconds


def index_all():
    """Run one indexing pass over all configured directories."""
    store = get_rag()
    total = 0
    for d in INDEX_DIRS:
        if os.path.isdir(d):
            try:
                n = store.index_directory(d, max_files=500)
                if n > 0:
                    print(f"[indexer] {d}: +{n} chunks", flush=True)
                total += n
            except Exception as e:
                print(f"[indexer] Error indexing {d}: {e}", flush=True)
    return total


def main():
    print(f"[indexer] Starting RAG file indexer (PID {os.getpid()})", flush=True)
    print(f"[indexer] Watching: {INDEX_DIRS}", flush=True)
    print(f"[indexer] Poll interval: {POLL_INTERVAL}s", flush=True)

    # Graceful shutdown
    running = True
    def handle_signal(signum, frame):
        nonlocal running
        print(f"[indexer] Received signal {signum}, shutting down...", flush=True)
        running = False
    signal.signal(signal.SIGTERM, handle_signal)
    signal.signal(signal.SIGINT, handle_signal)

    # Initial full index
    print("[indexer] Running initial index...", flush=True)
    total = index_all()
    stats = get_rag().get_stats()
    print(f"[indexer] Initial index complete: {total} new chunks", flush=True)
    print(f"[indexer] DB: {stats['indexed_files']} files, {stats['code_chunks']} code chunks, {stats['db_size_mb']} MB", flush=True)

    # Poll loop
    while running:
        try:
            time.sleep(POLL_INTERVAL)
            if not running:
                break
            n = index_all()
            if n > 0:
                stats = get_rag().get_stats()
                print(f"[indexer] Updated: +{n} chunks (total: {stats['code_chunks']})", flush=True)
        except Exception as e:
            print(f"[indexer] Poll error: {e}", flush=True)

    print("[indexer] Stopped.", flush=True)


if __name__ == "__main__":
    main()
