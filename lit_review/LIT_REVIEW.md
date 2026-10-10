# Literature review: Cheap but Confused? The accuracy cost of cache-optimized context layouts in LLM agents

Date: 2026-10-10. Method: the planning session's pre-emption sweep (`00_preemption_sweep_2026-10-10.md`,
59 arXiv ids, re-verified today against the arXiv API: 59 OK, 0 mismatches, `sweep_refs_verification.md`),
a recency and pre-emption re-check (`recency_2026-10-10.md`: 37 arXiv API queries sorted by submission
date, 536 unique ids screened, 59 candidates read at abstract level, 15 abstract pages fetched), and two
extension angles: A, stale and superseded information and positional effects in multi-turn agent
histories (`angle_A_stale_position.md`, 31 new verified ids), and B, agent context management, caching
economics and cost-aware evaluation (`angle_B_context_mgmt_cost.md`, 45 new verified ids). The merged,
de-duplicated table is `lit_review.csv`: **174 unique verified ids** (90 via the arXiv API, 59 via the
abstract page, 25 via a second API pass; 103 from 2026, 39 from 2025). Summaries are from abstracts unless
a full-text read is stated. No API keys or credentials appear in any file.

---

## Verdict: ALIVE-BUT-CROWDED (no pre-emption as of 2026-10-10)

No paper satisfies all four defining criteria at once: (a) a content-fixed manipulation of context
layout, (b) in a multi-turn tool-using agent, (c) scored against provider-reported cached tokens and
billed USD, (d) with task accuracy as an outcome. Nothing submitted in September or October 2026 holds
content fixed and varies layout; that wave is compaction and folding methods (content changes) and
serving-side KV-cache work. The intersection is open, and the neighbours now state the gap almost
verbatim: 2607.12161 asks for "cost per successful task, including cache behavior, trajectory changes,
and correctness"; 2609.37012 says efficient compression "depends not only on shortening prompts but also
on scheduling edits to preserve cache reuse"; 2610.04433 finds harness cost is "set at the first call, by
the preamble, scaled by the number of steps". Why crowded: at least six 2026 papers measure accuracy and
some notion of cache-aware cost in tool-using agents, and every compaction-method paper carries a
"full history" control that is, in effect, our append-only arm. The defensible novelty is therefore the
two arms nobody runs (relevance-reordered with content fixed, and stable-prefix plus recitation), the
stale-trap step annotation that names the mechanism, and provider-billed cache telemetry on all arms.

---

## Novelty delineation (written before any result; the paper's Table 1)

| Nearest work | What it established | What it does NOT do (ours) |
|---|---|---|
| Token Reduction Is Not Cost Reduction (2607.12161, Jul 2026) | Claude Code; provider-billed cost split into cache creation and reads; SWE-bench Go patch success; compression can raise the bill by changing trajectories; "cost per successful task including cache behavior" as the right metric | Manipulates tool-output compression (content changes); no order-only, no recitation arm; one family; no step-level stale annotation |
| Don't Break the Cache (2601.06007, Jan 2026) | Caching strategies on OpenAI, Anthropic, Google; 500+ sessions; 41-80% cost and 13-31% TTFT savings | Task accuracy is not an outcome; no layout manipulation |
| What Does a Harness Buy? Tokens, Mostly (2610.04433, Oct 2026) | 5 models x 3 harnesses on SWE-bench Verified; pass rate and cost per task; cached pricing scales the bill but does not reorder harnesses | Whole harnesses differ (prompt, tools, context policy); cost repriced from a list, not billed telemetry; no content-fixed arm |
| TokenPilot (2606.17016, EMNLP 2026 Findings) | Names the text-sparsity vs prompt-cache-continuity trade-off; ingestion-aware compaction; hit rate 38.7% to 79.2% | Method paper; order and pruning confounded; accuracy reported as "competitive" |
| Cache-Aware Prompt Compression (2607.15516, Jul 2026) | Anthropic telemetry; hit-rate plateau ~0.83; query-aware compression breaks caches; 50 tau-bench tasks | Compression only; no ordering or stale-retention arm; one provider |
| CacheWeaver (2606.19667) and Prefix Sharing Is a Sorting Problem (2609.13692) | Cache-aware ordering of retrieved evidence or shared prefixes; quality unchanged in RAG | Single-turn RAG or serving; no agent history, no stale observations, no pricing |
| Do RAG Systems Really Suffer From Positional Bias? (2505.15561, EMNLP 2025) | In realistic retrieval, relevance reordering is no better than shuffling | RAG, not agents; no history or caching; it is our D2 null |
| Less Context, Better Agents (2606.10209); The Complexity Trap (2508.21433); Masking Stale Observations (2606.00408); What Does Context Compression Cost an Agent? (2608.16370); OpenHands condenser study (2605.18854) | Pruning or masking vs full history with accuracy; masking is as good as LLM summaries and far cheaper; benefits depend on model capacity | No cache accounting, so every "compression saves X%" number is biased against append-only layouts by exactly the cache-read discount; no order-only arm |
| When Agent Context Goes Stale (2610.05281); multi-revision latest-value failures (2603.12271); repeated-key retrieval mechanism (2510.22752) | Agents answer from stale observations; latest-value accuracy falls as revisions accumulate; induction heads favour earliest and latest occurrences | Single-call or runtime-fix studies; no layout factorial, no cost |
| Leyline (2606.01065), Irminsul (2605.05696), Request Order Matters (2610.05833), KVTether (2609.39819) | Serving-side fixes for non-prefix KV reuse; naive reuse degrades fidelity | Do not evaluate the API-level discipline practitioners follow |
| StateAct (2410.02810), R&R reprompting (2403.05004), belief-state block (2610.01415), EverMemBench version semantics (2602.01313) | Restating goal and state near the question helps; timestamps alone do not convey which version is current | Not evaluated as a cache-preserving layout against pruning; no cost |
| Manus (Jul 2025), Anthropic (Sep 2025), Bouchard (Aug 2026), Copilot trace study (2608.00101) | Prescribe the layouts; production hit rates ~90% within a turn and ~55% at turn boundaries; compaction is the dominant invalidation event | No controlled accuracy measurement with content fixed |

