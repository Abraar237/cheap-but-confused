# INSTRUCTIONS: Cheap but Confused?
## The accuracy cost of cache-optimized context layouts in LLM agents

You are a Claude Code agent running a complete research project in this folder, start to
finish, without waiting for the user between phases. Your user is Mohammed Abraar (author name
on the paper; email abraar@vizz.vizuara.ai; GitHub `Abraar237`, already logged in via `gh`).
This file is your complete brief. Read it fully before doing anything. Predecessor projects
called this file `MISSION.md`; it plays the same role.

Target: a **workshop-level paper** (8 pages + appendix, ICLR style) that is unique, honest and
reproducible, plus the public repo, the project website, the explainer film and three GIFs.
Hard budget: **$30 of API spend** (hard stop $24, see §4).

---

## 0. THE CHECKPOINT PROTOCOL

The user has authorised running CP1 through CP6 **without stopping** (2026-10-10): "continue
until he completes all the research ... paper, video, github website etc." Record each CP in
`MILESTONES.md` as it completes and report ONCE at the end with links, headline numbers, spend
and the reviewer score. Stop early only for a hard blocker:

- a pre-emption discovered at CP1 (a paper that already owns the exact measurement in §1.4),
- the cost tracker's hard stop, an exhausted key, or a provider that refuses all calls,
- a result that makes the paper impossible to write honestly (then write the null and say so).

| CP | Gate | Done when |
|---|---|---|
| CP1 | Lit review + pre-emption | `lit_review/LIT_REVIEW.md` with verdict, novelty table, 40+ verified refs |
| CP2 | Experiment plan frozen | `EXPERIMENT_PLAN.md` + `site/plan.html`; budget table; pilot cost measured; directions dated in `MILESTONES.md` |
| CP3 | Experiments + analysis | frozen testbed, all runs, `experiments/analyze.py` -> `results/analysis.json` |
| CP4 | Paper | ICLR dual build compiles, figures, 40+ verified citations, appendix with verbatim prompts |
| CP5 | Published | public repo, GitHub Pages site, film on the site, 3 GIFs |
| CP6 | Self-review | `REVIEW.md` from `a-star-reviewer` with scores, P(accept), ranked fixes -> REPORT TO USER |

---

## 1. THE PROBLEM

### 1.1 Why this matters

Every major provider now discounts input tokens that match a previously seen **prefix**
(Anthropic `cache_control`, OpenAI automatic and explicit prefix caching, Gemini implicit
caching, DeepSeek context caching, vLLM and SGLang prefix caching; OpenRouter passes all of
them through and reports `cached_tokens`). Cache reads cost 0.1x the input price on Anthropic
and DeepSeek, 0.25x on Gemini and most OpenAI models. For an agent that makes 50 tool calls
with a 100:1 input-to-output ratio, the cache hit rate is the dominant cost term, and the most
read context-engineering guide of 2025 (Manus, July 2025) calls KV-cache hit rate "the single
most important metric of a production agent".

Caching rewards exactly one context layout: a **byte-stable prefix that is only ever appended
to**. So agent builders now (a) keep system prompt and tool definitions first and frozen,
(b) append every observation in arrival order and never reorder, (c) keep stale and
superseded tool results in place instead of deleting them, (d) mask tools instead of removing
them, and (e) avoid compaction because it rewrites the prefix. Each of these collides with a
known positional effect: lost-in-the-middle and primacy/recency (2307.03172, 2406.16008),
relevance-ordering benefits in RAG (2410.05983, 2401.14887), the question-last and
instruction-repetition advantages (2308.12097, 2403.05004), distractor and stale-information
damage in long contexts (Context Rot 2025, 2610.05281, 2606.00408).

**Nobody has measured what the cache-optimal layout costs in accuracy, with the information
content held fixed, against the real cached-token discount.** The systems literature proves
that non-prefix KV reuse degrades outputs and engineers around it (CacheBlend, EPIC, KVLink,
Leyline). The context-management literature proves pruning changes accuracy and token cost
but never accounts for cache hits (Complexity Trap 2508.21433, Less Context Better Agents
2606.10209). The one agent-caching evaluation measures cost and TTFT and never accuracy
("Don't Break the Cache" 2601.06007). The one ordering-under-caching paper is single-turn RAG
on vLLM with no pricing (CacheWeaver 2606.19667). Blogs prescribe the layout; none measures
it. The full sweep is in `lit_review/00_preemption_sweep_2026-10-10.md` (verdict:
ALIVE-BUT-CROWDED; extend it at CP1, re-check arXiv for anything posted after 2026-10-10).

