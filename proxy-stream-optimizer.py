#!/usr/bin/env python3
import http.server
import urllib.request
import json, os, re, sqlite3

PORT = 10101
COLIBRI_URL = "http://127.0.0.1:8080"
LLAMA_SPEC_URL = "http://127.0.0.1:11435"
OLLAMA_URL = "http://127.0.0.1:11434"

import sys
sys.path.insert(0, os.path.expanduser("~/.agents"))
import rag_context_store as rag_store

# Ensure proxy never routes internal loopback calls through sing-box or external proxy
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
urllib.request.install_opener(opener)

COLIBRI_MODELS = {
    "glm-5.2", "glm-5.2-colibri", "glm52",
    "glm-5.3", "glm-5.3-flash", "glm-5.3-flash-colibri", "glm53",
    "deepseek-v4", "deepseek-v4-colibri", "deepseek_v4", "deepseek-v4-flash",
    "kimi-k3", "kimi-k3-colibri", "kimi",
    "inkling", "inkling-colibri",
    "olmoe-colibri", "qwen38-colibri", "qwen36-colibri"
}

def is_colibri_model(model_name):
    if not model_name:
        return False
    m = model_name.lower().strip()
    if m.startswith("colibri") or m.endswith("colibri") or "colibri" in m:
        return True
    for c in COLIBRI_MODELS:
        if c in m:
            return True
    return False

def is_colibri_online():
    try:
        req = urllib.request.Request(f"{COLIBRI_URL}/v1/models", method='GET')
        with urllib.request.urlopen(req, timeout=0.2) as r:
            return r.status == 200
    except Exception:
        return False

def get_target_url(model_name=None):
    if model_name and is_colibri_model(model_name):
        if is_colibri_online():
            return COLIBRI_URL
        # Colibri backend is currently stopped -> auto-fallback to active in-memory model
    try:
        req = urllib.request.Request(f"{LLAMA_SPEC_URL}/health", method='GET')
        with urllib.request.urlopen(req, timeout=0.3) as r:
            if r.status == 200:
                return LLAMA_SPEC_URL
    except Exception:
        pass
    return OLLAMA_URL

def get_rag_context(query, session_id=None):
    try:
        return rag_store.retrieve_context(query, session_id=session_id)
    except Exception as e:
        print(f"RAG error: {e}")
        return ""

def flatten_tools(tools):
    if not isinstance(tools, list):
        return tools
    flat = []
    for t in tools:
        if not isinstance(t, dict):
            continue
        ttype = t.get('type')
        tname = t.get('name', '')
        # Drop bloated 3rd party plugin namespaces and heavy app GUI thread tools
        if tname.startswith('mcp__codex_apps__') or tname == 'mcp__codex_app':
            continue
        if ttype == 'function':
            flat.append(t)
        elif ttype == 'namespace' and 'tools' in t and isinstance(t['tools'], list):
            for sub_t in t['tools']:
                if isinstance(sub_t, dict) and sub_t.get('type') == 'function':
                    flat.append(sub_t)
        elif ttype == 'web_search':
            pass
    return flat

def sanitize_tool_calls(data):
    if not isinstance(data, dict):
        return data
    try:
        def clean_fn(fn):
            args = fn.get('arguments')
            if args is None or args == '' or args == 'null':
                fn['arguments'] = '{}'
            elif isinstance(args, str):
                try:
                    json.loads(args)
                except Exception:
                    fn['arguments'] = json.dumps({"command": args}) if args.strip() else "{}"
            elif isinstance(args, dict):
                fn['arguments'] = json.dumps(args)

        if 'choices' in data and isinstance(data['choices'], list):
            for choice in data['choices']:
                msg = choice.get('message', {})
                if 'tool_calls' in msg and isinstance(msg['tool_calls'], list):
                    for tc in msg['tool_calls']:
                        clean_fn(tc.get('function', {}))
                delta = choice.get('delta', {})
                if 'tool_calls' in delta and isinstance(delta['tool_calls'], list):
                    for tc in delta['tool_calls']:
                        clean_fn(tc.get('function', {}))
        elif 'output' in data and isinstance(data['output'], list):
            for item in data['output']:
                if item.get('type') == 'function_call':
                    clean_fn(item)
        elif 'item' in data and isinstance(data['item'], dict):
            if data['item'].get('type') == 'function_call':
                clean_fn(data['item'])
        elif 'response' in data and isinstance(data['response'], dict):
            for item in data['response'].get('output', []):
                if item.get('type') == 'function_call':
                    clean_fn(item)
    except Exception:
        pass
    return data

