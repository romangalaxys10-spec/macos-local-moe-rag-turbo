#!/bin/bash
# Serve + benchmark Qwen3.5-9B uncensored variants on vLLM-Metal (:8000)
set -u
VENV=~/.venv-vllm-metal
source "$VENV/bin/activate"
RESULTS=/Users/d/sand-watch/vllm-bench-results.txt
PRIMARY="TheCluster/Qwen3.5-9B-Claude-4.6-HighIQ-INSTRUCT-HERETIC-UNCENSORED-MLX-mxfp8"
FALLBACK="mlx-community/Qwen3.5-9B-4bit"

echo "$(date +%H:%M:%S) freeing ollama slot politely..." >> $RESULTS
for m in $(curl -s localhost:11434/api/ps | python3 -c "import json,sys;print(' '.join(x['name'] for x in json.load(sys.stdin)['models']))"); do
  curl -s localhost:11434/api/generate -d "{\"model\":\"$m\",\"keep_alive\":0,\"prompt\":\"x\",\"options\":{\"num_predict\":0}}" -o /dev/null
done

for MODEL in "$PRIMARY" "$FALLBACK"; do
  echo "$(date +%H:%M:%S) === serving: $MODEL ===" >> $RESULTS
  nohup vllm serve "$MODEL" --port 8000 --max-model-len 8192 > /tmp/vllm-serve.log 2>&1 &
  SERVER_PID=$!
  UP=0
  for i in $(seq 1 100); do   # up to ~25 min: weights download + load
    sleep 15
    if ! kill -0 $SERVER_PID 2>/dev/null; then echo "$(date +%H:%M:%S) server died early" >> $RESULTS; break; fi
    CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 3 localhost:8000/health 2>/dev/null || echo 000)
    if [ "$CODE" = "200" ]; then UP=1; echo "$(date +%H:%M:%S) HEALTHY after ~$((i*15))s" >> $RESULTS; break; fi
  done
  [ $UP = 0 ] && { echo "$(date +%H:%M:%S) never became healthy; next candidate..." >> $RESULTS; kill $SERVER_PID 2>/dev/null; continue; }

  T0=$(python3 -c 'import time;print(time.time())')
  RESP=$(curl -s --max-time 120 localhost:8000/v1/chat/completions -H "Content-Type: application/json" \
    -d '{"model":"'"$MODEL"'","max_tokens":80,"messages":[{"role":"user","content":"Write a haiku about GPUs, then explain why Apple Silicon is great for local AI in two sentences."}]}')
  T1=$(python3 -c 'import time;print(time.time())')
  echo "$RESP" | python3 -c "
import json,sys,time
d=json.load(sys.stdin)
u=d['usage']; wall=$T1-$T0
print(f\"BENCH {MODEL}: gen={u['completion_tokens']/wall:.1f} tok/s | {u['completion_tokens']} tok in {wall:.1f}s | TTFT-ish total\")" >> $RESULTS
  LONG=$(python3 - <<'PY'
import json
line = ("Review this code and list issues concisely.\n\n" + "def f(i):\n    return i*2+hash(i)%7\n"*120)[:6000]
print(json.dumps({"model":"'"$MODEL"'","max_tokens":40,"messages":[{"role":"user","content":line+" Reply DONE only."}]}))
PY
)
  T2=$(python3 -c 'import time;print(time.time())')
  LR=$(curl -s --max-time 180 localhost:8000/v1/chat/completions -H "Content-Type: application/json" -d "$LONG")
  T3=$(python3 -c 'import time;print(time.time())')
  echo "$LR" | python3 -c "
import json,sys,time
d=json.load(sys.stdin); u=d['usage']
print(f\"PREFILL-BENCH: {u['prompt_tokens']}/{$T3-$T2:.1f}s = {u['prompt_tokens']/($T3-$T2):.0f} tok/s prefill\")" >> $RESULTS
  kill $SERVER_PID 2>/dev/null; sleep 3
  break   # success on first working candidate -> stop chain
done
echo "$(date +%H:%M:%S) BENCH PIPELINE COMPLETE" >> $RESULTS