Caching itself is output-neutral: the same bytes produce the same distribution whether or not
the prefix was served from cache. **The paper is about the layout discipline that caching
imposes, not about caching.** Say this in the abstract and verify it with the control in §1.3.

### 1.2 Core questions

1. Holding information content fixed, does the cache-optimal append-only layout (L1) lose
   task accuracy relative to a relevance-reordered layout (L2) and to a stable-prefix hybrid
   that appends a recitation block (L4)?
2. Does keeping superseded tool results in context (what L1 must do) cause **stale-value
   errors**, and does pruning them (L3, which changes content and breaks the prefix) remove
   those errors?
3. What is the **cost per correct task** of each layout under real, provider-reported cache
   hits and billed USD, and at what cache-read price does the cheapest layout per call stop
   being the cheapest layout per correct answer?
4. Does the answer depend on the model family and on trajectory length?

### 1.3 Design (refine and freeze at CP2; keep it API-only, cheap, paired)

**Layouts** (the treatment; content identical across L1, L2, L4; L3 is the content-changing
comparator):

| Id | Layout | Prefix stable? | Content |
|---|---|---|---|
| L1 | Cache-optimal: system + tools first, every turn and tool result verbatim in arrival order, newest observation and user message last, tools masked via allowed-tool lists rather than removed, no summaries | yes | full |
| L2 | Relevance-reordered: same blocks, but prior observations re-sorted each turn by relevance to the current sub-goal (most relevant last, directly before the question) | no (rewritten every turn) | full |
| L3 | Pruned: superseded tool results replaced by a one-line placeholder ("[result superseded by call 7]"), stale ones dropped; no LLM summary unless the plan adds it as L3b | no | reduced |
| L4 | Hybrid: L1 untouched, plus a short appended block each turn that restates the goal, the current state, and which earlier observations are current vs superseded (Manus "recitation", R&R 2403.05004) | yes (append-only) | full + ~150 tokens |

**Tasks** (two arms; a third if budget remains):

- **T1 StaleTrap (primary, self-built, frozen before any call).** A deterministic stateful
  tool environment (inventory / calendar / ticketing style, JSON tools, local mock executor)
  with scripted multi-step tasks of controllable length (6, 12, 18 tool calls) in which
  earlier tool results become **superseded** by later updates, and the final answer depends on
  the current value. Every step is annotated as a *stale-trap step* (a superseded value is
  present in context and would give the wrong answer) or a *neutral step*. Add a controllable
  volume of **distractor** observations (irrelevant but plausible tool outputs). Ground truth
  is checkable programmatically (exact match on canonicalised final state and answer).
  Target: 90-120 tasks, 3 lengths, 2 distractor levels, 3+ task templates per domain, 2
  paraphrases of each user goal (single-anything dies in review).
- **T2 External arm.** BFCL v3 multi-turn (`long-context` and `base` splits, state-based
  scoring via the `bfcl-eval` package) on a 50-100 task subset. If the harness cannot be
  made to run cleanly within half a day, fall back to tau2-bench retail (50 tasks, small fixed
  user simulator, pass^1 and pass^2). Record the choice and the reason in `MILESTONES.md`.
- **T3 Optional single-call positional arm.** LongMemEval_S, 100 questions over-sampling the
  knowledge-update and abstention categories; layouts: chronological vs relevance-sorted vs
  pruned top-k vs chronological + question restated at the end. Only if spend < $14 after T1
  and T2.

**Models** (3 families via OpenRouter, all with caching; re-fetch prices at CP2 from
`https://openrouter.ai/api/v1/models`, which lists `pricing.input_cache_read`):

