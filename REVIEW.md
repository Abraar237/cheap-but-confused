# Simulated A* review: "Cheap but Confused? The accuracy cost of cache-optimized context layouts in LLM agents"

Target venue: **ICLR** (ICLR 2026 style file). Paper type: **analysis / measurement** with a
content-fixed factorial design on a self-built testbed. Judged on whether the evidence rules out
alternatives and whether the result changes a practice.

Reviewed build: `paper/iclr/paper_iclr_submission.pdf` (23 pages: 10 main including the
reproducibility, ethics and LLM-use statements, references, 12 appendix pages; 3 main-text figures
plus 3 in the appendix, 2 main-text tables plus 11 in the appendix, 76 references of which 71 are
arXiv-id verified and 5 are web documents), cross-checked against `results/analysis.json`, which
regenerates byte-identically from `results/raw/`.

> Estimated scores from a simulated review, not real reviews. Borderline outcomes at A* venues are
> noisy (about 50% disagreement on borderline papers in the NeurIPS consistency experiments). Treat
> the acceptance number as a base rate, not a promise.

## Scorecard

| Reviewer | Emphasis | Score (1 to 10) | Confidence |
|---|---|---|---|
| R1 | Rigor | **5** | 4/5 |
| R2 | Novelty | **5** | 4/5 |
| R3 | Clarity / impact | **6** | 4/5 |
| **Average** | | **5.33** | |

**Calibrated acceptance estimate: about 28%.** The 5.0 to 5.5 average band was accepted 31.6% of the
time across 5,352 real ICLR submissions in `Agent Skills/4-research-paper-review/data/review_calibration.json`.
ICLR 2026's overall rate was 27.0% against the 31% pooled historical rate, so the band estimate is
adjusted one step down to about 28%. Half a point more (a second provider family) moves the base rate
to 48.5%; one point more moves it to 78%.

---

## The claim in one sentence

Holding an agent's context information fixed and changing only its layout, the append-only layout that
prompt caching rewards loses about a third of its answers on questions whose answer changed behind the
agent and arrived inside a listing, while redacting the stale value removes the loss and is cheaper per
correct answer at every cache-read price on the three Gemini models tested.

A reviewer can repeat this from the abstract. Good.

## What the claim rests on

1. That the four layouts carry the same information (L1, L2, L4) or strictly less (L3). Established by
   construction; the serialisations are printed in Appendix C.
2. That the stale annotation is correct, so trap steps really do contain a superseded value. Established
   by the executor's schema-level supersession and a 360-of-360 check that stale values differ from answers.
3. That the layout effect is not an effect of the agent calling tools differently. Checked: reveal
   steps execute 99 to 100 percent of the time under every layout; restricting to fully executed
   threads moves nothing by more than half a point (Table 7).
4. That cache hits do not change outputs. Only weakly established: the on/off control did not run, and
   the paired substitute rests on 11 questions.
5. That the Google cost numbers generalise. Not established, and the paper says so.

## Attacking the claim four ways

**Confound.** The strongest alternative explanation for the L1-to-L3 gap is that L3's prompts are
shorter and cleaner, so the model is simply better at a shorter context, not better because the stale
value is gone. The paper's answer is the neutral-step and own-update results: both are at 100 percent
under L1, so the longer, uncut context does not hurt when nothing in it competes. That is a real
control and it is reported at exactly ceiling, which is the strong form. A second alternative is that
the listing-row reveal is a harder read than a dedicated reply in any layout; the data agree (external
traps are the only ones that fail), and the paper's claim is already restricted to that case. The
confound that remains is thinking tokens on 2.5 Flash, which differ by layout (639 against 790) and are
not controlled.

**Generality.** One provider family, three models, one of them on 36 tasks; one synthetic testbed; an
external arm (BFCL v3) that showed nothing. The paper states all of this plainly. A reviewer will
still write "one vendor" in the first line of weaknesses, and will be right.

**Direction of inference.** The design is interventional (same episode, four layouts, paired within
task), so the causal reading of the layout effect is sound. The cost claim is correlational in one
respect: the counterfactual repricing assumes the cache behaviour is unchanged under a different price,
which is true by construction on this provider but would not be if a provider offered explicit
breakpoints that the layouts could exploit differently.

**Consequence.** If true, two practices change: (a) a pruner that overwrites superseded values is
worth its cache cost on these models, and (b) the "150-token recitation note" fix that practitioners
reach for is far from free, because it must persist and grows the history quadratically. Both are
concrete. The second is the more surprising and the paper under-sells it.

