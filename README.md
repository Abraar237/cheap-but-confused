# Cheap but Confused? The accuracy cost of cache-optimized context layouts in LLM agents

Mohammed Abraar · Vizuara Research · October 2026

- **Website:** https://abraar237.github.io/cheap-but-confused/
- **Paper (AAAI-27 workshop format, Deployable AI Workshop):** [`docs/paper_aaai_preprint.pdf`](docs/paper_aaai_preprint.pdf) (named) · [`docs/paper_aaai_submission.pdf`](docs/paper_aaai_submission.pdf) (anonymous). Sources in `paper/aaai/`.
- **Film:** on the website (`docs/assets/film.mp4`)

Prompt caching rewards one context layout: keep the system prompt and tools first, append every
observation at the end, never reorder, never delete. Nothing is ever removed, so when a value
changes the old value stays in the context next to the new one. We held the information in an
agent's context fixed, changed only the layout, and measured accuracy, provider-reported cached
tokens and the billed cost.

## Headline numbers (Gemini 3.1 Flash-Lite, 144 episodes per layout, from `results/analysis.json`)

| | L1 append-only | L2 reordered | L3 pruned | L4 hybrid note |
|---|---|---|---|---|
| own-update traps (n=160) | 100% | 100% | 100% | 100% |
| external-update traps (n=200) | **65.5%** | 70.5% | **96.0%** | 73.5% |
| neutral steps (n=360) | 100% | 100% | 100% | 100% |
| cents per episode (billed) | 1.05 | 1.35 | 1.16 | 1.60 |
| cents per correct episode | 1.52 | 1.85 | **1.22** | 2.07 |
| cached share of prompt tokens | 0.71 | 0.62 | 0.68 | 0.71 |

1. **The cost of the cache-optimal layout is confined to external updates.** When the agent's own tool reply states the current value, nothing goes wrong. When the world changes behind the agent and the new value arrives as one row of a listing, the append-only agent answers from its own stale write about one time in three (L1 minus L3 on all trap steps: -0.177 [-0.231, -0.127], sign-flip p < 0.0001). 34 of 40 audited wrong answers are a superseded value read back.
2. **Reordering does nothing; a pointer-only note recovers a quarter of the gap** and costs 51% more per episode because every turn's note must stay in the history.
3. **Pruning is cheaper per correct episode at every cache-read price** from free to full, because on Google's best-effort cache the history is rarely served from cache under any layout (history-only cached share 0.24 under L1).
4. **Across three Gemini generations the gap shrinks and does not close.** External-trap accuracy under the append-only layout is 40% (2.5 Flash), 66% (3.1 Flash-Lite) and 80% (3.6 Flash) against 84%, 96% and 100% under pruning; pruning is the cheapest layout per correct episode on every model.

## Layout of the repository

```
corpus/            frozen StaleTrap testbed: tasks.json, tools.json, FROZEN.json (SHA-256 manifest)
experiments/       env.py (executor), prompts.py, build_corpus.py, layouts.py (L1-L4 serialisers),
                   runner.py, cost_tracker.py (locked, hard stop), analyze.py -> results/analysis.json,
                   audit_view.py, run_*.sh, t2_bfcl/ (BFCL v3 multi-turn arm)
results/raw/       every scored episode with per-call provider usage and billed cost (JSONL)
results/           analysis.json, audit_sample.json, audit_candidates.json, spend.json
paper/aaai/        AAAI-27 dual build with appendix, gen_tables.py, gen_appendix_assets.py, references.bib
figures/           build_figures.py, build_teaser.py, build_gifs.py, style.py
video/             script.md, film_tts.py (ElevenLabs Matilda with-timestamps, -14 LUFS), build_film.py
docs/              GitHub Pages site (gen_site.py renders index.html from analysis.json), PDFs, GIFs, film
lit_review/        lit review, verified reference CSVs, pre-emption sweep
EXPERIMENT_PLAN.md frozen plan and amendments; MILESTONES.md: pre-registration, incidents, spend log
```

## Reproduce

```bash
python3 experiments/analyze.py              # rebuilds results/analysis.json byte-identically from results/raw
python3 experiments/analyze.py --audit-export 40
python3 figures/build_figures.py && python3 figures/build_teaser.py && python3 figures/build_gifs.py
python3 paper/aaai/gen_tables.py && python3 paper/aaai/gen_appendix_assets.py
cd paper/aaai && for f in paper_aaai_submission paper_aaai_preprint; do pdflatex $f; bibtex $f; pdflatex $f; pdflatex $f; done   # AAAI kit needs pdfLaTeX
# AAAI-27 build needs pdfLaTeX (the aaai2027 style refuses XeTeX), e.g. TinyTeX:
cd paper/aaai && for f in paper_aaai_submission paper_aaai_preprint; do pdflatex $f && bibtex $f && pdflatex $f && pdflatex $f; done
python3 docs/gen_site.py
# re-run episodes (OPENROUTER_API_KEY in .env; the tracker refuses calls past the hard stop):
python3 experiments/runner.py --model google/gemini-3.1-flash-lite --layouts L1,L2,L3,L4 --workers 4
```

## Metered spend

Every call went through OpenRouter and was logged by `experiments/cost_tracker.py` (fcntl lock, hard stop at
USD 24). Total for the whole study, including pilots, calibration, smoke tests, discarded runs and the
external arm: **USD 18.42** (`results/spend.json`; the per-item log is in `MILESTONES.md`).

## Pre-registration

Five directional predictions were written into `MILESTONES.md` on 2026-10-10 before any model call and are
scored in the paper (Section 4.3): D1 confirmed in two parts of three, D2 half confirmed, D3 not supported,
D4 confirmed in direction with weak interaction evidence, D5 reversed.

## Licence

Code and testbed: MIT. Paper text and figures: CC BY 4.0.