| Family | Candidate id (2026-10-10 prices, per 1M tokens) | Cache mechanics |
|---|---|---|
| Anthropic | `anthropic/claude-haiku-5.5` (in $0.10, out $0.50, cache read $0.01, write $0.125) | explicit `cache_control` breakpoints; the only family where caching can be switched OFF for the control |
| OpenAI | `openai/gpt-5-mini` (in $0.25, cache read $0.025) or `openai/gpt-5.6-luna` (in $0.20, cache read $0.02, explicit breakpoints) | automatic >= 1,024-token prefix |
| Google | `google/gemini-3.1-flash-lite` (in $0.25, cache read $0.025) or `google/gemini-2.5-flash-lite` (in $0.10, cache read $0.01) | implicit, >= 2,048-4,096-token prefix |
| Optional 4th | `deepseek/deepseek-v4-flash` or an open-weight arm on Modal (vLLM, Qwen3/Gemma-4, prefix caching on, hits from `/metrics`) | for a mechanism check and a no-API-pricing replication |

Build the shared prefix (system + tool schemas) to **>= 4,500 tokens** so every provider's
minimum cacheable length is exceeded, and verify on the pilot that `cached_tokens > 0` from
turn 2 onwards in L1.

**Controls and batteries:**
- **Cache on/off at fixed layout** (Anthropic only): L1 with and without `cache_control` on
  30 tasks; accuracy difference is the noise floor that proves caching itself is neutral.
- **Repeat-call noise floor:** 30 tasks x 5 identical L1 runs on one model (temperature 0
  is not deterministic on these routes; the voice-provenance project saw 83% of cells vary).
- **Order-only vs content-only decomposition:** L1 vs L2 isolates order; L1 vs L3 isolates
  content; L4 vs L1 isolates the recitation block.
- **Length dose-response:** 6 / 12 / 18 calls, and distractor low / high.

**Measurement per call** (log every field raw, derive later): `prompt_tokens`,
`usage.prompt_tokens_details.cached_tokens`, `cache_write_tokens`, `completion_tokens`,
`reasoning_tokens`, `usage.cost` (OpenRouter's billed USD; this is ground truth, never
estimate), provider id from the response, latency, `finish_reason`. Run each episode's turns
sequentially within one process and within 5 minutes so TTL never expires; pass a
`session_id` per episode for sticky routing. Derive: cache-read fraction per episode, USD per
episode, **USD per correct task**, and the accuracy-vs-cost frontier per model.

**Statistics** (one `analyze.py`, seeded, byte-identical on re-run): unit = task; paired
within-task contrasts (L1-L2, L1-L3, L4-L1, L4-L3); sign-flip permutation tests clustered by
task template (20k); task-cluster bootstrap 95% CIs (10k); layout x length and layout x family
interactions tested directly by label permutation; Benjamini-Hochberg over the full family
from day one, bold survivors only; stale-trap vs neutral step accuracy reported separately;
hand audit of n >= 30 wrong answers coded as stale-value / distractor / other, shipped as
`results/audit_sample.json`.

### 1.4 Pre-registered directions (copy into `MILESTONES.md` with today's date BEFORE any data)

- **D1 (stale-retention cost).** L1 accuracy is below L3 on stale-trap steps, the gap grows
  with trajectory length, and there is no comparable gap on neutral steps.
- **D2 (order-only effect is small, cost is large).** L2 does not significantly beat L1
  (consistent with 2505.15561, where reordering was no better than shuffling), while its
  cache-read fraction falls below 20% and its USD per task rises by >= 3x on 0.1x-read
  pricing. L2 is dominated on the frontier.
- **D3 (the hybrid dominates).** L4 recovers >= 50% of the L1-to-L3 accuracy gap while
  keeping >= 80% of L1's cache-read fraction, and sits on or inside the frontier for every
  model.
- **D4 (model dependence).** The L1-vs-L3 gap shrinks with model capability; the confusion
  cost is largest for the cheapest models, which is where caching saves the least absolute
  money.
- **D5 (price threshold).** Per correct task, L3 is cheapest when cache reads are expensive
  and L1/L4 become cheapest below a cache-read price threshold; report the threshold per
  model and compare with the ~$0.55/MTok break-even reported by Bouchard (2026) and the
  ~10-turn break-even of 2603.04814.

If a direction fails or reverses, report it plainly in the abstract. The predecessors'
best sections were honest reversals.

### 1.5 Pre-emption frontier (verified 2026-10-10; re-verify at CP1 and delineate in the paper)