## Claims against evidence, line by line

| Claim (abstract / intro) | Evidence | Status |
|---|---|---|
| Own-update traps and neutral steps perfect under every layout | Table 3 and Figure 2: 1.00 on all 160 own traps and 360 neutral steps (3.1 Flash-Lite); one miss each on 2.5 Flash (own, L1) and 3.6 Flash (neutral, L3) | supported; "perfect" should read "at or near 1.00" in the abstract for the ladder models |
| External-trap accuracy 65.5 / 96.0 / 70.5 / 73.5 | Table 6, Figure 2 | supported |
| 34 of 40 audited errors are a superseded value read back | Appendix G, `results/audit_sample.json` | supported; coder not blind |
| Gap as large at six calls as at thirty | Table 5: -0.22 and -0.22; slope p = 0.85 | supported |
| L1 cheapest per episode, L3 cheapest per correct episode, at every read price | Table 3, Table 9, Figure 6 | supported |
| History rarely served from cache | history cached share 0.24 (L1) and 0.15 (L3) on 3.1 Flash-Lite; 0.006 and 0.000 on 3.6 Flash | supported |
| Gap shrinks 27, 18, 11 across generations | Table 3 and the family interaction: p = 0.035 all tasks, 0.092 common tasks | supported in direction; interaction evidence weak, and the paper says so |
| "Caching does not change the answers" | 11 paired questions, difference 0.000 | weakly supported; the heading overstates it |

## Strengths

- A clean, content-fixed manipulation that nobody had run: the same transcript under four layouts,
  paired within task, with a stale annotation known by construction (Section 3). The pre-emption
  table (Appendix A) convincingly separates it from the compression and KV-cache literatures.
- Provider-billed cost rather than price-sheet arithmetic, and the sanity check that the list-price
  model reproduces the bill to the fourth decimal (Section 4).
- The own-versus-external split is the paper's best result: it turns "stale context hurts" into
  "stale context hurts exactly when the fresh value arrives as a listing row", which is actionable.
- Two sensitivity checks that a sceptical reviewer would have demanded (action fidelity, hit-versus-miss)
  are already in the paper, and the second is reported with its confound named.
