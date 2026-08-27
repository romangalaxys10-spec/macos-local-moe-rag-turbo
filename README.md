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

## 🌙 Hardening round II — context cure, concurrency guards, RAM policy (2026-08-26 evening)
* **Context ceiling cured at the source**: the imported models carried baked-in `num_ctx 16384` params layers — every request beyond 16k died no matter what. Params-only Modefile rebuilds (in `ollama-jinja-guard-fix/`) raise this to **32k** while preserving every original stop/batch/GPU setting — templates untouched, weights reused.
* **Proxy (:10101) now defuses the trailing-assistant killer**: collapses repeated/paired assistant tails into one turn and appends a `(continue)` nudge before anything reaches strict backends. Trim budget lifted 15k→45k chars so real agent payloads flow without over-shaving.
* **Anti-loop sampler**: ornith launcher runs `--repeat-penalty 1.12`, ending the degenerate rewrite-loops.
* **One-model RAM policy** via new `com.user.ollama.single-model-env.plist`: max one LLM resident, flash attention, quantized KV (q8_0), 45s idle unload — measured prefill +13% and halved cache RAM.
* **Live token HUD**: `token-hud.py` streams prompt-tokens / % / tok-s from the engine log in any Terminal.
Full post-mortem chain lives in `ollama-jinja-guard-fix/README.md`.

## 🔁 2026-08-27 — engine migration: vLLM-Metal added → decommissioned · Unsloth Studio replaces Ollama

This repo's control stack moved its serving layer twice today; history and tooling below.

### Phase 1 — vLLM-Metal experiment (added, benchmarked, retired)
`~/tools/vllm-install/` tools published under `vllm-metal/` here:
- `use-model` — rewritten pure-bash switcher: flushes ollama residents (3-attempt verify),
  pkills prior serve, HF_HUB_DISABLE_XET turbo-resume of MLX weights, health-polls ≤5 min.
  Aliases: `abl`, `heretic`, `qwen35`, `gemma4`; warn-and-continue unload policy documented inline.
- `setup-engine` — venv bootstrap for `~/.venv-vllm-metal`.
- `fetch-heretic-gguf.py` — authenticated multi-stream HF fetch of the 6.1 GB i1-Q5_K_M HERETIC GGUF.
- `bench-runner` + `serve-bench.sh` — repeatable warm-decode/prefill benchmarks writing verbatim
  result lines (see README section below for verdict format).
**Verdict:** mxfp8 9B dense served at 23.9 tok/s decode / 287 tok/s prefill vs ollama ~32 — kept
only as opt-in lane; later the whole engine was dropped when Unsloth landed (same llama.cpp core,
zero config burden). ⚠️ discipline rule learned: after any comparison bench, re-serve the USER'S
previous selection.

### Phase 2 — Unsloth Studio is now THE local engine (:8888)
- Serving: `unsloth studio -p 8888` via LaunchAgent **com.user.unsloth.studio**
  (KeepAlive, log `~/.unsloth/studio-server.log`). Ollama app/engine/agents fully removed;
  legacy plists archived in `~/Library/LaunchAgents/retired-ollama-20260827/`.
- Model migration: all Ollama blobs exported as named GGUFs with APFS `cp -c` clones into
  `~/.cache/huggingface/hub/unsloth-local-ggufs/`, registered via `POST /api/hub/scan-folders`.
  Served ids: highiq-heretic, qwen35-abl, qwen3.8-27b-uncensored, ornith-1.5-35b-uncensored,
  ornith-1.5-9b, qwen3.8-27b-iq1 (+ mradermacher HF repo auto-detected).
- One-model RAM policy preserved through Studio setting
  `PUT /api/settings/openai-auto-switch`: enabled + idle_unload_active +
  auto_unload_idle_seconds=600 + auto_unload_keep_kv=true.
- pi wiring: provider `unsloth-local` (baseURL http://127.0.0.1:8888/v1) — see `pi/pi_models_resync.sh`
  in this repo for the CRITICAL precedence fix:
  `api_key = opts.get('apiKey') or (auth[pid].get('key') if pid in auth else None)`
  (old script forwarded options.apiKey only for z-ai → every other provider shipped apiKey='EMPTY'
  → upstreams answered 401 Invalid token payload).
- Native macOS app: `/Applications/Unsloth Studio.app` — Swift/WKWebView shell,
  source under `native-app/UnslothStudio.swift` (+ `native-app/Info.plist`). Rebuild:
  `cd ~/path/to/repo/native-app && swiftc -O -target arm64-apple-macos13.0 UnslothStudio.swift \
     -o "Unsloth Studio.app/Contents/MacOS/UnslothStudio" -framework WebKit && \
   codesign --force -s - "Unsloth Studio.app"`
  (⚠️ default target macosx28 makes LaunchServices reject the bundle with error -10825 on darwin-27;
  direct exec still worked, which is why it looked healthy in terminal tests).
- Credentials referenced ONLY by path in docs/scripts: `~/.unsloth/studio/auth/{zcode-api-key,zcode-admin.txt}`.

### Debug war stories preserved
- GGUF multiline chat template inside an ollama Modelfile MUST be triple-quoted:
  `TEMPLATE """…"""` else import fails with "command must be one of from/license/…".
- Thinking models need max_tokens ≥ ~400 or top-level content returns empty (reasoning eats budget);
  streamed deltas arrive as `reasoning_content`.
- Mimosa/PreToolUse hooks on this box block `curl | sh` installers and scripts composing shell
  commands/paths from unvalidated strings — replicate installers natively instead
  (uv venv + pip --no-deps + bundled NO_TORCH=1 installer), validate every path component.
