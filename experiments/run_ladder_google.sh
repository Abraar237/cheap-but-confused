#!/bin/bash
# Google capability ladder (plan B, guardrail not lifted). Sized 2026-10-10 19:17 from the 2-task smoke test:
# 2.5-flash ~1.8x and 3.6-flash ~5x the per-episode cost of 3.1-flash-lite. Runs after the batteries finish.
cd "$(dirname "$0")"
while pgrep -f "run_batteries_google.sh" > /dev/null; do sleep 30; done
# rung A: gemini-2.5-flash, L1/L3/L4 on the seed-0 half of the grid (72 tasks x 3 layouts = 216 episodes, ~$5.6)
python3 runner.py --model google/gemini-2.5-flash --layouts L1,L3,L4 --tasks="-s0$" --workers 3
# rung B: gemini-3.6-flash, L1/L3 on the 36-task repeat-battery subset (72 episodes, ~$2.7)
python3 runner.py --model google/gemini-3.6-flash --layouts L1,L3 --tasks="-L(6|18)-(low|high)-s0" --workers 3
echo LADDER DONE
