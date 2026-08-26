# Mac OSX Local LLM Turbo & RAG Context Optimizer 🚀

A highly-customized, lightning-fast architecture to run large Mixture of Experts (MoE) models (like Qwen 3.6 35B / Ornith) on macOS / Apple Silicon. This stack ensures **maximum inference speed**, **zero extra RAM overhead** for context injection, and prevents context-window crashing when using massive agentic tooling payloads.

## 🔥 Features

* **Upgraded Model (Q3_K_M — 17.17 GB)**: Runs `Ornith-1.5-35B-A3B-CRACK-Q3_K_M.gguf` with quantized KV cache (`-ctk q4_0 -ctv q4_0`), delivering **44+ tokens/second** on Apple Silicon with deep reasoning.
* **16,384 Context Window**: Eliminates `unexpected EOF` and context ceiling crashes during multi-thousand-token code generation.
* **Zero-RAM SSD RAG Context Window**: A zero-dependency SQLite FTS5 (BM25) search engine (`rag_context_store.py`) that chunks and indexes your codebase on your SSD. Instead of consuming 20GB+ RAM to hold large contexts, it smartly queries your codebase and injects the top results directly into the hidden system prompt.
* **Smart Streaming Proxy (`proxy-stream-optimizer.py`)**: 
  * **Dynamic Backend Routing**: Auto-detects and seamlessly routes between standalone `llama-server` (:11435) and `Ollama` daemon (:11434).
  * **Tool Call Argument Sanitizer**: Intercepts and validates all tool call arguments on the fly, preventing `unexpected end of JSON input` crashes.
  * **Non-Blocking SSE Streaming**: Real-time token streaming that keeps sockets alive and resets client read deadlines.
  * **Context Management**: Intercepts and dynamically truncates historical context to strictly fit within the window, avoiding prompt overflow.
* **Background Daemon Indexer**: Automatically scans and re-indexes your files every 60 seconds (`rag-file-indexer.py`) without blocking your main workflow.
* **100% Exception-Free Permissive Jinja**: Custom ChatML Jinja template (`chatml-permissive.jinja`) with 0 `raise_exception` statements, supporting native tool calling, safe string/mapping argument handling, and system/developer roles.

## 🛠️ Architecture

1. **Model Layer**: `Ollama` / `llama-server` (running on port 11434 / 11435) with 16k context and Metal GPU acceleration.
2. **Proxy Layer**: `proxy-stream-optimizer.py` (running on port 10101) sits between your client (like Codex CLI) and the model backend.
3. **Data Layer**: SQLite FTS5 Database keeping track of codebase chunks and conversational history.

## 🚀 Setup & Installation

### 1. Copy Files
Drop the python files into your `~/.agents/` or `~/.local/bin/` directories as referenced.

### 2. Load the LaunchDaemons (macOS)
The repository includes macOS `launchd` `.plist` files for persistence. Place them in `~/Library/LaunchAgents/` and load them:
```bash
launchctl load ~/Library/LaunchAgents/com.user.ornith.spec.plist
launchctl load ~/Library/LaunchAgents/com.user.proxy.optimizer.plist
launchctl load ~/Library/LaunchAgents/com.user.rag.indexer.plist
```

### 3. Point your Client
Configure your AI client (Codex CLI, VSCode, Cursor) to point to the optimizer proxy rather than the raw model:
```toml
base_url = "http://127.0.0.1:10101/v1"
```

## 🧠 Why this was built?
When running high-end agentic workflows, injecting dozens of tools and skills into the context window blows up the prompt size. `llama-server` rigidly rejects oversized prompts to protect RAM. This custom proxy acts as an intelligent bouncer—trimming just enough history to fit the tools, appending the latest user message to bypass strict Jinja template rules, intercepting unsupported `reasoning` outputs, and expanding the model's memory via SSD-based RAG. 

*Engineered natively on macOS.*

## 🛡️ Deployed Fix: "Jinja Exception: No user query found in messages" (2026-08-26)

`ornith-1.5-35b-uncensored` and `qwen3.8-27b-uncensored` shipped a strict Qwen-style chat template
**embedded inside the GGUF weights** (`tokenizer.chat_template`) that raised a hard exception whenever
an agent sent a turn without a genuine user message (typical during tool-loop "continue" steps),
killing responses with an instant HTTP 500.

**Applied fix:** the guard lines were surgically removed *in place* inside both GGUF blobs at the
exact KV byte offsets, padding to original length so the GGUF layout is untouched. Verified: the
previously-fatal no-user-message payload now returns HTTP 200 on both models; normal chats unchanged.
This makes the fix immune to clients that bypass the proxy on :10101 and hit Ollama directly.

**See `ollama-jinja-guard-fix/`** for the full record: README with reusable GGUF-KV locator snippet,
idempotent re-patch tool for fresh re-imports, revert tooling, and untouched snapshot copies of both
original templates. Note: a fresh pull/re-import of these models restores the strict template in a NEW
blob digest — rerun the patch per that folder's docs. The `chatml-permissive.jinja` +
proxy user-message workaround remain as belt-and-suspenders layers.