| Nearest work | What it does | What it does NOT do (ours) |
|---|---|---|
| Don't Break the Cache (2601.06007) | Caching strategies on 3 providers, 500+ sessions, cost and TTFT | no accuracy, no layout manipulation |
| TokenPilot (2606.17016) | Names the "text sparsity vs cache continuity" trade-off; a method | no controlled factorial; order and pruning confounded |
| Cache-Aware Prompt Compression (2607.15516) | Anthropic telemetry; compression breaks caches; 50 tau-bench tasks | compression only; no ordering or stale arm; one provider |
| CacheWeaver (2606.19667) | Reorders retrieved evidence for prefix reuse in vLLM | single-turn RAG; no agents, stale observations or pricing |
| Do RAG Systems Really Suffer From Positional Bias? (2505.15561) | Reordering no better than shuffling in RAG | RAG not agents; no history, no caching; it is our D2 null |
| Less Context Better Agents (2606.10209), Complexity Trap (2508.21433), Masking Stale Observations (2606.00408) | Pruning vs full history with accuracy | no cache accounting; no order-only arm |
| Leyline / Irminsul / Request Order Matters (2606.01065, 2605.05696, 2610.05833) | Serving-side fixes for shifted-position reuse | do not evaluate the API-level discipline practitioners follow |
| Manus (Jul 2025), Anthropic (Sep 2025), Bouchard (Aug 2026) | Prescribe the layouts; one app-level cost study | no controlled accuracy measurement; no order manipulation |

**Ours alone:** content-fixed layout manipulation (order-only vs content-only vs recitation) in
a multi-turn tool-using agent, scored against provider-reported cached tokens and billed USD,
with a stale-trap step annotation that names the mechanism.

### 1.6 Threats to pre-empt in v1

Best-effort caching (Gemini, DeepSeek) can miss silently: report the observed hit
distribution per layout, not the nominal one. Anthropic's 4-breakpoint limit and 20-block
lookback can break L1 if breakpoints are placed badly: put one after the tool block, one on
the system block, one on the latest tool result, and log every miss. User-simulator noise in
tau2: fixed cheap simulator, pass^2. Temperature-0 nondeterminism: the repeat battery.
"Layout is not caching": the cache on/off control. Provider price changes: quote the price
table with the retrieval date and compute the frontier from logged `usage.cost`.

---

## 2. THE PIPELINE (copy the predecessors; it has worked five times)

Predecessor papers are in `reference/` (script-bias, voice-judge, ocr-injection,
schema-drift). Templates copied from the most recent project are in `templates/` (runner,
cost tracker, analysis script, figure style, LaTeX dual build, site, film builder, TTS, plan
page, lit review, reference verification, review). **Read `reference/` and `templates/`
first.** The schema-drift paper is the closest methodological sibling (frozen tool testbed,
mock executor, paired stats).

| Stage | Replicate | Skill (in `Agent Skills/`) |
|---|---|---|
| 1. Lit review | Start from `lit_review/00_preemption_sweep_2026-10-10.md`; 3-4 angle agents + a recency sweep for anything after 2026-10-10; verified CSV + `LIT_REVIEW.md` with the novelty-delineation table written BEFORE results | `prior-work-check` |
| 2. Plan | `EXPERIMENT_PLAN.md` + `site/plan.html`; budget table from a measured 10-task pilot; pre-registered directions dated in `MILESTONES.md` | `paper-topic-selection`, `research-pipeline` |
| 3. Experiments | Frozen testbed with SHA-256 manifest; one `runner.py` (one episode per process, turns sequential, randomised task order, resume-safe JSONL keyed by model x task x layout x rep); `cost_tracker.py` with hard stop; one `analyze.py` -> `results/analysis.json`; EVERY paper number traces to it | — |
| 4. Paper | ICLR-format LaTeX from day one (`templates/iclr_latex_template/`); anonymous + named dual build from one body; 40+ arXiv-verified refs (`templates/refs_verification_example.md`); HTML->headless-Chrome teaser figure; results tables with CIs, bold BH survivors; verbatim prompts and the layout serialisations in the appendix | `research-paper-writing`, `paper-quality`, `paper-figures`, `humanizer`, `no-ai-slop` |
| 5. Publish | Public repo under `Abraar237` (`.gitignore` BEFORE first add; `.env` never committed; `Agent Skills/`, `reference/`, `templates/` excluded); GitHub Pages from `docs/`; film (ElevenLabs Matilda `XrExE9yKIg1WjnnlVkGX` + Remotion or the PIL frame builder in `templates/build_film_example.py`, script written first, -14 LUFS, CONTINUOUS animated motion, numbers from `analysis.json`); 3 GIFs in the CLEAN FLAT CHART style (white card, flat bars, monospace numerals, replay pill, Helvetica; NOT hand-drawn rough.js, the user rejected that look) | `research-website`, `paper-site`, `paper-to-video`, `research-film`, `social-media-gif` |
| 6. Review | `a-star-reviewer` with its calibration data on the final PDF; report scores, P(accept), effort-ranked fixes; then `venue-fit` for a workshop shortlist | `a-star-reviewer`, `venue-fit`, `format-linter` |

