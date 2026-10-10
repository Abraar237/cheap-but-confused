# Cheap but Confused? · Milestones & Checkpoints

Brief: INSTRUCTIONS.md. Budget cap **$30** (hard stop $24; the OpenRouter key is shared with
`../indic search gap research/`). The user authorised CP1-CP6 without stopping (2026-10-10);
report once at the end. Update this file at every checkpoint.

## Problem-statement history
- 2026-10-10 Pre-emption sweep by the planning session (`lit_review/00_preemption_sweep_2026-10-10.md`):
  verdict ALIVE-BUT-CROWDED. Nearest: Don't Break the Cache 2601.06007 (no accuracy), TokenPilot
  2606.17016 (method, confounded), CAPC 2607.15516 (compression only), CacheWeaver 2606.19667
  (single-turn RAG), 2505.15561 (reordering ~ shuffle in RAG; our D2 null). Chosen.

## Pre-registered directions (recorded 2026-10-10, BEFORE any experiment or pilot call; verbatim from INSTRUCTIONS.md §1.4)
- [x] **D1 (stale-retention cost).** L1 accuracy is below L3 on stale-trap steps, the gap grows with trajectory length, and there is no comparable gap on neutral steps.   Recorded: 2026-10-10
- [x] **D2 (order-only effect is small, cost is large).** L2 does not significantly beat L1 (consistent with 2505.15561, where reordering was no better than shuffling), while its cache-read fraction falls below 20% and its USD per task rises by >= 3x on 0.1x-read pricing. L2 is dominated on the frontier.   Recorded: 2026-10-10
- [x] **D3 (the hybrid dominates).** L4 recovers >= 50% of the L1-to-L3 accuracy gap while keeping >= 80% of L1's cache-read fraction, and sits on or inside the frontier for every model.   Recorded: 2026-10-10
- [x] **D4 (model dependence).** The L1-vs-L3 gap shrinks with model capability; the confusion cost is largest for the cheapest models, which is where caching saves the least absolute money.   Recorded: 2026-10-10
- [x] **D5 (price threshold).** Per correct task, L3 is cheapest when cache reads are expensive and L1/L4 become cheapest below a cache-read price threshold; report the threshold per model and compare with the ~$0.55/MTok break-even reported by Bouchard (2026) and the ~10-turn break-even of 2603.04814.   Recorded: 2026-10-10

If a direction fails or reverses, it is reported plainly in the abstract. This is a project-log pre-registration, not a registry filing. No OpenRouter call other than the key/credit check had been made at the time of recording.

