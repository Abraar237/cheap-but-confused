#!/bin/zsh
# Full T2 run: 50 tasks (ids 0,2,...,48 of multi_turn_base and multi_turn_long_context) x L1/L3/L4
# on google/gemini-3.1-flash-lite via OpenRouter. One layout per process, sequential.
set -u
cd "/Users/prometheus/VizzAI/cache layout cost research/experiments/t2_bfcl"
PY=../bfcl_env/bin/python
$PY run_bfcl.py set-ids multi_turn_base=0,2,4,6,8,10,12,14,16,18,20,22,24,26,28,30,32,34,36,38,40,42,44,46,48 multi_turn_long_context=0,2,4,6,8,10,12,14,16,18,20,22,24,26,28,30,32,34,36,38,40,42,44,46,48
for L in l1 l3 l4; do
  echo "===== GENERATE $L $(date)"
  $PY run_bfcl.py generate --model openrouter/google/gemini-3.1-flash-lite-$L --run-ids --temperature 0 --num-threads 3 2>&1 | grep -v "^-*$" | grep -v "^ID: " 
  echo "===== generate $L exit ${pipestatus[1]} $(date)"
done
for L in l1 l3 l4; do
  echo "===== EVALUATE $L"
  $PY run_bfcl.py evaluate --model openrouter/google/gemini-3.1-flash-lite-$L --test-category multi_turn --partial-eval 2>&1 | grep "Running test\|Accuracy\|Error\|Traceback"
done
echo "===== SUMMARIZE"
$PY run_bfcl.py summarize google/gemini-3.1-flash-lite
echo "===== DONE $(date)"
