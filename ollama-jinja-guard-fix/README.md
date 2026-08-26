# Ollama "Jinja Exception: No user query found in messages" — fix record (2026-08-26)

## Root cause
`ornith-1.5-35b-uncensored` and `qwen3.8-27b-uncensored` carry a strict Qwen-style Jinja
chat template **embedded inside the GGUF weights** (`tokenizer.chat_template`). It ends with:

    {%- if ns.multi_step_tool %}
        {{- raise_exception('No user query found in messages.') }}
    {%- endif %}

When a coding CLI sends a turn with no genuine user message (system + assistant/tool only,
typical during agent "continue" steps), Ollama 0.32.x evaluates this template per request and
returns instant HTTP 500 — killing the response mid-task.

Why not a Modelfile? `ollama create` validates the `TEMPLATE` directive with legacy Go
text/template (`function "content" not defined` on any bare Jinja identifier), and the GGUF-embedded
Jinja outranks any manifest template layer anyway. No env var switches it off.

## Fix applied (in place, byte-length preserving)
For each model, inside `~/.ollama/models/blobs/…` at KV value offset, the 3 guard lines were
removed and the remainder padded with `\n` to the original length so the GGUF layout is untouched:

| model | blob | chat_template len | val offset |
|---|---|---|---|
| ornith-1.5-35b-uncensored | sha256-10edce4298d4… | 7764 | 10934978 |
| qwen3.8-27b-uncensored | sha256-7cb7cedcb3ea… | 8952 | 10935048 |

Backups: `orig-ornith-chat_template.jinja`, `orig-qwen-chat_template.jinja` (this folder).
Revert anytime: `python3 revert.py`

## Verified
- killer payload `[system, assistant]` → previously 500 in ~5 ms, now HTTP 200 + completion on BOTH models
- normal `[system, user]` chat still works (ornith replied "READY")
- `ollama show <model> --template` reflects patched text

## Re-patch after re-imports
A fresh pull/import restores the strict template in a NEW blob. To re-patch manually, run the
GGUF KV scanner below, then remove the same guard block with equal-length `\n` padding:

```python
# locate tokenizer.chat_template in a GGUF: prints len and byte offset
import struct, sys
f = open(sys.argv[1], 'rb')
assert f.read(4) == b'GGUF'
ver, tc, kvc = struct.unpack('<IQQ', f.read(20))
SIZES = {0:1,1:1,2:2,3:2,4:4,5:4,6:4,7:1,10:8,11:8,12:8}
for _ in range(kvc):
    n = struct.unpack('<Q', f.read(8))[0]; key = f.read(n).decode()
    vt = struct.unpack('<I', f.read(4))[0]
    if vt == 8:
        vn = struct.unpack('<Q', f.read(8))[0]; off = f.tell(); val = f.read(vn)
        if key == 'tokenizer.chat_template':
            print(key, 'len=', vn, 'off=', off)
            open('current-chat_template.jinja', 'w').write(val.decode())
    elif vt == 9:
        et, cnt = struct.unpack('<IQ', f.read(12))
        if et == 8:
            for __ in range(cnt):
                ln = struct.unpack('<Q', f.read(8))[0]; f.seek(ln, 1)
        else:
            f.seek(cnt * SIZES[et], 1)
    else:
        f.seek(SIZES[vt], 1)
```

New model manifests after a re-import: check paths under
`~/.ollama/models/manifests/registry.ollama.ai/library/<model>/<tag>` for the fresh weight blob digest.