## Environment sanity (2026-10-10)
- [x] OpenRouter key remaining credit: **$49.72** of a $50 limit (checked 2026-10-10 via /auth/key; shared with the sibling project). Hard stop for this project: $24.
- [x] **GUARDRAIL BLOCKER (reported to user 2026-10-10):** the key's workspace guardrail blocks every non-Google model
      (anthropic/claude-haiku-5.5, openai/gpt-5-mini, gpt-5.6-luna, gpt-5-nano, deepseek-v4-flash, qwen3.7/3.8-flash, kimi-k2.6,
      mistral-small, llama-4-maverick, glm-5, claude-sonnet-5 all return "Model blocked by guardrail"). Only google/* goes through.
      User asked to lift it at openrouter.ai (workspace guardrails). Until lifted, only one family is runnable.
- [x] Per-model smoke test (>=5.6k-token system+tools prefix, 3 sequential turns, 4 s apart; results/smoke_test.json, diag cost $0.015):
      - google/gemini-2.5-flash-lite, implicit caching (no cache_control): turn0 cached=0 ($0.000574), turn1 cached=5355 ($0.000093), turn2 cached=5353. Reliable hits.
      - google/gemini-3.1-flash-lite, implicit: turn1 cached=6157 ($0.000195 vs $0.001577 cold), turn2 cached=0 (a MISS 4 s later): best-effort, report the hit distribution.
      - Explicit cache_control on Gemini via OpenRouter: reports cached=6292 from turn 0 and bills ~$0.00069/turn on 3.1-flash-lite (3.5x an implicit hit) and
        ~$0.00054 on 2.5-flash-lite (5.8x): it creates an explicit cache every call (write + storage). DO NOT use cache_control on Gemini; implicit only.
      - A 1.1k-token prefix (no tools) never caches on either Gemini model (below the 2,048/4,096 minimum), confirming the >=4.5k prefix requirement.
      - Anthropic/OpenAI smoke tests pending the guardrail lift.
- [x] tectonic / ffmpeg / node v25 / Chrome / playwright / gh (Abraar237) / modal profile thesreedath: all OK. Skills present in ~/.claude/skills.
- [x] **ELEVENLABS BLOCKER (reported to user 2026-10-10):** key returns HTTP 401 "Invalid API key" on text-to-speech for every model id
      (multilingual_v2, turbo_v2_5, flash_v2_5, v3). Film narration at CP5 needs a valid TTS-scoped key.
- Prices re-fetched 2026-10-10 from /api/v1/models (per 1M tokens): claude-haiku-5.5 in 0.10 / read 0.01 / write 0.125; gpt-5-mini 0.25 / 0.025;
  gpt-5.6-luna 0.20 / 0.02 / write 0.25; gpt-5-nano 0.05 / 0.005; gemini-3.1-flash-lite 0.25 / 0.025 / write 0.0833; gemini-2.5-flash-lite 0.10 / 0.01 / write 0.0833;
  deepseek-v4-flash 0.017 / 0.0168 (no real discount on this route).

## CP1 · Lit review + pre-emption: DONE 2026-10-10
- [x] Recency sweep (37 arXiv API queries by submission date, 536 ids screened, 59 read) -> lit_review/recency_2026-10-10.md
- [x] Sweep references re-verified: 59/59 OK (lit_review/sweep_refs_verification.md, verify_refs.py)
- [x] Angles A (stale/position in agent histories, 31 new) and B (context management + caching economics, 45 new)
- [x] lit_review.csv: 174 unique verified ids; LIT_REVIEW.md with the novelty table written BEFORE any result
- [x] Verdict: **ALIVE-BUT-CROWDED**. No paper holds content fixed, varies layout, in a multi-turn tool agent, with billed
      cache telemetry and accuracy. New nearest neighbours to delineate: Token Reduction Is Not Cost Reduction 2607.12161
      (billed cache split + success, but compression not layout) and What Does a Harness Buy 2610.04433 (harness-level cost,
      not content-fixed). TokenPilot is now EMNLP 2026 Findings.

## CP2 · Experiment plan frozen: DONE 2026-10-10
- 2026-10-10 Testbed built: experiments/env.py (3 task domains + 1 never-used messaging/HR domain, 39 JSON tools, deterministic executor with
  schema-level read/write metadata), build_corpus.py (StaleTrap tasks), layouts.py (L1-L4 serialisers), runner.py, cost_tracker.py ($24), analyze.py.
- 2026-10-10 Pre-freeze calibration log (all discarded files are results/raw/_discarded*.jsonl; none enters the analysis):
  - pilot 1 (gemini-2.5-flash-lite, 7 episodes, 29 tools, prefix 3.3k Gemini tokens): tool calling, implicit caching (L1 0.73 cached, L2 0.35-0.51,
    L3 0.53-0.67), L3 redaction and L4 note all verified in transcripts; completed episodes scored 12/12 on trap steps (ceiling risk);
    Gemini sometimes emitted tool names namespaced `default_api.*` (two episodes lost): runner now normalises that prefix and logs it.
  - prefix enlarged to clear the 4,096-token implicit-cache minimum of Gemini 3.x on Google's tokenizer: +10 messaging/HR tools (never
    required by any task; "mask, don't remove" realism) + procedures and glossary text. Measured 5,102 Gemini tokens at turn 1.
  - length 30 added (4 lengths: 6/12/18/30; 144 tasks), chain-3 traps at L=30, and the update-to-question distance widened with length
    (QGAP 2-3 / 3-6 / 3-7 / 4-9 calls) so the current value does not always sit at the end of the context. Decided BEFORE any accuracy
    number on the new corpus was seen; motivated by the 12/12 pilot ceiling and the length-dose pre-registration (D1).
  - calibration 1 (gemini-2.5-flash-lite, L1, 36 episodes planned): ~30% of action turns returned finish_reason=error with
    native_finish_reason MALFORMED_FUNCTION_CALL / UNEXPECTED_TOOL_CALL (the model writes Python-style `default_api.x()` calls that Google
    drops); deterministic on retry; across many tools (get_event 43, get_room_schedule 27, set_price 27, ...). Run killed and discarded.
    Probe of 5 first-turn requests x 4 newer Gemini models: 3.1-flash-lite, 3.5-flash-lite, 2.5-flash, 3.6-flash all 5/5 clean tool calls.
    **Google arm = google/gemini-3.1-flash-lite** (the brief's named candidate; $0.25 in / $0.025 read). 2.5-flash-lite is not usable on
    this harness and is reported as such in the paper's limitations.
  - Gemini: reasoning stays ~75 tokens on 2.5-flash-lite whatever the `reasoning` field says; 0 on 3.x with effort=minimal.
  - calibration 2 (gemini-3.1-flash-lite, L1, own-update traps, 3 episodes before kill): 10/10 trap steps at L18/L30 high; $0.0107 (L18) and
    $0.0166 (L30) per episode, 75-83% cached, prefix 5,140 Gemini tokens. CEILING on own-update traps.
  - design change 2 (before any further data): **external-update trap kind** added. Someone else changes the record and the agent only sees
    the new value as a row inside an unrelated listing (list_bin_contents / get_room_schedule / list_tickets); 5 of 9 templates support it,
    4 keep own-update traps; chains >1 mix own writes with a final external change. Listing results now declare per-row states, L3 redacts
    inside listing rows, L4's note lists only records with superseded observations. Rationale: this is the realistic source of staleness
    (2610.05281) and keeps L3's supersession rule exact.
  - calibration 3 (gemini-3.1-flash-lite, L1 + L3 on the 5 external templates at L18/L30 high, 14 of 20 episodes before kill, discarded):
    L1 external-trap accuracy 13/19 (0.68), L3 26/28 (0.93), neutral 19/19 and 28/28; every error used a stale value (stale_present true);
    action fidelity 311/312; 0 retries. Cost L1 $0.0112 (L18) / $0.0179 (L30), L3 $0.0124 / $0.0216 (1.15x), cache 0.78 vs 0.71.
    Headroom confirmed: FREEZE.
- [x] EXPERIMENT_PLAN.md + site/plan.html written; budget table from the measured episodes; cost_tracker armed ($24)
- [x] **Testbed frozen 2026-10-10: corpus/FROZEN.json manifest SHA-256 8717956a533c53c56ac8c52d00fb5de5000a8490659f3de7d14ee1e02df5898b** (144 tasks, 720 questions: 360 trap
      [200 external, 160 own; chains 1/2/3 = 180/144/36], 360 neutral; 2,376 tool calls; 240 external updates)
- [x] Full Google grid launched 2026-10-10 (144 x L1-L4 = 576 episodes, 4 workers) -> results/raw/google_gemini-3.1-flash-lite.jsonl
- Spend at CP2 close: $0.59 (all pilots and calibrations; discarded files kept under results/raw/_discarded*)

## CP3 · Experiments + analysis
- Incident 2026-10-10 17:30: the T1 runner and the T2 BFCL driver both wrote results/spend.json without a cross-process lock; a torn read made 177 T1 episodes fail at their first call (each a few tenths of a cent). cost_tracker.py now uses an fcntl lock and atomic rename; the grid was restarted at 17:40 and resumes the missing episodes (keys are idempotent).
- Design correction 2026-10-10 18:05 (found by the T2 agent on BFCL, then confirmed in T1): an L4 note prepended only to the newest user turn at send time is NOT append-only, because the next turn re-serialises that earlier turn without it and rewrites the prefix. L4 now keeps every turn's note in the history (user_sent stored per block). The 55 L4 episodes run under the non-persistent variant ($0.56) are discarded (results/raw/_discarded_L4v1_nonpersistent_note.jsonl) and re-run; L1-L3 unaffected. The BFCL arm's L4 was re-run the same way (v2).
- Main grid finished 2026-10-10 19:08: gemini-3.1-flash-lite, 144 tasks x 4 layouts = 576 episodes, 0 failures after the two restarts; grid spend $8.47 (L1 $1.87, L2 $1.95, L3 $1.85, L4 $2.80). First full analysis (before batteries and ladder models): trap accuracy L1 0.806, L2 0.841, L3 0.983, L4 0.879; neutral 1.000 for all four; USD per episode L1 0.0105, L2 0.0135, L3 0.0116, L4 0.0160; L1 minus L3 on trap accuracy -0.177 [-0.231, -0.127], sign-flip p = 5e-5.
- Incident 2026-10-10 19:08: experiments/run_batteries_google.sh passed the task regex as `--tasks "-L(6|18)..."`; argparse read the leading dash as a new option and every battery invocation exited with a usage error before making a call (no spend). Fixed to `--tasks=...`, dry-run checked, relaunched 19:12.
- Guardrail re-probe 2026-10-10 19:14: anthropic/claude-haiku-5.5, openai/gpt-5-mini and deepseek/deepseek-v4-flash still return 404 "0 endpoints ... matching your guardrail restrictions". Plan B from EXPERIMENT_PLAN §7 applies: one-family Google capability ladder. Added to the paper as a stated limitation, not a footnote.
- Ladder smoke 2026-10-10 19:16: gemini-3.5-flash-lite returns MALFORMED_FUNCTION_CALL (empty message, no content) on 8 of 26 calls in one L18 episode, the same provider-side fault as 2.5-flash-lite with our 39-tool list; two of 18 actions were never executed after 4 retries each. It is dropped from the ladder (cost and action fidelity both unusable). 3.6-flash and 2.5-flash smoke-tested next.
- Audit shipped 2026-10-10 19:21: results/audit_sample.json, n = 40 wrong trap answers from the main grid (L1 11, L2 11, L3 8 = all of L3's, L4 10). Codes: stale_value 34, ambiguous_stale_or_boundary 3 (qty equals threshold), reveal_not_executed 2 (both L3: the agent skipped a scripted listing call, so the fresh value never entered the context), arithmetic_or_count 1. Coder: the agent, from the observation history in results/_audit_view_0_40.txt; not blind to layout.
- Action-fidelity sensitivity added to analyze.py (fidelity block): reveal-step execution rate L1 0.995, L2 1.000, L3 0.990, L4 0.990; trap accuracy restricted to questions whose thread steps were all executed: L1 0.811, L2 0.836, L3 0.983, L4 0.858 (vs 0.808 / 0.836 / 0.978 / 0.853 unrestricted, question-level). The layout gap is not an action-fidelity artefact.
- Ladder decision 2026-10-10 19:17 (smoke on inv-T3-L18-high-s0, L1 and L3): gemini-3.6-flash clean, $0.053 per L18 episode (about 5x 3.1-flash-lite), implicit cache share 0.50; gemini-2.5-flash clean, $0.016 to $0.019 per L18 episode (about 1.8x) with 480 to 825 thinking tokens per episode despite reasoning effort minimal; gemini-3.5-flash-lite dropped (malformed calls). Spend $11.21 with about $1.5 of batteries still to run, so about $9.5 is available under the $24 hard stop. Sized: rung A gemini-2.5-flash, L1/L3/L4 on the seed-0 half (72 tasks, 216 episodes, about $5.6); rung B gemini-3.6-flash, L1/L3 on the 36-task repeat-battery subset (72 episodes, about $2.7). Both subsets are balanced over domain, template, length and distractor. experiments/run_ladder_google.sh, queued behind the batteries.
- ElevenLabs re-check 2026-10-10 19:22: the key in .env still returns 401 invalid_api_key on a 3-character TTS call. Film narration remains blocked; the film script and silent build proceed so narration can be dropped in when a valid key exists.
- Added to analyze.py 2026-10-10 19:25: (a) cache hit rate by turn kind: on Google's implicit cache the no-tool question turns (tool_choice none) hit far less often than action turns (L1: 0.93 of action turns vs 0.51 of question turns), so the cost side must be read with that in mind; (b) hit-versus-miss trap accuracy within layout, unpaired (confounded by length and chain, flagged as such), stratified by (length, chain), and paired within question on the repeat battery (same question, same layout, served from cache in some runs and not in others). The paired version is the Google substitute for the Anthropic on/off control.
- [x] T1 StaleTrap DONE 2026-10-10 20:46: gemini-3.1-flash-lite 144 x 4 (576 ep); gemini-2.5-flash 72 x L1/L3/L4 (216 ep, $3.87); gemini-3.6-flash 36 x L1/L3 (72 ep, $2.44); 0 failures. External-trap accuracy under L1 / L3: 2.5 Flash 0.40 / 0.84, 3.1 Flash-Lite 0.655 / 0.96, 3.6 Flash 0.80 / 1.00; own-update traps and neutral steps at or near 1.00 everywhere. L1 minus L3 trap gap -0.273, -0.177, -0.111 (model-label permutation p = 0.035 all tasks, 0.092 on the common 36). L3 cheapest per correct episode at every cache-read multiplier on all three models.
- [x] Controls DONE 2026-10-10 19:35: repeat battery 36 tasks x L1 x 5 runs (trap outcome flips in 11.1% of cells, within-cell sd of question accuracy 0.017); phrasing battery 36 episodes (phrasing 2 minus 1 = -0.007 [-0.042, +0.032], p = 0.87); cache on/off NOT RUN (Anthropic blocked by the guardrail), replaced by the within-question hit-vs-miss comparison on the repeat battery (difference 0.000 over 11 questions with both outcomes). Battery spend $1.58.
- [x] T2 external arm DONE 2026-10-10 18:14: **BFCL v3 multi-turn** (official bfcl-eval 2026.3.23 harness through OpenRouter with a per-call message hook; experiments/t2_bfcl/FEASIBILITY.md). 25 base + 25 long-context tasks (even ids 0-48) x L1 / L3 (age-based observation masking: no schema oracle in BFCL) / L4 (persistent pointer note) on gemini-3.1-flash-lite. Result: a null. Accuracy base/long: L1 0.44/0.44, L3 0.44/0.48, L4 0.44/0.40; no layout moves more than 3 of 50 tasks; cached fraction 0.78-0.80 for all three (masking at turn boundaries re-warms on the next step); USD per correct task L1 $0.0210, L3 $0.0182, L4 $0.0219. Failures are state mismatches and 20-step loops, i.e. capability, not stale reads. T2 spend $1.96 (incl. $0.52 for the discarded non-persistent L4 v1, archived under results/raw/t2/L4v1-nonpersistent/).
- [x] T3 optional LongMemEval_S slice: NOT RUN (spend was $12.12 before the ladder and the ladder was the better use of the remaining budget; plan rule 'only if spend < $14' applied at the time the ladder was sized)
- [x] analyze.py -> results/analysis.json regenerates byte-identically (checked 2026-10-10 20:50); BH family size: 65 tests, 29 survive at q = 0.05 (threshold p <= 0.0207); hand audit n = 40 shipped (results/audit_sample.json)
- Headline: the accuracy cost of the cache-optimal layout is confined to external updates (own updates and neutral steps 100% under every layout); on Gemini 3.1 Flash-Lite L1 65.5% vs L3 96.0% on external traps (L1 minus L3 on all traps -0.177 [-0.231, -0.128], p < 1e-4); reordering does nothing (-0.036, p = 0.12); the note recovers 42% of the gap (79% on 2.5 Flash); L3 is cheapest per correct episode at every cache-read price on all three models because the history is rarely cached (history share 0.24 under L1 on 3.1 Flash-Lite, 0.006 on 3.6 Flash); the gap shrinks with generation (27, 18, 11 points) and does not close.
- Spend at CP3 close: $18.42 (tracker, 2026-10-10 20:46); hard stop $24 never reached.

## CP4 · Paper
- [x] CP4 DONE 2026-10-10 21:20: ICLR dual build compiles (tectonic, anonymous + named); pages 23 (10 main incl. statements, refs, 12 appendix); refs verified 71/76 arXiv ids via API + 5 web documents (paper/iclr/refs_verification.md); figures: teaser (HTML to headless Chrome) + 6 matplotlib (3 main, 3 appendix); every table generated by paper/iclr/gen_tables.py from results/analysis.json; verbatim prompts and one episode per layout in the appendix
- [x] Title: Cheap but Confused? The Accuracy Cost of Cache-Optimized Context Layouts in LLM Agents

## CP5 · Publish
- [x] Repo: https://github.com/Abraar237/cheap-but-confused (public, .gitignore excludes .env, Agent Skills/, reference/, templates/, discarded runs; README with reproduce commands and metered spend)
- [x] Pages: https://abraar237.github.io/cheap-but-confused/ (docs/index.html rendered by docs/gen_site.py from analysis.json; both PDFs; 3 GIFs; film)
- [x] Film: video/film.mp4 and docs/assets/film.mp4, 3 min 43 s (222.9 s), 1920x1080 at 60 fps, libx264 crf 20, narration normalised to -14.0 LUFS integrated / -2.2 dBTP; QA on the actual render (video/qa_film.py): contact sheet every 4 s (56 tiles), sync audit at 61 anchor phrases, transition audit at every boundary, motion audit (no static stretch over 8 s, no near-blank over 4 s). NARRATION CAVEAT: the ElevenLabs key in .env returns 401 on every call, so the track is a macOS placeholder voice; video/film_tts.py regenerates the Matilda narration and re-times every scene once a valid key is present.
- [x] GIFs: docs/assets/gifs/same-information-four-layouts.gif, cost-per-correct-task.gif, where-the-cache-reads-come-from.gif (clean flat-chart style, 110 frames each, numbers from analysis.json)

## CP6 · Self-review
- [x] REVIEW.md 2026-10-10: R1 rigor 5, R2 novelty 5, R3 clarity/impact 6, avg 5.33, calibrated P(accept) about 28% (band 31.6%, adjusted for ICLR 2026's 27% rate); ranked fixes (non-Google replication first); venue shortlist ICLR 2027 > ICML 2027 > agent/efficiency workshops now > ACL 2027 (review/venue_fit_output.txt)

## Spend log
| Date | Item | Amount | Running total |
|---|---|---|---|
| 2026-10-10 | Smoke test (6 models x 2 calls; 4 blocked) + guardrail probe (14 tiny calls) + Gemini caching diagnosis (24 calls) | $0.015 | $0.015 |
| 2026-10-10 | Pilot 1 (7 ep, 2.5-flash-lite), calibration 1 (7 ep, errors), Gemini model probes (20 calls), calibration 2 (3 ep), calibration 3 (14 ep) | $0.58 | $0.59 |
| 2026-10-10 | T1 main grid, gemini-3.1-flash-lite, 576 episodes (plus 177 torn-read failures and 55 discarded L4 v1 episodes, $0.56) | $8.47 | $9.06 |
| 2026-10-10 | T2 BFCL v3 multi-turn, 150 episodes incl. discarded L4 v1 | $1.96 | $11.02 (tracker: $10.54 after de-duplicating the smoke/diag row; tracker is authoritative) |
| 2026-10-10 | Guardrail re-probe (3 calls), ladder smoke tests (2.5-flash, 3.5-flash-lite, 3.6-flash; 6 episodes) | $0.20 | $10.96 (tracker) |
| 2026-10-10 | Repeat battery (144 ep) + phrasing battery (36 ep), gemini-3.1-flash-lite | $1.58 | $12.12 (tracker) |
| 2026-10-10 | Ladder rung A: gemini-2.5-flash, 214 episodes (+2 smoke) | $3.87 | $15.98 (tracker) |
| 2026-10-10 | Ladder rung B: gemini-3.6-flash, 70 episodes (+2 smoke) | $2.44 | $18.42 (tracker) |