Install the skills once at start: `cp -R "Agent Skills/3-research-paper-writing/skills/"* ~/.claude/skills/`
(and the same for bundles 1, 2 and 4). Most are already in `~/.claude/skills/`.

---

## 3. METHOD LESSONS FROM THE PREDECESSORS (do not relearn the hard way)

1. **One episode per process, turns sequential, temperature 0, randomised task order,
   resume-safe JSONL.** Here the episode is the unit; never interleave episodes' turns
   across models, or the cache state becomes uninterpretable.
2. **Pre-register in writing before data; report reversals plainly.**
3. **Single-anything dies in review.** Multiple task templates per domain, two paraphrases per
   goal, three lengths, three model families, a repeat-call noise floor from day one.
4. **Test interactions directly.** A difference in significance is not a significant
   difference.
5. **BH over the full family from day one; bold only survivors.**
6. **Hand-audit n >= 30 wrong answers** and ship the audited sample. Never claim an audit you
   did not perform.
7. **Verify every citation** via arxiv.org/abs (or the arXiv API; Semantic Scholar batch when
   arXiv rate-limits). One fake reference kills the paper.
8. **Cost tracker with hard stop; log `usage.cost` exactly.** Reasoning tokens bill as output:
   set `reasoning: {effort: "minimal"}` (or `low` where minimal is rejected) and give
   `max_tokens` headroom, or you get empty replies (the voice project lost $0.18 to this).
9. **Corrected-numbers discipline:** when a number changes, update paper, site, film and GIFs
   in ONE pass.