- Pre-registration scored prediction by prediction, including two reversals (D3's frontier claim, D5).
- The L4 cost finding (persistent note raises prompt tokens 69 percent) is a genuinely useful negative
  result for a popular practitioner recipe.

## Weaknesses (ordered by severity)

1. **One provider family (fatal for a top-tier accept, fixable).** Every number is Gemini. The cost
   conclusion, in particular, is a statement about Google's best-effort cache. The paper is candid
   about this (Section 5), but candour does not substitute for an Anthropic or OpenAI replication,
   and the D5 threshold question is left open precisely where it is most interesting. Estimated
   effort: one day and about USD 10 with a key that reaches those providers; the runner already
   supports explicit breakpoints.
2. **L3 is an oracle (fixable by framing, partly).** The headline "redaction is cheaper per correct
   answer" is about a pruner that knows the schema. The nearest deployable thing is L4, which the
   paper shows to be dominated. A reviewer will ask what a non-oracle pruner (age-based masking, as
   in the BFCL arm) achieves on StaleTrap. That arm exists in the code; running it on the main grid
   is cheap.
3. **The cache on/off control is weak.** Eleven paired questions. The heading "Caching does not
   change the answers" should be softened to what the evidence supports.
4. **The external arm is a null on a benchmark where the mechanism cannot fire.** BFCL multi-turn
   failures are state-mismatch and loop failures. The right external arm is a benchmark with
   world changes behind the agent (tau2-bench retail or airline has them). Its absence will be noticed.
5. **Audit not blind.** The coder is the agent that ran the study and could see the layout. The codes
   are mechanical and shipped, which mitigates but does not remove the concern.
6. **Thinking tokens on 2.5 Flash vary by layout** (639 to 790) and are not discussed as a confound
   for that rung.
7. **Page budget.** The main text runs 10 pages with the statements; ICLR 2026 allows 10, so it is
   legal, but the results section is dense and the dose-by-length figure was pushed to the appendix
   to make room.

## Format audit (ICLR 2025 norms from `venue_norms.json`, n = 151 accepted papers)

| Norm | Accepted-paper rate / median | This draft | Verdict |
|---|---|---|---|
| Pages (with appendix) | median 25 | 23 | fine |
| Figures | mean 11.5 | 6 (3 main + 3 appendix) + teaser | flag: below mean; density is adequate, results are also tabled |
| Tables | mean 8.7 | 13 | fine |
| Ablation table | 56.8% have one | the layout factorial is the ablation; Tables 3 and 4 | fine |
| Teaser figure on page 1 | 10.6% | present (Figure 1, page 2 by float) | fine, differentiator |
| Error bars / CIs | 40.2% | every contrast has a bootstrap CI; Table 3 means lack CIs in the table body | flag: add CIs to Table 3 |
| Significance tests | 6.1% | sign-flip, BH over 65 tests | fine, differentiator |
| Topic fit | "LLM Optimization and Programming" share 2.19% (2026, rising from 0.66% in 2023); "Autonomous LLM Agent Systems" 2.45% (rising from 0.10%) | both clusters growing | fine |

## Questions for the authors

1. What does an age-based (non-oracle) masking pruner score on StaleTrap's external traps, and where
   does it sit on the cost frontier?
2. Does the L1-to-L3 gap survive on a provider with explicit cache breakpoints, and does the cheapest
   layout per correct episode change there?
3. Why does L4 on 2.5 Flash recover 79 percent of the gap but only 42 percent on 3.1 Flash-Lite? Is the
   note read more by the thinking model?
4. On 3.6 Flash the history is never cached. Is that a property of the model's serving stack or of the
   1.6 to 1.9 second turn latency relative to the cache's refresh window?
5. How many of the 189 wrong trap answers on the main grid are "own write read back" versus "first
   read read back"? The audit sample suggests mostly the former; the full count is one line of code.

## What would move this to accept (ranked by expected score gain per hour)

1. **Run L1 and L3 on one non-Google model** (Claude Haiku 5.5 with explicit breakpoints, 144 tasks,
   about USD 6, half a day). Even a replication of the accuracy gap with a different cost ordering
   would resolve the paper's biggest open question and likely add a point.
2. **Add the non-oracle pruner (age-based masking) as L3b on the main grid** (USD 2, two hours). Turns
   "an oracle is cheaper" into "a deployable rule is cheaper (or is not)".
3. **Run a 30-task tau2-bench slice with external state changes** as the external arm instead of, or in
   addition to, BFCL (USD 3, half a day).
4. **Soften two headings** ("Caching does not change the answers" to "No evidence that a cache hit
   changes an answer"; abstract "perfectly" to "at or near 1.00") (ten minutes).
5. **Second, blind coder for the audit** (one hour of a colleague's time).
6. **Add CIs to Table 3** and move the dose figure back to the main text if space allows (half an hour).

## Venue shortlist (from `venue-fit`, 50 nearest accepted papers)

Nearest accepted neighbours sit at ICML (16), ICLR (12), NeurIPS (10) and ACL (8); the dominant topic
cluster is "LLM Optimization and Programming" (26 of 50), with "Autonomous LLM Agent Systems" second
(7 of 50). Both clusters are growing (2.2% and 2.4% of accepted papers in 2026, up from 0.7% and 0.1%
in 2023). Closest neighbours: Tail-Optimized Caching for LLM Inference (NeurIPS 2025), Tvcache
(ICML 2026), Agentic Plan Caching (NeurIPS 2025), When KV Cache Reuse Fails in Multi-Agent Systems
(ACL 2026), How Memory Management Impacts LLM Agents (ACL 2026), Auditing Prompt Caching in Language
Model APIs (ICML 2025); the last three were added to the related work after this retrieval.

Recommendation, in order:

1. **ICLR 2027 main track** after fixes 1 and 2 above (fit: the measurement-with-controls style and
   the cost-aware evaluation line of work are both at home there; acceptance rate 27%).
2. **ICML 2027 main track** as the alternative (largest neighbour share; same fixes).
3. **Workshops now, as is:** the ICLR or NeurIPS workshops on LLM agents and on efficient inference
   (the 2026 editions were "Agentic AI" and "Efficient Systems for Foundation Models"); the paper's
   single-vendor scope and oracle pruner are acceptable there, and the own-versus-external finding
   is a strong workshop talk.
4. **ACL 2027** is a plausible fourth: the ACL neighbours are the memory-management and KV-reuse
   empirical studies, and the paper's style (controls, pre-registration, audit) matches ACL's
   analysis track.
