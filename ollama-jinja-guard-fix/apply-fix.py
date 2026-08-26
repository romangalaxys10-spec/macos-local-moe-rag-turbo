#!/usr/bin/env python3
"""Re-strip the strict 'No user query found' Jinja guard from local Ollama GGUF blobs.
Idempotent. Re-run after any fresh pull / re-import that recreates these blobs
(new blob digest => check the locator snippet in ollama-jinja-guard-fix/README.md for new offsets).
Original templates are preserved in this folder before each patch."""
import os

FIX_DIR = os.path.dirname(os.path.abspath(__file__))
BLOB_ORNITH = "/Users/d/.ollama/models/blobs/sha256-10edce4298d48345ff6efd192d580de0b6f2db429baf8fb491bb84de51a5c2be"
BLOB_QWEN = "/Users/d/.ollama/models/blobs/sha256-7cb7cedcb3ea17abcbde467acd4eb5b7a0f2971ad45cb44a3da9dea5691dede6"

GUARD = "\n{%- if ns.multi_step_tool %}\n    {{- raise_exception('No user query found in messages.') }}\n{%- endif %}\n"

for name, path, off, length in [
    ("ornith", BLOB_ORNITH, 10934978, 7764),
    ("qwen", BLOB_QWEN, 10935048, 8952),
]:
    if not os.path.isfile(path):
        print(f"{name}: blob missing - model re-imported under a new digest; use README locator for fresh offsets")
        continue
    with open(path, "r+b") as fh:
        fh.seek(off)
        cur = fh.read(length)
    s = cur.decode("utf-8")
    if GUARD not in s:
        print(f"{name}: already patched, skipping")
        continue
    if "render_content" not in s or len(s) != length:
        raise RuntimeError(f"{name}: slot at offset {off} does not hold the expected chat_template")
    nb = s.replace(GUARD, "\n").encode("utf-8")
    padlen = length - len(nb)
    if padlen < 0:
        raise RuntimeError(f"{name}: patched text exceeds original KV slot size")
    with open(FIX_DIR + "/" + name + "-orig-backup.jinja", "w") as bak:
        bak.write(s)
    with open(path, "r+b") as fh:
        fh.seek(off)
        fh.write(nb + b"\n" * padlen)
        fh.flush()
        os.fsync(fh.fileno())
    print(f"{name}: patched ({len(s)} -> {length} bytes incl. {padlen} pad)")
