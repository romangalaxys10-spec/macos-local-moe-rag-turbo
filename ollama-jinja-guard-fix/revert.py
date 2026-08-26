#!/usr/bin/env python3
"""Restore the ORIGINAL (stock) chat templates into the Ollama GGUF blobs,
undoing the guard removal. Uses the untouched orig-*-chat_template.jinja backups."""
import os

TARGETS = [
    ("ornith", "sha256-10edce4298d48345ff6efd192d580de0b6f2db429baf8fb491bb84de51a5c2be", 10934978, 7764),
    ("qwen",   "sha256-7cb7cedcb3ea17abcbde467acd4eb5b7a0f2971ad45cb44a3da9dea5691dede6", 10935048, 8952),
]
BLOBS = os.path.expanduser("~/.ollama/models/blobs/")
WS = os.path.dirname(os.path.abspath(__file__))

for name, digest, off, length in TARGETS:
    src = os.path.join(WS, f"orig-{name}-chat_template.jinja")
    data = open(src, "rb").read()
    assert len(data) == length, f"{name}: backup size {len(data)} != KV length {length}"
    with open(BLOBS + digest, "r+b") as f:
        f.seek(off)
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    print(f"{name}: stock template restored ({len(data)} bytes)")
