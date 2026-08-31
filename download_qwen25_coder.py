#!/usr/bin/env python3
import os
import sys
import time
import urllib.request
import threading

URL = "https://huggingface.co/bartowski/Qwen2.5-Coder-32B-Instruct-abliterated-GGUF/resolve/main/Qwen2.5-Coder-32B-Instruct-abliterated-Q4_K_S.gguf"
DEST = "/Users/d/models/qwen2.5-coder-32b-uncensored/Qwen2.5-Coder-32B-Instruct-abliterated-Q4_K_S.gguf"
PART_DEST = DEST + ".downloading"
LOG_FILE = os.path.expanduser("~/.ollama/download_qwen25_coder.log")

def log(msg):
    ts = time.strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{ts} {msg}\n"
    sys.stdout.write(line)
    sys.stdout.flush()
    with open(LOG_FILE, "a") as f:
        f.write(line)

def get_remote_size(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}, method="HEAD")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return int(resp.headers.get("Content-Length", 0))

def download():
    with open(LOG_FILE, "w") as f:
        f.write("")
    
    log(f"Starting download from: {URL}")
    log(f"Destination: {DEST}")

    if os.path.exists(DEST):
        sz = os.path.getsize(DEST)
        remote_sz = get_remote_size(URL)
        if sz == remote_sz and sz > 18 * (1024**3):
            log(f"Model file already complete: {sz / (1024**3):.2f} GB")
            return

    remote_sz = get_remote_size(URL)
    log(f"Remote file size: {remote_sz / (1024**3):.2f} GB ({remote_sz} bytes)")

    existing_sz = os.path.getsize(PART_DEST) if os.path.exists(PART_DEST) else 0
    if existing_sz > 0:
        log(f"Resuming download from {existing_sz / (1024**3):.2f} GB ({existing_sz} bytes)")

    chunk_size = 16 * 1024 * 1024 # 16 MB
    retries = 0
    max_retries = 100

    while existing_sz < remote_sz:
        try:
            req = urllib.request.Request(
                URL,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Range": f"bytes={existing_sz}-"
                }
            )
            with urllib.request.urlopen(req, timeout=30) as resp, open(PART_DEST, "ab" if existing_sz > 0 else "wb") as out_f:
                start_time = time.time()
                bytes_this_session = 0
                last_log_time = time.time()

                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    out_f.write(chunk)
                    existing_sz += len(chunk)
                    bytes_this_session += len(chunk)

                    now = time.time()
                    if now - last_log_time >= 5:
                        elapsed = now - start_time
                        speed = (bytes_this_session / elapsed) / (1024**2) if elapsed > 0 else 0
                        pct = (existing_sz / remote_sz) * 100
                        remaining_bytes = remote_sz - existing_sz
                        eta_sec = remaining_bytes / (speed * 1024 * 1024) if speed > 0 else 0
                        log(f"Progress: {existing_sz / (1024**3):.2f} / {remote_sz / (1024**3):.2f} GB ({pct:.1f}%) | Speed: {speed:.1f} MB/s | ETA: {eta_sec/60:.1f} min")
                        last_log_time = now

            if existing_sz >= remote_sz:
                break
        except Exception as e:
            retries += 1
            if retries > max_retries:
                log(f"FATAL: Max retries exceeded: {e}")
                sys.exit(1)
            log(f"Warning: Connection dropped ({e}). Retrying in 3s (attempt {retries}/{max_retries})...")
            time.sleep(3)
            existing_sz = os.path.getsize(PART_DEST) if os.path.exists(PART_DEST) else 0

    log("Verifying downloaded file...")
    if os.path.getsize(PART_DEST) == remote_sz:
        os.rename(PART_DEST, DEST)
        log(f"SUCCESS: Model downloaded and verified at {DEST} ({remote_sz / (1024**3):.2f} GB)")
    else:
        log(f"ERROR: Size mismatch. Expected {remote_sz}, got {os.path.getsize(PART_DEST)}")

if __name__ == "__main__":
    download()
