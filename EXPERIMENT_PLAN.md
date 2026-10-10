# Experiment plan: Cheap but Confused? The accuracy cost of cache-optimized context layouts in LLM agents

Status: frozen at CP2 on 2026-10-10 after three discarded calibration passes (logged in MILESTONES.md;
no calibration episode enters the analysis). Pre-registered directions D1-D5 were recorded in
MILESTONES.md on 2026-10-10 before any model call. Testbed hash: see `corpus/FROZEN.json`.

## 1. Question

Prompt caching rewards one context layout: a byte-stable prefix that is only ever appended to. Holding
the information content of an agent's context fixed, does that layout cost task accuracy relative to a
relevance-reordered layout, an oracle-pruned layout and a stable-prefix + recitation hybrid, and does the
cache discount pay for the loss? We measure accuracy against provider-reported cached tokens and billed
USD (OpenRouter `usage.cost`), never modelled cost.

## 2. The StaleTrap testbed (T1, primary; self-built; frozen)

**Environment.** `experiments/env.py`: three stateful back-office domains (inventory, calendar, ticketing)
plus a never-required messaging/HR domain, 39 JSON-schema tools (10 read, 19 write, 10 unused), a
deterministic local executor, and schema-level read/write metadata: every result declares which
(record, field) values it states (dedicated reads, writes that report the new value, and every row of a
listing). The shared prefix (system prompt 1,849 cl100k tokens + tools 4,513) measures 5,102 tokens on
Google's tokenizer, above every provider's implicit-cache minimum.

**Tasks.** 144 scripted episodes = 3 domains x 3 templates x 4 lengths (6/12/18/30 tool calls) x 2
distractor levels x 2 seeds, each with two phrasings. Composition per length:

| Length | Trap threads (chains) | Neutral threads | Questions | Distractor calls | Update-to-question distance |
|---|---|---|---|---|---|
| 6 | 1 (c1) | 1 | 2 | 3 | 2-3 calls |
| 12 | 2 (c1, c2) | 2 | 4 | 5 | 3-6 |
| 18 | 3 (c1, c2, c1) | 3 | 6 | 8 | 3-7 |
| 30 | 4 (c1, c2, c3, c2) | 4 | 8 | 14 | 4-9 |

A **trap thread** reads a record's field, later updates it one to three times, then asks for the current
value at a no-tool question step (`tool_choice: none`; the question says tools are disabled and to answer
from the conversation). Every stale value in context differs from the final answer by construction (checked
programmatically, 360/360). A **neutral thread** reads a field once and asks for it later; nothing in
context competes. Two **trap kinds**: *own* (the agent's own write returns the new value explicitly; 4
templates: inventory price, calendar room, calendar attendees, ticketing status) and *external* (someone
else changes the record; the agent only sees the new value as one row inside an unrelated listing it was
asked for: `list_bin_contents`, `get_room_schedule`, `list_tickets`; 5 templates: inventory quantity x2
including the compound below-threshold judgement, calendar start time, ticketing assignee, ticketing
priority). Chains above 1 combine own writes with a final external change. **Distractor level** changes the
volume and pressure of distractor calls, not their count: low = compact single-record reads and writes on
unrelated records; high = verbose listings, near-miss identifiers (one digit transposed), and writes to
other fields of thread records. Ground truth is the executor's live state at question time; answers are
canonicalised (numbers, HH:MM, lower-cased strings, yes/no) and exact-matched.

**Scoring.** Per question: correct vs live state; `stale_present` (a superseded value for that record and
field is actually in the transcript) marks whether the trap materialised. Per action step: tool and
argument correctness and execution success (the agent's own mistakes propagate to the live state; the
question is still scored against the real world). Episode success = all questions correct.

## 3. Layouts (`experiments/layouts.py`; content identical for L1, L2, L4)

| Id | Layout | Prefix | How |
|---|---|---|---|
| L1 | cache-optimal | stable | system + tools, every block verbatim in arrival order, newest last; tools masked by `tool_choice`, never removed |
| L2 | relevance-reordered | rewritten each turn | same blocks, stable-sorted by number of record identifiers shared with the current turn, most relevant last |
| L3 | pruned (content changes) | breaks at first edit | every (record, field) value that a later result restates is redacted in place to `<superseded at step k>`; a result whose stated values are all superseded becomes `[result superseded by step k]`; rule is schema-level and transcript-derived, so it is an upper bound for a real pruner |
| L4 | hybrid | stable (append-only) | L1 + a pointer-only session note prepended to each user turn as it is sent (goal, step number, and for each record with an updated observation which step is current and which are superseded; no values); every turn keeps its note, so the history is append-only |

Anthropic: `cache_control` on the system block and on the newest user turn. OpenAI: automatic. Google:
implicit only (explicit breakpoints create a billed cache per call; measured 3.5-5.8x an implicit hit).
Each episode runs in one process, turns sequential, `session_id` per episode, temperature 0, reasoning
effort minimal, `max_tokens` 700. Provider errors are retried up to three times with backoff and logged.

## 4. Models

| Family | Model (OpenRouter id) | Price in / cache read / out per MTok (2026-10-10) | Caching | Status |
|---|---|---|---|---|
| Google | `google/gemini-3.1-flash-lite` | 0.25 / 0.025 / 1.50 | implicit, best-effort | runnable now |
| Anthropic | `anthropic/claude-haiku-5.5` | 0.10 / 0.01 / 0.50 (write 0.125) | explicit breakpoints; on/off control | blocked by workspace guardrail (reported) |
| OpenAI | `openai/gpt-5-mini` (fallback `gpt-5-nano` 0.05 / 0.005 / 0.40) | 0.25 / 0.025 / 2.00 | automatic >= 1,024 | blocked by workspace guardrail (reported) |

