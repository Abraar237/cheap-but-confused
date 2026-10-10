#!/bin/zsh
# L4 v2 (persistent session notes) regeneration on the same 50 tasks, then evaluate + summarize.
cd "/Users/prometheus/VizzAI/cache layout cost research/experiments/t2_bfcl"
PY=../bfcl_env/bin/python
echo "===== GENERATE l4 v2 $(date)"
$PY run_bfcl.py generate --model openrouter/google/gemini-3.1-flash-lite-l4 --run-ids --temperature 0 --num-threads 3 2>&1 | grep -v "^-*$" | grep -v "^ID: "
echo "===== generate l4 exit ${pipestatus[1]} $(date)"
echo "===== EVALUATE l4"
$PY run_bfcl.py evaluate --model openrouter/google/gemini-3.1-flash-lite-l4 --test-category multi_turn --partial-eval 2>&1 | grep "Running test\|Accuracy\|Error\|Traceback"
echo "===== SUMMARIZE"
$PY run_bfcl.py summarize google/gemini-3.1-flash-lite
echo "===== DONE $(date)"
