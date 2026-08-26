# Mac OSX Local LLM Turbo & RAG Context Optimizer 🚀

A highly-customized, lightning-fast architecture to run large Mixture of Experts (MoE) models (like Qwen 3.6 35B / Ornith) on macOS / Apple Silicon. This stack ensures **maximum inference speed**, **zero extra RAM overhead** for context injection, and prevents context-window crashing when using massive agentic tooling payloads.

## 🔥 Features

* **Zero-RAM SSD RAG Context Window**: A zero-dependency SQLite FTS5 (BM25) search engine (`rag_context_store.py`) that chunks and indexes your codebase on your SSD. Instead of consuming 20GB+ RAM to hold large contexts, it smartly queries your codebase and injects the top results directly into the hidden system prompt.
* **Smart Streaming Proxy (`proxy-stream-optimizer.py`)**: 
  * Intercepts and dynamically truncates historical context to strictly fit within your model's exact context limit (e.g. 8192 tokens), preventing the dreaded `exceeds available context size` errors when agentic tools send massive payloads.
  * Filters out leaky `<think>` tags from DeepSeek-style reasoning models while keeping the underlying reasoning intact in the RAG memory.
  * Normalizes the OpenAI Responses API formats so `llama-server` understands them natively.
* **Background Daemon Indexer**: Automatically scans and re-indexes your files every 60 seconds (`rag-file-indexer.py`) without blocking your main workflow.
* **Jinja Crash Patches**: A custom permissive ChatML Jinja template (`chatml-permissive.jinja`) that preserves 100% of the model's native tool-calling abilities while bypassing the infamous `Jinja Exception: System message must be at the beginning` and `No user query found` crashes caused by non-standard system prompts.

## 🛠️ Architecture

1. **Model Layer**: `llama-server` (running via `com.user.ornith.spec.plist` on port 11435) with `--reasoning-format deepseek`.
2. **Proxy Layer**: `proxy-stream-optimizer.py` (running on port 10101) sits between your client (like Codex CLI) and `llama-server`.
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
