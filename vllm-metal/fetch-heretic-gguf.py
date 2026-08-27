#!/usr/bin/env python3
"""Authenticated turbo-fetch of the HighIQ-HERETIC-UNCENSORED Q5_K_M GGUF twin
into the HF cache, for local Ollama import (avoids ollama's own throttled lane)."""
import os, time

os.environ["HF_HUB_ENABLE_HF_TRANSFER"] = "1"   # empirically delivered fastest lanes tonight

from huggingface_hub import snapshot_download  # noqa: E402

REPO = "mradermacher/Qwen3.5-9B-Claude-4.6-HighIQ-INSTRUCT-HERETIC-UNCENSORED-i1-GGUF"
TARGET = "Qwen3.5-9B-Claude-4.6-HighIQ-INSTRUCT-HERETIC-UNCENSORED.i1-Q5_K_M.gguf"

t0 = time.time()
p = snapshot_download(REPO, allow_patterns=[TARGET])
print(f"DONE in {time.time()-t0:.0f}s -> {p}")
