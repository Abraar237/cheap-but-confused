#!/bin/bash
# Waits for the main Google grid to finish, then runs the repeat battery (36 tasks x L1 x 4 extra reps) and the phrasing battery.
cd "$(dirname "$0")"
while pgrep -f "runner.py --model google/gemini-3.1-flash-lite --layouts L1,L2,L3,L4" > /dev/null; do sleep 60; done
for rep in 1 2 3 4; do
  python3 runner.py --model google/gemini-3.1-flash-lite --layouts L1 --tasks="-L(6|18)-(low|high)-s0" --battery repeat --rep $rep --workers 4
done
python3 runner.py --model google/gemini-3.1-flash-lite --layouts L1,L3 --tasks="-L(12|18)-high-s0" --phrasing 2 --workers 4
echo BATTERIES DONE