10. **Figures:** Times in paper figures, white backgrounds, house palette (slate #155e8c, hot
    #b3006b, shelf #c0641a, good #1c7a55), eyebrow titles, direct labels, the finding
    annotated on the figure; `templates/figure_style.py`.
11. **Pre-empt the reviewer in v1:** noise floors, interaction tests, per-family tables, BH,
    verbatim prompts and the exact serialised context of one episode per layout in the
    appendix, honest Limitations.
12. **Lessons from the two newest reviews (psb1 v5, voice provenance):** explain the headline
    mechanism, do not just observe it (the stale-trap annotation and the audit do this);
    never let a comparison be confounded by information content (L1 vs L2 vs L4 are
    content-matched by construction; say so); give the lever's cost on the cells where it was
    not needed (L4's extra tokens on neutral steps); a result on one family is a result on one
    family, so run all three families on the primary arm.
13. **Pilot first** (`--limit 10`), read the raw transcripts, confirm `cached_tokens > 0` in
    L1 from turn 2, then scale.

---

## 4. BUDGET (hard rules)

- **Cap $30. Hard stop $24 in `cost_tracker.py`.** The OpenRouter key is shared with the
  sibling project (`../indic search gap research/`) and held $49.72 on 2026-10-10, so the two
  projects' hard stops must sum to less than that. If the user tops up, raise to $25.
- Expected (confirm with the pilot, then write the table into `EXPERIMENT_PLAN.md`):
  T1 full factorial (~100 tasks x 4 layouts x 3 models, ~80k input tokens per episode, L1/L4
  mostly cached) ~$8-12; T2 external arm on 2 models ~$4-6; controls and batteries ~$2; pilots
  and re-runs ~$2. Modal arm, if run, ~1-2 GPU-hours on A10G/L4 (~$2-3).
- Report spend at every CP in `MILESTONES.md`. If a planned arm would break the cap, cut tasks
  per cell and say so in the paper; never silently exceed.

## 5. KEYS AND ACCOUNTS (`.env` in this folder; NEVER commit, never print values)

- `OPENROUTER_API_KEY`: ALL experiment calls. Check remaining credit before big runs with
  `GET https://openrouter.ai/api/v1/auth/key` (returns `limit_remaining`; never print the key).
  Usage accounting is always included in responses; `usage.cost` is the billed USD.
- `token-id` / `token-secret`: Modal (profile `thesreedath`), optional open-weight arm only.
  `python3 -m modal profile current` should print `thesreedath`.
- `ELEVENLABS_API_KEY`: film narration only (Matilda `XrExE9yKIg1WjnnlVkGX`). TTS-scoped:
  do NOT call `voices_read` or `user_read` (401); call text-to-speech directly
  (`templates/film_tts_example.py`).
- GitHub: `gh` CLI authenticated as `Abraar237`. Create the repo public at CP5.
- No Gemini direct key is provided; every model goes through OpenRouter.

## 6. FOLDER LAYOUT

```
cache layout cost research/
  INSTRUCTIONS.md     <- this file (the brief)
  CLAUDE.md           <- pointer to this file for new sessions
  MILESTONES.md       <- checkpoint tracker; pre-registered directions go here first
  EXPERIMENT_PLAN.md  <- written and frozen at CP2
  REVIEW.md           <- written at CP6
  .env  .env.example  .gitignore
  Agent Skills/       <- the 4 skill bundles (gifs, video, writing, review)
  reference/          <- four predecessor papers; read first
  templates/          <- copied working code from the newest predecessor; adapt, do not import
  lit_review/         <- 00_preemption_sweep_2026-10-10.md (seed), angle files, lit_review.csv, LIT_REVIEW.md
  corpus/             <- the frozen StaleTrap testbed: tools.json, tasks.json, manifest with SHA-256
  experiments/        <- env.py (mock executor), layouts.py (the 4 serialisers), runner.py, cost_tracker.py, analyze.py, prompts.py
  results/            <- raw/<model>_<layout>.jsonl, spend.json, analysis.json, audit_sample.json
  paper/iclr/         <- dual build; figures/ <- build_figures.py, build_gifs.py, fig1_teaser.html
  site/plan.html      <- CP2 plan page;   docs/ <- GitHub Pages site, both PDFs, film, GIFs
  video/              <- tts.py, build_film.py, words.json, film_final.mp4
```

## 7. FIRST ACTIONS WHEN YOU (the new session) START

1. Read this file fully, then `lit_review/00_preemption_sweep_2026-10-10.md`, then the four
   PDFs in `reference/` (method and honest-reporting register), then skim `templates/`.
2. Install the skills (see §2). Confirm `tectonic`, `ffmpeg`, `node` (Remotion), `gh auth
   status`, `python3 -m modal profile current`.
3. Sanity-check the key: one tiny OpenRouter call per planned model with a >= 4,500-token
   prefix sent twice; confirm `usage.cost` and `cached_tokens` appear on the second call.
   Log the cost. Record remaining credit in `MILESTONES.md`.
4. Write the pre-registered directions D1-D5 into `MILESTONES.md` with today's date.
5. CP1: extend the sweep (recency check for anything after 2026-10-10 on arXiv: "prompt
   caching accuracy", "append-only context agents", "KV cache hit rate task success",
   "context layout agents"), build `lit_review.csv` with 40+ verified ids, write
   `LIT_REVIEW.md` with the novelty table. If a paper now owns §1.4 exactly, STOP and report.
6. CP2 onward per §0. Do not stop between checkpoints. Report once at the end.

## 8. DEFINITION OF DONE (all of these, then report)

- [ ] `results/analysis.json` regenerates byte-identically; every paper number traces to it
- [ ] Paper: anonymous + named PDFs, 8 pages main + appendix, 40+ verified refs, teaser figure,
      frontier figure (accuracy vs USD per task, per model, layouts as points), stale-trap
      figure, dose-response figure, BH table, Limitations, Ethics/Reproducibility statements
- [ ] Repo public under `Abraar237`, README with reproduce commands and metered spend
- [ ] GitHub Pages site with story-driven sections, both PDFs, film embed, 3 GIFs
- [ ] Film 2-4 min, 1080p60, Matilda narration, -14 LUFS, continuous motion, QA contact sheet
- [ ] `REVIEW.md` with three reviewer scores, calibrated P(accept), ranked fixes, and a
      workshop shortlist from `venue-fit`
- [ ] `MILESTONES.md` spend log complete; final spend < $24