def normalize_conversation_tail(msgs):
    """Enforce what strict backends require: never end with 2+ assistant messages,
    and always finish on a user/tool turn. Merges loop-duplicate assistants away."""
    out = []
    for m in msgs:
        if not isinstance(m, dict):
            continue
        r = m.get('role')
        if out and r == 'assistant' and out[-1].get('role') == 'assistant':
            if json.dumps(m.get('content', '')) == json.dumps(out[-1].get('content', '')):
                continue  # exact repetition loop artifact -> drop
        out.append(m)
    while len(out) >= 2 and out[-1].get('role') == 'assistant' and out[-2].get('role') == 'assistant':
        out.pop(-2)  # keep the newest assistant of any remaining run
    if out:
        last = out[-1]
        last_role = last.get('role')
        last_type = last.get('type')
        if last_role not in ('user', 'tool') and last_type not in ('function_call', 'function_call_output'):
            out.append({"type": "message", "role": "user", "content": [{"type": "input_text", "text": "(continue)"}]})
    return out


class ProxyHandler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, HEAD')
        self.send_header('Access-Control-Allow-Headers', '*')
        self.end_headers()

    def do_HEAD(self):
        req = urllib.request.Request(f"{get_target_url()}{self.path}")
        try:
            with urllib.request.urlopen(req) as resp:
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    self.send_header(k, v)
                self.end_headers()
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            with open('/tmp/proxy_last_err.log', 'w') as ef:
                ef.write(tb)
            self.send_error(502, f"Proxy error: {str(e)}\n{tb}")

    def do_GET(self):
        if self.path in ('/', ''):
            out = b"Ollama is running"
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.send_header('Content-Length', str(len(out)))
            self.end_headers()
            self.wfile.write(out)
            return
        if self.path == '/api/version':
            out = b'{"version":"0.5.12"}'
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(out)))
            self.end_headers()
            self.wfile.write(out)
            return
        if self.path == '/api/tags':
            out = json.dumps({
                "models": [{
                    "name": "ornith-1.5-35b-uncensored:latest",
                    "model": "ornith-1.5-35b-uncensored:latest",
                    "modified_at": "2026-08-25T22:00:00Z",
                    "size": 13247182634,
                    "digest": "03e7efdd5ca1",
                    "details": {
                        "parent_model": "",
                        "format": "gguf",
                        "family": "qwen35moe",
                        "families": ["qwen35moe"],
                        "parameter_size": "35.5B",
                        "quantization_level": "Q2_K"
                    }
                }]
            }).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(out)))
            self.end_headers()
            self.wfile.write(out)
            return

        if self.path == '/v1/models':
            models = []
            # 1. Fetch from local In-Memory engines (Ollama / llama-server)
            try:
                backend = get_target_url()
                req = urllib.request.Request(f"{backend}/v1/models")
                with urllib.request.urlopen(req, timeout=0.5) as resp:
                    d = json.loads(resp.read().decode())
                    models.extend(d.get('data', []))
            except Exception:
                pass

            # 2. Fetch from Colibri engine (port 8080) if running
            try:
                req = urllib.request.Request(f"{COLIBRI_URL}/v1/models")
                with urllib.request.urlopen(req, timeout=0.3) as resp:
                    d = json.loads(resp.read().decode())
                    models.extend(d.get('data', []))
            except Exception:
                pass

            # If backends are idle, supply standard catalog
            if not models:
                models = [
                    {"id": "ornith-1.5-35b-uncensored", "object": "model", "owned_by": "local-moe"},
                    {"id": "qwen3.8-27b-uncensored", "object": "model", "owned_by": "local-moe"},
                    {"id": "glm-5.2-colibri", "object": "model", "owned_by": "colibri-frontier"},
                    {"id": "glm-5.3-flash-colibri", "object": "model", "owned_by": "colibri-frontier"},
                    {"id": "deepseek-v4-colibri", "object": "model", "owned_by": "colibri-frontier"}
                ]

            out = json.dumps({"object": "list", "data": models}).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(out)))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(out)
            return

        req = urllib.request.Request(f"{get_target_url()}{self.path}")
        try:
            with urllib.request.urlopen(req) as resp:
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(resp.read())
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            with open('/tmp/proxy_last_err.log', 'w') as ef:
                ef.write(tb)
            self.send_error(502, f"Proxy error: {str(e)}\n{tb}")

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        raw = self.rfile.read(length)
        with open('/tmp/codex_incoming_request.json', 'wb') as cf:
            cf.write(raw)
        import io
        self.rfile = io.BytesIO(raw)
        with open('/tmp/proxy_post_hit.log', 'a') as hit_f:
            hit_f.write(f"POST {self.path}\n")
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)
        with open('/tmp/last_raw_request.json', 'wb') as rf:
            rf.write(body)
        data = None
        user_text = ""

        try:
            data = json.loads(body.decode('utf-8'))
        except Exception:
            data = None

        if isinstance(data, dict):
            try:
                if 'tools' in data and isinstance(data['tools'], list):
                    data['tools'] = flatten_tools(data['tools'])

                if 'input' in data and isinstance(data['input'], list):
                    client_sys = ""
                    if 'instructions' in data and isinstance(data['instructions'], str):
                        client_sys += data['instructions'].strip() + "\n\n"

                    for item in data['input']:
                        if isinstance(item, dict) and item.get('role') in ('developer', 'system'):
                            c = item.get('content')
                            if isinstance(c, str):
                                client_sys += "\n\n" + c
                            elif isinstance(c, list):
                                for b in c:
                                    if isinstance(b, dict) and b.get('type') == 'input_text':
                                        client_sys += "\n\n" + b.get('text', '')

                    AUTONOMOUS_DIRECTIVE = (
                        "### CRITICAL OPERATIONAL RULES (MANDATORY ENFORCEMENT) ###\n"
                        "1. NO CONVERSATIONAL PROMISES: Never reply with conversational promises, filler, or plans (such as 'I will create...', 'Let me design...', or 'I am going to...').\n"
                        "2. IMMEDIATE TOOL EXECUTION: Immediately execute tools (such as `exec_command`) in your very first response to carry out the requested actions.\n"
                        "3. COMMAND BUFFER LIMIT (< 2,000 CHARACTERS):\n"
                        "   Each command argument in `exec_command` MUST NOT exceed 2,000 characters.\n"
                        "   NEVER paste a large file directly inside a single `cat << 'EOF'` bash command argument.\n"
                        "   To write files larger than 1.5KB, write a clean Python script (`python3 -c \"...\"`) or write in small modular chunks (< 1,500 characters each).\n"
                        "4. CONTINUE UNTIL VERIFIED: Continue executing tools until the entire task is finished, verified, and complete."
                    )
                    sys_prompt = ""
                    if client_sys.strip():
                        sys_prompt += client_sys.strip() + "\n\n"
                    sys_prompt += AUTONOMOUS_DIRECTIVE

                    for item in reversed(data['input']):
                        if isinstance(item, dict) and item.get('role') == 'user':
                            c = item.get('content')
                            if isinstance(c, str):
                                user_text = c
                            elif isinstance(c, list):
                                user_text = " ".join([b.get('text', '') for b in c if isinstance(b, dict)])
                            break

                    rag_snippet = get_rag_context(user_text) if user_text else ""
                    if rag_snippet:
                        sys_prompt += f"\n\n{rag_snippet}"

                    # Keep user, assistant, tool, AND function_call, function_call_output!
                    recent = []
                    for i in data['input']:
                        if not isinstance(i, dict):
                            continue
                        if i.get('role') in ('user', 'assistant', 'tool') or i.get('type') in ('function_call', 'function_call_output'):
                            # Truncate oversized historical command arguments to prevent poisoning the context window
                            if i.get('type') == 'function_call' and isinstance(i.get('arguments'), str) and len(i['arguments']) > 2500:
                                try:
                                    arg_obj = json.loads(i['arguments'])
                                    if 'cmd' in arg_obj and isinstance(arg_obj['cmd'], str):
                                        arg_obj['cmd'] = arg_obj['cmd'][:1500] + "\n... [truncated large command history]"
                                        i['arguments'] = json.dumps(arg_obj)
                                    elif 'command' in arg_obj and isinstance(arg_obj['command'], str):
                                        arg_obj['command'] = arg_obj['command'][:1500] + "\n... [truncated large command history]"
                                        i['arguments'] = json.dumps(arg_obj)
                                    else:
                                        i['arguments'] = i['arguments'][:1500] + '... [truncated large command history]"}'
                                except Exception:
                                    i['arguments'] = '{"command":"[truncated large command history]"}'
                            recent.append(i)
                    recent = recent[-30:]
                    
                    MAX_CHARS = 55000
                    current_chars = len(sys_prompt) + len(json.dumps(data.get('tools', [])))
                    kept_input = []
                    for i in reversed(recent):
                        i_str = json.dumps(i)
                        if current_chars + len(i_str) > MAX_CHARS and len(kept_input) >= 6:
                            break
                        kept_input.insert(0, i)
                        current_chars += len(i_str)

                    # Ensure conversation does not start with an orphaned function_call_output
                    while kept_input and kept_input[0].get('type') == 'function_call_output':
                        kept_input.pop(0)

                    if not any(i.get('role') == 'user' or i.get('type') == 'function_call_output' for i in kept_input):
                        kept_input.append({"type": "message", "role": "user", "content": [{"type": "input_text", "text": user_text if user_text else "Hello"}]})
                    
                    # Do NOT duplicate sys_prompt into input[0] because instructions already contains it!
                    data['input'] = normalize_conversation_tail(kept_input)
                    data['instructions'] = sys_prompt
                    body = json.dumps(data).encode('utf-8')

                elif 'messages' in data and isinstance(data['messages'], list):
                    messages = data['messages']
                    for m in reversed(messages):
                        if isinstance(m, dict) and m.get('role') == 'user':
                            c = m.get('content')
                            if isinstance(c, str):
                                user_text = c
                            elif isinstance(c, list):
                                user_text = " ".join([b.get('text', '') for b in c if isinstance(b, dict)])
                            break

                    rag_snippet = get_rag_context(user_text) if user_text else ""
                    AUTONOMOUS_DIRECTIVE = (
                        "### CRITICAL OPERATIONAL RULES (MANDATORY ENFORCEMENT) ###\n"
                        "1. NO CONVERSATIONAL PROMISES: Never reply with conversational promises or explanations (such as 'I will create...', 'Let me design...').\n"
                        "2. IMMEDIATE TOOL EXECUTION: Immediately execute tools (such as `exec_command`) in your response.\n"
                        "3. COMMAND BUFFER LIMIT (< 2,000 CHARACTERS):\n"
                        "   Each command argument in `exec_command` MUST NOT exceed 2,000 characters.\n"
                        "   To write files larger than 1.5KB, use a clean Python script (`python3 -c \"...\"`) or write in small modular chunks.\n"
                        "4. CONTINUE UNTIL VERIFIED: Continue executing tools until the entire task is finished, verified, and complete."
                    )
                    sys_prompt = "You are a helpful coding assistant. Answer concisely and accurately.\n\n" + AUTONOMOUS_DIRECTIVE
                    if rag_snippet:
                        sys_prompt += f"\n\n{rag_snippet}"

                    # Extract and combine any existing system prompts so they only appear once at index 0
                    non_system_msgs = []
                    for m in messages:
                        if isinstance(m, dict):
                            if m.get('role') in ('system', 'developer'):
                                c = m.get('content')
                                if isinstance(c, str) and c not in sys_prompt:
                                    sys_prompt += f"\n\n{c}"
                            elif m.get('role') in ('user', 'assistant', 'tool') or 'tool_calls' in m or 'tool_call_id' in m:
                                non_system_msgs.append(m)

                    lean_messages = [{"role": "system", "content": sys_prompt}]
                    recent_msgs = non_system_msgs[-30:]
                    
                    MAX_CHARS = 55000
                    current_chars = len(sys_prompt) + len(json.dumps(data.get('tools', [])))
                    
                    kept_msgs = []
                    for m in reversed(recent_msgs):
                        m_str = json.dumps(m)
                        if current_chars + len(m_str) > MAX_CHARS and len(kept_msgs) >= 6:
                            break
                        kept_msgs.insert(0, m)
                        current_chars += len(m_str)

                    if not any(m.get('role') == 'user' or 'tool_call_id' in m for m in kept_msgs):
                        kept_msgs.append({"role": "user", "content": user_text if user_text else "Hello"})
                    
                    lean_messages.extend(kept_msgs)
                    data['messages'] = normalize_conversation_tail(lean_messages)
                    body = json.dumps(data).encode('utf-8')
            except Exception:
                pass

        model_name = data.get('model') if isinstance(data, dict) else None
        target_backend = get_target_url(model_name)
        req = urllib.request.Request(
            f"{target_backend}{self.path}",
            data=body,
            headers={"Content-Type": "application/json"}
        )
        headers_sent = False
        try:
            if 'user_text' in locals() and user_text:
                try:
                    rag_store.store_conversation("default", "user", user_text)
                except Exception:
                    pass

            with urllib.request.urlopen(req) as resp:
                status = resp.status
                is_sse = 'text/event-stream' in resp.headers.get('Content-Type', '')
                self.send_response(status)
                if is_sse:
                    for k, v in resp.headers.items():
                        if k.lower() not in ('content-length', 'transfer-encoding'):
                            self.send_header(k, v)
                    self.end_headers()
                    headers_sent = True
                    assistant_text = ""
                    while True:
                        line = resp.readline()
                        if not line:
                            break
                        
                        if line.startswith(b'data: '):
                            data_str = line[6:].strip()
                            if data_str != b'[DONE]':
                                try:
                                    chunk = json.loads(data_str)
                                    chunk = sanitize_tool_calls(chunk)
                                    if 'choices' in chunk and len(chunk['choices']) > 0:
                                        delta = chunk['choices'][0].get('delta', {})
                                        delta_text = delta.get('content', '')
                                        if delta_text:
                                            assistant_text += delta_text
                                    line = b'data: ' + json.dumps(chunk, separators=(',', ':')).encode('utf-8') + b'\n\n'
                                except Exception:
                                    pass
                        
                        self.wfile.write(line)
                        self.wfile.flush()
                    if assistant_text:
                        try:
                            rag_store.store_conversation("default", "assistant", assistant_text)
                        except Exception:
                            pass
                else:
                    content = resp.read()
                    try:
                        resp_data = json.loads(content)
                        resp_data = sanitize_tool_calls(resp_data)
                        assistant_text = ""
                        if 'choices' in resp_data and len(resp_data['choices']) > 0:
                            msg = resp_data['choices'][0].get('message', {})
                            assistant_text = msg.get('content', '')
                            if assistant_text:
                                msg['content'] = re.sub(r'<think>.*?</think>', '', assistant_text, flags=re.DOTALL)
                        elif 'output' in resp_data:
                            with open('/tmp/proxy-response.log', 'w') as log_f:
                                log_f.write(json.dumps(resp_data['output'], indent=2))
                            # Strip the custom llama-server reasoning block completely
                            resp_data['output'] = [o for o in resp_data['output'] if o.get('type') != 'reasoning']
                            
                            if len(resp_data['output']) > 0:
                                msg = resp_data['output'][0].get('content', [{}])[0]
                                assistant_text = msg.get('text', '')
                                if assistant_text:
                                    msg['text'] = re.sub(r'<think>.*?</think>', '', assistant_text, flags=re.DOTALL)
                        
                        content = json.dumps(resp_data).encode('utf-8')
                        if assistant_text:
                            rag_store.store_conversation("default", "assistant", assistant_text)
                    except Exception:
                        pass

                    for k, v in resp.headers.items():
                        if k.lower() not in ('content-length', 'transfer-encoding'):
                            self.send_header(k, v)
                    self.send_header('Content-Length', str(len(content)))
                    self.end_headers()
                    headers_sent = True
                    self.wfile.write(content)
                    self.wfile.flush()
        except Exception as e:
            try:
                import traceback, time
                tb = traceback.format_exc()
                with open('/tmp/proxy_last_err.log', 'w') as ef:
                    ef.write(tb)
                
                is_responses_stream = ('/v1/responses' in self.path) and isinstance(data, dict) and data.get('stream', False)
                if is_responses_stream:
                    msg_id = f"msg_err_{int(time.time())}"
                    resp_id = f"resp_err_{int(time.time())}"
                    
                    err_detail = ""
                    if isinstance(e, urllib.error.HTTPError):
                        try:
                            err_raw = e.read().decode('utf-8', errors='ignore')
                            err_json = json.loads(err_raw)
                            err_detail = err_json.get('error', {}).get('message', '') or err_raw
                        except Exception:
                            err_detail = str(e)
                    else:
                        err_detail = str(e)

                    clean_msg = f"Task in progress. (Server: {err_detail[:120] if err_detail else 'recovering stream'}). Continuing..."

                    if not headers_sent:
                        self.send_response(200)
                        self.send_header('Content-Type', 'text/event-stream; charset=utf-8')
                        self.send_header('Cache-Control', 'no-cache')
                        self.send_header('Connection', 'keep-alive')
                        self.send_header('Access-Control-Allow-Origin', '*')
                        self.end_headers()
                    
                    events = [
                        {"type": "response.created", "response": {"id": resp_id, "model": model_name or "local", "status": "in_progress"}},
                        {"type": "response.in_progress", "response": {"id": resp_id, "model": model_name or "local", "status": "in_progress"}},
                        {"type": "response.output_item.added", "item": {"id": msg_id, "type": "message", "role": "assistant", "status": "in_progress", "content": []}},
                        {"type": "response.content_part.added", "item_id": msg_id, "part": {"type": "output_text", "text": ""}},
                        {"type": "response.output_text.delta", "item_id": msg_id, "delta": clean_msg},
                        {"type": "response.output_text.done", "item_id": msg_id, "text": clean_msg},
                        {"type": "response.output_item.done", "item": {"id": msg_id, "type": "message", "role": "assistant", "status": "completed", "content": [{"type": "output_text", "text": clean_msg}]}},
                        {"type": "response.completed", "response": {"id": resp_id, "model": model_name or "local", "status": "completed", "output": [{"id": msg_id, "type": "message", "role": "assistant", "status": "completed", "content": [{"type": "output_text", "text": clean_msg}]}]}}
                    ]
                    for ev in events:
                        self.wfile.write(f"event: {ev['type']}\ndata: {json.dumps(ev)}\n\n".encode('utf-8'))
                        self.wfile.flush()
                    return
                else:
                    if not headers_sent:
                        self.send_error(502, f"Proxy error: {str(e)}\n{tb}")
            except Exception:
                pass

def run():
    server = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), ProxyHandler)
    server.serve_forever()

if __name__ == '__main__':
    run()