`gemini-2.5-flash-lite` was the planned Google model; it returned malformed function calls on ~30% of
tool-calling turns with this 39-tool catalogue (deterministic, provider-side) and was dropped.

## 5. Grid and batteries

- **T1 full factorial:** 144 tasks x 4 layouts per model (576 episodes, ~9,900 LLM calls per model).
- **Cache on/off at fixed layout** (Anthropic only): L1 with and without `cache_control`, 36 tasks (the
  seed-0, high-distractor cells), to show caching itself is output-neutral on this provider.
- **Repeat battery:** 30 stratified tasks x L1 x 5 identical runs on the Google model (temperature 0 is
  not deterministic on these routes).
- **Phrasing battery:** 36 tasks x L1 and L3 on phrasing 2 on the Google model.
- **T2 external arm:** BFCL v3 multi-turn (base + long-context) on a 50-task subset with L1, L3, L4 on two
  models, if the harness runs cleanly (feasibility in `experiments/t2_bfcl/FEASIBILITY.md`); else
  tau2-bench retail. Decision and reason recorded in MILESTONES.md.
- **T3** (LongMemEval_S slice) only if spend < $14 after T1 and T2.

## 6. Analysis (`experiments/analyze.py` -> `results/analysis.json`; every paper number)

Unit = task. Per model and layout: trap-step accuracy, neutral-step accuracy, episode success, billed USD,
cache-read fraction (overall and history-only, i.e. excluding the static prefix), USD per correct task.
Paired within-task contrasts L1-L2, L1-L3, L4-L1, L4-L3, L2-L3: two-sided sign-flip permutation (20,000),
task-bootstrap 95% CIs (10,000), paired d_z, and a template-cluster exact sign-flip as a robustness column.
Interactions tested directly by label permutation (5,000): layout gap x length (slope per call), x
distractor, trap vs neutral (difference of differences), x model family. D3 recovery fraction
(L4-L1)/(L3-L1) with bootstrap CI. D5: USD per correct task from billed cost, then recomputed under
counterfactual cache-read multipliers 0 to 1x of the input price, reporting the multiplier at which the
cheapest layout per correct task flips. Benjamini-Hochberg over the full family of primary tests from day
one; bold survivors only. Hand audit of >= 30 wrong answers coded stale_value / distractor_record /
arithmetic_or_count / abstain_or_unparsed / other, shipped as `results/audit_sample.json`.

## 7. Budget (cap $30; hard stop $24 in `cost_tracker.py`; billed `usage.cost` logged per call)

Measured on `gemini-3.1-flash-lite` (calibration 3, discarded): L1 $0.0112 per 18-call episode and
$0.0179 per 30-call episode (78% cached); L3 $0.0124 and $0.0216 (71% cached, 1.15x L1); pilot-1 ratios put
L2 at ~1.7x L1 and L4 at ~1.1x L1. Mean over the four lengths ~$0.010 (L1), so ~$0.05 per task over the
four layouts.

| Item | Episodes | Estimate |
|---|---|---|
| T1 Google gemini-3.1-flash-lite, 4 layouts | 576 | $7.0 |
| T1 Anthropic claude-haiku-5.5, 4 layouts (2.5x cheaper per token) | 576 | $3.0 |
| T1 OpenAI gpt-5-mini, 4 layouts (half grid, seed 0, if budget allows; else gpt-5-nano full) | 288-576 | $3.5-4.5 |
| Cache on/off (Anthropic, 36 tasks) + repeat (150 episodes) + phrasing (72) | 258 | $2.0 |
| T2 external arm, 50 tasks x 3 layouts x 2 models | 300 | $3.5 |
| Pilots and calibration (spent, discarded) | | $0.4 |
| **Total** | | **~$19.5-20.5** |

If the guardrail is not lifted, the paper runs three Google models (3.1-flash-lite, 3.5-flash-lite,
3.6-flash) as a one-family capability ladder and says so; the Anthropic on/off control is then replaced by
a Google implicit-hit-vs-miss within-layout comparison.

Amendment 2026-10-10 19:17 (after the main grid, before any ladder episode was scored): the guardrail was
re-probed and is still in place. 3.5-flash-lite was smoke-tested and dropped because it returns malformed
function calls on about a third of tool-calling turns with our catalogue (the same fault as 2.5-flash-lite).
The ladder is therefore 2.5-flash (older generation, thinking on), 3.1-flash-lite (full grid) and 3.6-flash
(newest generation). Budget forces partial grids: 2.5-flash runs L1/L3/L4 on the seed-0 half (72 tasks);
3.6-flash runs L1/L3 on the 36-task subset used for the repeat battery. Contrasts are paired within model on
the tasks each model ran; the model-by-layout interaction is tested on the tasks common to all three.

## 8. Threats and controls

Best-effort caching: report the observed per-turn hit distribution, not nominal. Caching is output-neutral:
on/off control (Anthropic) and hit-vs-miss comparison (Google). Temperature-0 nondeterminism: repeat
battery. Prefix-size effects: the static prefix is identical across layouts; history-only cache fraction
reported. Oracle pruning: L3 uses transcript-derived supersession; stated as an upper bound. Model
execution errors: action-step fidelity reported per layout; questions scored against live state. Phrasing:
battery on phrasing 2. Multiple comparisons: one BH family.