**Ours alone:** content-fixed layout manipulation (order-only L2, content-only L3, recitation-only L4,
against the cache-optimal L1) in a multi-turn tool-using agent, on three model families, scored against
provider-reported cached tokens and billed USD, with every question step annotated as stale-trap or
neutral so the mechanism is named rather than inferred, and a per-model cache-read price threshold at
which the cheapest layout per call stops being the cheapest per correct answer.

---

## What the three angles imply for the pre-registered directions

**D1 (stale-retention cost).** Strong prior from 2603.12271 (latest-value accuracy falls as revisions
accumulate while first-value accuracy stays high) and 2510.22752 (retrieval favours the earliest and
latest occurrence of a repeated key). Two cautions the design already absorbs: 2508.07479 predicts
far-back values are attenuated rather than misread in long inputs, so the hand audit codes "could not
find the current value" separately from "used the stale value"; 2601.07226 and 2602.11348 show
distractor damage in tool settings can be large, so "no comparable gap on neutral steps" is tested as a
layout x distractor interaction, not assumed.

**D2 (order-only effect small, cost large).** The null prior is strengthened: recency is the stable bias
as inputs grow (2508.07479), and L1 already places the newest observation and the user turn last, so L2's
"most relevant last" moves an item into a slot the newest observation already occupies. The one
pro-reordering counterweight is single-call document ranking (2508.05128, 2410.05983), which rewrites
the prefix every call. If L2 wins, the explanation to test is that the stale competitor was moved away
from the end, not that the current value was moved toward it.

**D3 (the hybrid dominates).** StateAct, the belief-state block and EverMemBench all point to an explicit
"which observation is current" line as the thing the history lacks; TRACE (2608.06503) and StateComp
(2609.27298) warn that replacing history weakens recency and that "safe to replace" is a learned
judgement. If D3 holds, it is the first content-matched evidence that the benefit attributed to
compression comes largely from restating current state near the question rather than from deleting the
past. The known cost (2607.08716: always-on reminders underperform selective ones) is reported on neutral
steps.

**D4 (model dependence).** 2606.00408 gives the regime map: masking helps mid-capacity models and does
nothing or harms at the extremes; the capability ordering within each family is a property of the
checkpoints, not a law.

**D5 (price threshold).** External anchors: Bouchard's ~$0.55/MTok break-even, the ~10-turn break-even of
2603.04814, Copilot's 90%/55% hit rates, and the convention in HAL (2510.11977), Cost-of-Pass
(2504.13359) and the harness papers (2607.06906, 2607.22585, 2608.08654) of pricing tokens at list rates
with no cache split. The threshold is presented as the correction to that convention: USD per correct
task from billed `usage.cost`, then recomputed under counterfactual cache-read multipliers (0.025x to 1x).

---

## Methodological flags recorded for the design

- Prefix caching alone changes agent trajectories in 36-75% of episodes on open-source engines
  (2609.04748). On the API providers, Anthropic documents caching as output-neutral; our cache on/off
  control on the Anthropic arm tests it directly, and any open-weight arm must pair runs and fix seeds.
- Cache TTL expiry during tool pauses must be controlled (2607.19214), or expiry misses are confused with
  layout misses: every episode's turns run sequentially inside one process within the TTL.
- Explicit `cache_control` on Gemini through OpenRouter creates an explicit cache each call and bills
  write plus storage (measured today: 3.5x to 5.8x the cost of an implicit hit), so the Gemini arm uses
  implicit caching only and reports the observed hit distribution.
- The "mask vs remove tools" question is unmeasured anywhere (only catalogue-size effects are documented:
  2505.10570, 2505.03275, 2605.24660), which supports holding the tool block fixed across L1-L4.

## Files
- `lit_review.csv` (174 ids), `sweep_refs_verified.csv`, `angle_recency.csv`, `angle_A.csv`, `angle_B.csv`
- `recency_2026-10-10.md`, `angle_A_stale_position.md`, `angle_B_context_mgmt_cost.md`, `sweep_refs_verification.md`, `verify_refs.py`
