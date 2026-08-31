# Mac OSX Local LLM Turbo & RAG Context Optimizer 🚀

A highly-customized, lightning-fast architecture to run large Mixture of Experts (MoE) models (like Qwen 3.6 35B / Ornith) on macOS / Apple Silicon. This stack ensures **maximum inference speed**, **zero extra RAM overhead** for context injection, and prevents context-window crashing when using massive agentic tooling payloads.

## 🔥 Features

* **Dual-Tier Multi-MoE Architecture**:
  * **Tier 1 (High-Speed In-Memory)**: Runs `Ornith-1.5-35B-A3B-CRACK-Q3_K_M.gguf` (17.17 GB) with quantized KV cache (`-ctk q4_0 -ctv q4_0`), delivering **44+ tokens/second** on Apple Silicon with 16k context.
  * **Tier 2 (Colibrì Frontier Expert Streaming)**: Integrated [JustVugg/colibri](https://github.com/JustVugg/colibri) pure-C engine with native Apple Silicon Metal GPU acceleration (`backend_metal.mm`). Streams sparse routed experts from internal 6.39 GB/s NVMe SSD into RAM, unlocking **frontier 284B–744B models** (DeepSeek V4 Flash, GLM-5.2, GLM-5.3-Flash, Kimi K3) on a 32GB Mac!
* **16,384 Context Window**: Eliminates `unexpected EOF` and context ceiling crashes during multi-thousand-token code generation.
* **Zero-RAM SSD RAG Context Window**: A zero-dependency SQLite FTS5 (BM25) search engine (`rag_context_store.py`) that chunks and indexes your codebase on your SSD. Instead of consuming 20GB+ RAM to hold large contexts, it smartly queries your codebase and injects the top results directly into the hidden system prompt.
* **Intelligent Multi-Backend Gateway (`proxy-stream-optimizer.py` on :10101)**: 
  * **Dynamic Model Router**: Auto-routes in-memory models (`ornith-1.5-35b-uncensored`, `qwen3.8-27b`) to Ollama/llama-server and frontier models (`glm-5.2`, `deepseek-v4`, `glm-5.3`) to Colibrì (:8080).
  * **Unified `/v1/models` Catalog**: Dynamically merges all local GGUF and Colibrì models into a single OpenAI-compatible endpoint.
  * **Tool Call Argument Sanitizer**: Intercepts and validates all tool call arguments on the fly, preventing `unexpected end of JSON input` crashes.
  * **Non-Blocking SSE Streaming**: Real-time token streaming that keeps sockets alive and resets client read deadlines.
  * **Context Management**: Intercepts and dynamically truncates historical context to strictly fit within the window, avoiding prompt overflow.
* **Turnkey CLI Tools**:
  * `colibri-manager`: Start, stop, plan, diagnose, and launch the live 3D expert cortex dashboard (`coli web`).
  * `coli`: Universal CLI launcher for all Colibrì family engines.
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
