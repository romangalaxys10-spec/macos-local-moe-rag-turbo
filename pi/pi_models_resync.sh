#!/bin/zsh
# pi-models-resync — mirror opencode's ACTIVE openai-compatible providers into ~/.pi/agent/models.json
# Fired by LaunchAgent com.user.pi.models.resync on WatchPaths changes (opencode.jsonc, auth.json).
# Idempotent: rewrites the file only when merged output actually differs.

set -eu
export PATH="/usr/bin:/bin:/usr/sbin:/sbin:$HOME/.local/node-v22/bin:$PATH"
LOG="$HOME/.pi/agent/pi-models-resync.log"

# /usr/bin/python3 is an Xcode-license shim on this machine (exit 69); use the real one.
PYTHON="$HOME/.local/bin/python3"
[ -x "$PYTHON" ] || PYTHON=$(command -v python3)

"$PYTHON" - <<'PYEOF' >> "$LOG" 2>&1
import json, re, os, tempfile

def load_jsonc(p):
    t = open(os.path.expanduser(p)).read()
    t = re.sub(r'^\s*//.*$', '', t, flags=re.M)
    return json.loads(t)

oc = load_jsonc('~/.config/opencode/opencode.jsonc')
auth = json.load(open(os.path.expanduser('~/.local/share/opencode/auth.json')))
provs_in = oc.get('provider', {})
disabled = set(oc.get('disabled_providers', []))

out = {"providers": {}}
for pid, p in provs_in.items():
    if pid in disabled:
        continue
    if pid == 'ollama':  # legacy alias: same endpoint as ollama-local, zero models
        continue
    opts = p.get('options', {})
    # options.apiKey wins when present (unsloth-local & friends); auth.json is the fallback store.
    api_key = opts.get('apiKey') or (auth[pid].get('key') if pid in auth else None)
    out['providers'][pid] = {
        'name': p.get('name', pid),
        'baseUrl': opts['baseURL'],
        'api': 'openai-completions',
        'apiKey': api_key or 'EMPTY',
        'models': [{'id': mid, 'name': m.get('name', mid), **({'limit': m['limit']} if m.get('limit') else {})} for mid, m in p.get('models', {}).items()],
    }

dest = os.path.expanduser('~/.pi/agent/models.json')
new = json.dumps(out, indent=2) + "\n"
cur = open(dest).read() if os.path.exists(dest) else ""
if new == cur:
    print(f"{__import__('time').strftime('%F %T')} unchanged ({len(out['providers'])} providers)")
else:
    d = os.path.dirname(dest)
    fd, tmp = tempfile.mkstemp(dir=d, prefix='.models.')
    with os.fdopen(fd, 'w') as f:
        f.write(new)
    os.replace(tmp, dest)
    print(f"{__import__('time').strftime('%F %T')} synced {len(out['providers'])} providers / "
          f"{sum(len(p['models']) for p in out['providers'].values())} models -> models.json")
PYEOF
