#!/usr/bin/env python3
"""Live token/speed HUD for local Ollama chats:

    python3 ~/sand-watch/token-hud.py

Pure file-tail of the engine log — no network, no deps. Ctrl+C quits."""
import os, re, time

LOG = os.path.expanduser("~/.ollama/logs/server.log")
PROMPT_RE = re.compile(r"n_tokens =\s*(\d+)")
PROG_RE = re.compile(r"progress = ([0-9.]+)")

def main():
    while not os.path.exists(LOG):
        print("waiting for engine log...", end="\r"); time.sleep(1)
    f = open(LOG, "rb", buffering=0)
    f.seek(0, os.SEEK_END)
    last_tokens = None
    last_time = None
    speed = 0.0
    total = "?"
    prog = "-"
    while True:
        raw = f.readline()
        if not raw or len(raw) == 0:
            try:
                if f.tell() > os.path.getsize(LOG):   # rotated/truncated -> reopen
                    f.close(); f = open(LOG, "rb", buffering=0); f.seek(0, os.SEEK_END)
            except OSError:
                pass
            ts = time.strftime("%H:%M:%S")
            sp = f"{speed:.0f} tok/s" if speed else "idle"
            print(f"\x1b[2K\r[{ts}] prefill {total} tok | {sp} | {prog}", end="", flush=True)
            time.sleep(0.25)
            continue
        txt = raw.decode("utf-8", "replace")
        m = PROMPT_RE.search(txt)
        if not m:
            continue
        n = int(m.group(1)); now = time.time()
        pm = PROG_RE.search(txt)
        if pm:
            try: prog = f"{float(pm.group(1))*100:.0f}%"
            except ValueError: pass
        if last_tokens is not None and n >= last_tokens and now > last_time:
            inst = (n-last_tokens)/(now-last_time)
            speed = round(0.7*speed + 0.3*inst, 1) if speed else inst
        elif n < last_tokens:
            speed = 0.0     # new request started; counter reset
        last_tokens, last_time = n, now

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nbye")
