#!/usr/bin/env python3
import http.server
import urllib.request
import json, os, re, sqlite3

PORT = 10101
TARGET_URL = "http://127.0.0.1:11435"
import sys
sys.path.insert(0, os.path.expanduser("~/.agents"))
import rag_context_store as rag_store

def get_rag_context(query, session_id=None):
    try:
        return rag_store.retrieve_context(query, session_id=session_id)
    except Exception as e:
        print(f"RAG error: {e}")
        return ""

def sanitize_tool_calls(data):
    if not isinstance(data, dict):
        return data
    try:
        if 'choices' in data and isinstance(data['choices'], list):
            for choice in data['choices']:
                msg = choice.get('message', {})
                if 'tool_calls' in msg and isinstance(msg['tool_calls'], list):
                    for tc in msg['tool_calls']:
                        fn = tc.get('function', {})
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
                delta = choice.get('delta', {})
                if 'tool_calls' in delta and isinstance(delta['tool_calls'], list):
                    for tc in delta['tool_calls']:
                        fn = tc.get('function', {})
                        if 'arguments' in fn:
                            args = fn['arguments']
                            if args is None or args == 'null':
                                fn['arguments'] = '{}'
        elif 'output' in data and isinstance(data['output'], list):
            for item in data['output']:
                if item.get('type') == 'function_call':
                    args = item.get('arguments')
                    if args is None or args == '' or args == 'null':
                        item['arguments'] = '{}'
                    elif isinstance(args, str):
                        try:
                            json.loads(args)
                        except Exception:
                            item['arguments'] = json.dumps({"command": args}) if args.strip() else "{}"
                    elif isinstance(args, dict):
                        item['arguments'] = json.dumps(args)
    except Exception:
        pass
    return data

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
        req = urllib.request.Request(f"{TARGET_URL}{self.path}")
        try:
            with urllib.request.urlopen(req) as resp:
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    self.send_header(k, v)
                self.end_headers()
        except Exception as e:
            self.send_error(500, str(e))

    def do_GET(self):
        if self.path in ('/', ''):
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(b"Ollama is running")
            return
        if self.path == '/api/version':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"version":"0.5.12"}')
            return
        if self.path == '/api/tags':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({
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
            }).encode('utf-8'))
            return

        req = urllib.request.Request(f"{TARGET_URL}{self.path}")
        try:
            with urllib.request.urlopen(req) as resp:
                self.send_response(resp.status)
                for k, v in resp.headers.items():
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(resp.read())
        except Exception as e:
            self.send_error(500, str(e))

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length)

        try:
            data = json.loads(body.decode('utf-8'))
            user_text = ""
            if 'input' in data and isinstance(data['input'], list):
                sys_prompt = "You are a helpful coding assistant."
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

                lean_input = [{"role": "developer", "content": [{"type": "input_text", "text": sys_prompt}]}]
                recent = [i for i in data['input'] if isinstance(i, dict) and i.get('role') in ('user', 'assistant', 'tool')][-20:]
                
                MAX_CHARS = 15000
                current_chars = len(sys_prompt) + len(json.dumps(data.get('tools', [])))
                kept_input = []
                for i in reversed(recent):
                    c = i.get('content', '')
                    c_str = json.dumps(c) if isinstance(c, list) else str(c)
                    if current_chars + len(c_str) > MAX_CHARS:
                        break
                    kept_input.insert(0, i)
                    current_chars += len(c_str)
                if not any(i.get('role') == 'user' for i in kept_input):
                    kept_input.append({"role": "user", "content": [{"type": "input_text", "text": user_text if user_text else "Hello"}]})
                
                lean_input.extend(kept_input)
                data['input'] = lean_input
                body = json.dumps(data).encode('utf-8')

            elif 'messages' in data and isinstance(data['messages'], list):
                messages = data['messages']
                for m in reversed(messages):
                    if m.get('role') == 'user':
                        c = m.get('content')
                        if isinstance(c, str):
                            user_text = c
                        elif isinstance(c, list):
                            user_text = " ".join([b.get('text', '') for b in c if isinstance(b, dict)])
                        break

                rag_snippet = get_rag_context(user_text) if user_text else ""
                sys_prompt = "You are a helpful coding assistant. Answer concisely and accurately."
                if rag_snippet:
                    sys_prompt += f"\n\n{rag_snippet}"

                # Extract and combine any existing system prompts so they only appear once at index 0
                non_system_msgs = []
                for m in messages:
                    if m.get('role') in ('system', 'developer'):
                        c = m.get('content')
                        if isinstance(c, str) and c not in sys_prompt:
                            sys_prompt += f"\n\n{c}"
                    elif m.get('role') in ('user', 'assistant', 'tool'):
                        non_system_msgs.append(m)

                lean_messages = [{"role": "system", "content": sys_prompt}]
                recent_msgs = non_system_msgs[-20:]
                
                # Truncate older messages if the total payload is too large for 8k context (~24k chars)
                MAX_CHARS = 15000
                current_chars = len(sys_prompt) + len(json.dumps(data.get('tools', [])))
                
                # Iterate backwards to keep the newest messages first
                kept_msgs = []
                for m in reversed(recent_msgs):
                    c = m.get('content', '')
                    c_str = c if isinstance(c, str) else json.dumps(c)
                    if current_chars + len(c_str) > MAX_CHARS:
                        break
                    kept_msgs.insert(0, m)
                    current_chars += len(c_str)

                if not any(m.get('role') == 'user' for m in kept_msgs):
                    kept_msgs.append({"role": "user", "content": user_text if user_text else "Hello"})
                
                lean_messages.extend(kept_msgs)
                data['messages'] = lean_messages
                body = json.dumps(data).encode('utf-8')
        except Exception:
            pass

        req = urllib.request.Request(
            f"{TARGET_URL}{self.path}",
            data=body,
            headers={"Content-Type": "application/json"}
        )
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
                    in_think = False
                    think_buffer = ""
                    assistant_text = ""
                    while True:
                        line = resp.readline()
                        if not line:
                            break
                        
                        if line.startswith(b'data: '):
                            try:
                                chunk = json.loads(line[6:])
                                delta_text = ""
                                if 'choices' in chunk and len(chunk['choices']) > 0:
                                    delta = chunk['choices'][0].get('delta', {})
                                    delta_text = delta.get('content', '')
                                elif 'delta' in chunk:
                                    delta_text = str(chunk.get('delta', ''))
                                
                                if delta_text:
                                    assistant_text += delta_text
                                    filtered_text = ""
                                    for char in delta_text:
                                        think_buffer += char
                                        if not in_think:
                                            if "<think>" in think_buffer:
                                                in_think = True
                                                filtered_text += think_buffer.split("<think>")[0]
                                                think_buffer = ""
                                            elif not "<think>".startswith(think_buffer):
                                                filtered_text += think_buffer
                                                think_buffer = ""
                                        else:
                                            if "</think>" in think_buffer:
                                                in_think = False
                                                parts = think_buffer.split("</think>")
                                                think_buffer = parts[1] if len(parts) > 1 else ""
                                    
                                    # Write back the filtered text to the chunk
                                    if 'choices' in chunk and len(chunk['choices']) > 0:
                                        chunk['choices'][0]['delta']['content'] = filtered_text
                                    elif 'delta' in chunk:
                                        chunk['delta'] = filtered_text
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
                    # Leave reasoning_content intact
                    
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
                                import json
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
                        if k.lower() != 'content-length':
                            self.send_header(k, v)
                    self.send_header('Content-Length', str(len(content)))
                    self.end_headers()
                    self.wfile.write(content)
                    self.wfile.flush()
        except Exception as e:
            try:
                self.send_error(500, str(e))
            except Exception:
                pass

def run():
    server = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), ProxyHandler)
    server.serve_forever()

if __name__ == '__main__':
    run()
