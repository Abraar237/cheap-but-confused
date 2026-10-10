# Literature sweep: "Cheap but Confused? The Accuracy Cost of Cache-Optimized Context Layouts in LLM Agents"

Sweep date: 2026-10-10. Method: ~40 web searches (standard + extended), ~35 page fetches of arXiv abstracts and vendor docs, and one batch arXiv-API lookup that confirmed title/author/date for 74 IDs. Every arXiv ID below marked [V] was returned by the arXiv API with the stated title; [D] = verified by fetching the vendor/doc page; [U] = could not be verified (stated explicitly). Summaries are from abstracts and doc pages, not full-paper reads, unless noted.

---

## 0. One-paragraph answer

Nobody has yet run the experiment this paper proposes: hold the *information content* of an agent's context fixed, vary only its *layout* (append-only prefix-stable vs relevance-reordered vs pruned/compacted vs a stable-prefix + goal-recitation hybrid), and measure task accuracy against *real provider-reported cached tokens and real USD*. But the surrounding ground is crowded and moving fast. Three 2026 arXiv papers sit within one step of it: "Don't Break the Cache" (2601.06007, cost/TTFT of caching strategies for agents, **no accuracy**), "TokenPilot" (2606.17016, explicitly names the "text sparsity vs prompt-cache continuity" trade-off, but as a method paper, not a controlled layout study), and "Cache-Aware Prompt Compression" (2607.15516, caching-vs-compression cost model on Anthropic's API with a 50-task tau-bench check, **no ordering arm**). On the RAG side, "Do RAG Systems Really Suffer From Positional Bias?" (2505.15561, EMNLP 2025) found relevance-based reordering is no better than shuffling in realistic RAG, which is a direct threat to the hypothesis that cache-friendly ordering costs accuracy and must be engaged head-on. Verdict: **ALIVE-BUT-CROWDED**; details and sharpening in Sections 8-9.

---

## 1. Positional effects in LLMs

| Paper | ID / venue | Date | Summary (2-3 sentences) |
|---|---|---|---|
| Lost in the Middle: How Language Models Use Long Contexts (Liu, Lin, Hewitt, et al.) | arXiv 2307.03172 [V]; TACL 2024 | Jul 2023 | Multi-document QA and key-value retrieval: accuracy is U-shaped in the position of the relevant document, highest at the start and end, lowest in the middle; degradation grows with context length. The canonical citation for primacy/recency in long context. |
| Found in the Middle: Calibrating Positional Attention Bias Improves Long Context Utilization (Hsieh, Chuang, Li, et al.) | arXiv 2406.16008 [V]; ACL 2024 Findings | Jun 2024 | Attributes lost-in-the-middle to an intrinsic U-shaped attention bias and proposes a calibration ("found-in-the-middle") that disentangles position from relevance, improving RAG accuracy by up to ~15 points. Evidence that the effect is an attention-level artifact, not a data artifact. |
| Found in the Middle: ... via Plug-and-Play Positional Encoding (Ms-PoE) (Zhang, Chen, Liu, et al.) | arXiv 2403.04797 [V] | Mar 2024 | Multi-scale positional encoding rescaling to reduce the middle-position penalty without fine-tuning. Same name, different paper; cite both carefully. |
| Make Your LLM Fully Utilize the Context (An, Ma, Lin, et al.) | arXiv 2404.16811 [V]; NeurIPS 2024 | Apr 2024 | IN2 (information-intensive) training as a data-driven cure for lost-in-the-middle. Shows the effect is trainable away, so magnitude is model-dependent (important for your H4). |
| The Power of Noise: Redefining Retrieval for RAG Systems (Cuconasu, Trappolini, Siciliano, et al.) | arXiv 2401.14887 [V]; SIGIR 2024 | Jan 2024 | Relevant documents must sit near the query to be used; topically related but non-answering distractors hurt most; randomly irrelevant noise can even help. Core citation for "position of gold relative to the question" and distractor effects. |
| Do RAG Systems Really Suffer From Positional Bias? (Cuconasu, Filice, Horowitz, Maarek, Silvestri) | arXiv 2505.15561 [V]; EMNLP 2025 main | May 2025 (rev. Oct 2025) | In realistic retrieval pipelines, >60% of queries have a hard distractor in the top-10, so positional bias penalizes relevant and distracting passages alike; sophisticated reordering strategies do no better than random shuffling. **The strongest published counter-argument to your premise; must be addressed.** |
| Long-Context LLMs Meet RAG (Jin, Yoon, Han, et al.) | arXiv 2410.05983 [V] | Oct 2024 | Retrieval reordering (placing top-ranked passages at the extremes) significantly improves RAG with many passages; hard negatives degrade long-context RAG. Pro-reordering evidence. |
| GOLD PANNING: Strategic Context Shuffling (Byerly, Khashabi) | arXiv 2510.09770 [V] | Oct 2025 | Exploits positional bias as a control signal: iterative document reordering identifies the gold document in O(log N) rounds with 30-65% fewer queries than permutation self-consistency. Shows ordering is a live lever even on 2025 models. |
| Lost at the End: Primacy Bias in Multimodal RAG QA (Liu, Gu, Chen, et al.) | arXiv 2606.16494 [V] | Jun 2026 | For VLMs the curve is not U-shaped: gold-at-first beats gold-at-last by 16-26 points across 3B-32B models. Shows the direction of bias is model-family dependent. |
| Input Order Shapes LLM Semantic Alignment in Multi-Document Summarization (Ma) | arXiv 2512.02665 [V] | Dec 2025 | Clear primacy effect: summaries align with the first-seen document, with implications for agentic pipelines where early-seen content drives later actions. |
| Giraffe: Adventures in Expanding Context Lengths (Pal et al.) | arXiv 2308.10882 [V] | Aug 2023 | Includes a direct question-first vs question-last comparison on FreeFormQA: question at the end wins consistently across context lengths. |
| BAMBOO benchmark (Dong, Tang, Li, et al.) | arXiv 2309.13345 [V] | Sep 2023 | Observes that instruction placed only at the beginning degrades as input grows; placing it at the end helps. |
| Instruction Position Matters in Sequence Generation with LLMs (Liu, Zeng, Meng, et al.) | arXiv 2308.12097 [V]; ACL 2024 Findings | Aug 2023 | Pre-Ins vs Post-Ins vs Both-Ins: post-instruction improves generation (translation/summarization), especially for long inputs. |
| Do prompt positions really matter? (Mao, Middleton, Niranjan) | arXiv 2305.14493 [V] | May 2023 | Prompt position substantially affects performance; positions used in prior work are often sub-optimal even for instruction-tuned models. |
| Attention Instruction: Amplifying Attention in the Middle via Prompting (Zhang, Meng, Collier) | arXiv 2406.17095 [V] | Jun 2024 | Prompting the model to attend to a region partly mitigates middle neglect. Relevant to the L4 "recitation" arm. |
| Can't Remember Details in Long Documents? You Need Some R&R (Agrawal, Gao, Gajek) | arXiv 2403.05004 [V]; EMNLP 2024 Findings | Mar 2024 | "Reprompting" (repeating the instruction periodically) plus in-context retrieval improves long-document QA by ~16 points on GPT-4 Turbo / Claude 2.1 at up to 80k tokens, attributed to reducing instruction-to-evidence distance. **Direct precedent for the L4 hybrid (restate the question at the end while keeping the prefix stable).** |
| Context Rot: How Increasing Input Tokens Impacts LLM Performance (Hong, Troynikov, Huber; Chroma) | trychroma.com/research/context-rot [D] | Jul 14 2025 | 18 models; NIAH with distractors, needle-question similarity, haystack structure, LongMemEval focused (~300 tok) vs full (~113k tok), repeated words. Even one distractor hurts; shuffled haystacks beat coherent ones; large focused-vs-full gap on LongMemEval especially for Claude. Industry-standard citation for "more context, worse answers". |
| NoLiMa: Long-Context Evaluation Beyond Literal Matching (Modarressi et al.) | arXiv 2502.05167 [V] | Feb 2025 | NIAH without lexical overlap; most models fall below 50% of short-context performance by 32k. Shows degradation is about associative retrieval, not just length. |
| Tool Preferences in Agentic LLMs are Unreliable (Faghih, Wang, Cheng, et al.) | arXiv 2505.18135 [V] | May 2025 | Position in the tool list biases selection: with identical tools, the first-listed is used more by GPT-4.1 and Qwen2.5-7B. The agent-side analogue of position bias; relevant to "tools first, never reordered". |
| When Agent Context Goes Stale: Incoherence in Volatile Agent Context (Liu, Fang, Qian) | arXiv 2610.05281 [V] | Oct 2026 | Agents answer from stale tool observations after the underlying file changes; Concord links observations to sources and updates/annotates/suppresses stale ones; ConcordBench. Directly supports the "stale tool outputs kept for cache" risk, but is a runtime fix, not a layout study. |
| Masking Stale Observations Helps Search Agents -- Until It Doesn't (Zhang, Xu, Li, et al.) | arXiv 2606.00408 [V] | May 2026 | Regime map across 4B-284B models and three retrievers: masking old observations helps mid-capacity models with strong retrievers, does nothing with weak retrievers, and collapses saturated models. Mechanism: token-for-turn trade-off. No caching or cost analysis. Important for predicting model-dependence of your effect. |

Also relevant: LongMemEval (2410.10813 [V], ICLR 2025) has explicit "knowledge update" and "abstention" categories that are exactly stale-vs-current information tests inside long chat histories.

---

## 2. Prompt / prefix / KV caching systems papers

| Paper | ID / venue | Date | What it does | Measures accuracy loss from reuse/reordering? |
|---|---|---|---|---|
| Prompt Cache: Modular Attention Reuse for Low-Latency Inference (Gim et al.) | 2311.04934 [V]; MLSys 2024 | Nov 2023 | Precompute KV for reusable prompt "modules" via a schema; reuse at different positions. | Yes: reports output quality roughly preserved on a few benchmarks, but reuse is position-aware via schema. |
| SGLang / RadixAttention (Zheng et al.) | 2312.07104 [V]; NeurIPS 2024 | Dec 2023 | Radix-tree prefix KV cache sharing across requests; the open-source baseline for exact-prefix caching. | No accuracy change (exact prefix). |
| RAGCache (Jin, Zhang, Jiang, et al.) | 2404.12457 [V] | Apr 2024 | Knowledge-tree KV cache for retrieved documents with prefix-aware replacement and dynamic speculative pipelining. | Exact-prefix reuse, so no accuracy study; notes order sensitivity as a constraint. |
| CacheBlend (Yao, Li, Liu, et al.) | 2405.16444 [V]; EuroSys 2025 | May 2024 | Fuse independently cached chunk KVs by selectively recomputing a small fraction of tokens. | Yes: quality within small margin of full prefill on RAG QA; later work (KVLink, Request Order Matters) shows degradation and history-sensitivity. |
| EPIC: Efficient Position-Independent Caching (Hu, Huang, Wang, et al.) | 2410.15332 [V]; ICML 2025 | Oct 2024 | Position-independent caching with LegoLink to fix per-document attention sinks. | Yes: up to 8x TTFT with "negligible or no" loss; vs CacheBlend, accuracy loss within 7%. |
| Block-Attention for Efficient Prefilling (Ma, Wang, Tian, et al.) | 2409.15355 [V]; ICLR 2025 | Sep 2024 | Encode retrieved blocks independently so their KV can be reused in any order; needs fine-tuning. | Yes: after fine-tuning matches self-attention accuracy on RAG; without it, large drop. |
| APE: Adaptive Parallel Encoding (Yang, Chen, Chen) | 2502.05431 [V]; ICLR 2025 | Feb 2025 | Parallel encoding of contexts with shared prefix, attention temperature and scaling to preserve ~98% of sequential-encoding accuracy. | Yes: central contribution. |
| Cache-Craft (Agarwal, Sundaresan, Mitra, et al.; Adobe) | 2502.15734 [V]; SIGMOD 2025 | Feb 2025 | Manage chunk-caches for RAG; identify reusable chunk KVs and recompute a small fraction to hold quality. | Yes: notes naive reuse "leads to output quality degradation"; 51% less compute vs prefix caching with maintained quality. |
| KVLink (Yang, Hou, Wei, et al.) | 2502.16002 [V]; NeurIPS 2025 | Feb 2025 | Position re-embedding plus trainable link tokens to restore cross-document attention. | Yes: cites up to 35% relative QA accuracy loss from naive independent encoding; recovers +4% over SOTA. |
| MPIC (Zhao, Hu, Huang, et al.) | 2502.01960 [V] | Feb 2025 | Position-independent multimodal context caching with reuse-recompute mixing. | Yes: "negligible or no" loss claimed. |
| Irminsul (Ma, Eitzinger, Koestler) | 2605.05696 [V] | May 2026 | MLA-native content-addressed caching extending SGLang radix cache; recovers ~83% of prompt tokens above exact-prefix on agentic traffic. | Output-consistency checks only. Documents the agent "shifted position" problem. |
| Leyline: KV Cache Directives for Agentic Inference (same group) | 2606.01065 [V] | May 2026 | Serving-side directives to splice/edit cached content with RoPE correction, because agent contexts evolve by edits, not just appends. | Yes: +11.2 pp cache hit, +14.3 pp solve rate on debug-gym. Closest serving-side cousin: it argues the append-only constraint is a serving limitation. |
| Request Order Matters: Cache-History Sensitivity in Selective KV-Cache Reuse for Rolling Agents (Gu et al.) | 2610.05833 [V] | Oct 2026 | Rolling-window agents with CacheBlend-style selective recompute give different answers depending on request history; document-aligned recompute cuts answer variation from 69% to 26%. | Yes, fidelity to full prefill. Serving-side, not API-side. |
| Accelerating LM Workflows with Prompt Choreography (Bai, Eisner) | 2512.23049 [V]; TACL | Dec 2025 | Global KV cache where calls attend to arbitrary reordered subsets of prior messages; acknowledges cached encodings differ from re-encoding and fine-tunes to close the gap. | Yes, via fine-tuning. |
| CacheWeaver: Cache-Aware Evidence Ordering for Grounded RAG (Tan, Gu, Li) | 2606.19667 [V] | Jun 2026 | Prompt-layer method: reorder retrieved evidence to maximize prefix-tree reuse in vLLM; 20-33% TTFT reduction "without hurting answer quality in our QA tests". | Partially: checks QA quality is unchanged, but single-turn RAG, open-weight serving, no agent tasks, no API cost. **Nearest RAG-side neighbor.** |
| SemPIC: Learning Semantic Position-Independent KV Caches (Xie, Xiao, Deng) | 2607.28069 [V] | Jul 2026 | Learned PIC. | Not fetched in detail. |
| KVCOMM (Ye, Gao, Ma, et al.) | 2510.12872 [V] | Oct 2025 | Cross-context KV communication for multi-agent systems; robust to ordering strategies. | Reports accuracy maintained across orderings. |
| Learning Agent Execution for KV-Cache Management in Agentic Serving (Zhang, Kim, Feng, et al.) | 2608.14624 [V] | Jul 2026 | Predict agent execution to schedule KV eviction/prefetch. | Serving only. |
| Agentic Plan Caching (Zhang, Wornow, Wan, et al.) | 2506.14852 [V] | Jun 2025 | Cache plan templates rather than KV; notes semantic/full-history caching causes accuracy drops on hits. | Yes, at plan level. |

Takeaway: the systems literature already knows that *non-prefix* KV reuse costs accuracy and has spent two years engineering around it. What it never asks is whether the *application-level* discipline that exact-prefix caching imposes (never reorder, never prune) costs accuracy by itself.

---

## 3. Context engineering for agents and provider caching mechanics

### 3.1 Practitioner guidance
- **Manus, "Context Engineering for AI Agents: Lessons from Building Manus"** (Yichao "Peak" Ji, Jul 18 2025) [D]. Sections: Design Around the KV-Cache; Mask, Don't Remove; Use the File System as Context; Manipulate Attention Through Recitation; Keep the Wrong Stuff In; Don't Get Few-Shotted. Claims KV-cache hit rate is "the single most important metric", ~50 tool calls per task, ~100:1 input:output. **No accuracy measurements; all anecdotal.** Note the internal tension: "Recitation" (rewrite todo.md at the end) is itself a cache-preserving recency hack, which is your L4.
- **Anthropic, "Effective context engineering for AI agents"** (Sep 2025) [search-verified, not fetched]. Context as a finite resource; compaction, structured note-taking (NOTES.md / todo), sub-agent architectures; recommends deferred tool loading when tool definitions exceed ~10k tokens. No controlled accuracy numbers.
- **Louis Bouchard / Towards AI, "Context Engineering in 2026: Why We Stopped Compacting Our Agent's Context"** (Aug 18 2026) [D]. AI tutor on Gemini 3.5 Flash with DeepSeek V4 Flash and local 32B as secondary; strategies: full history, production preset (clear tool outputs at 5k, summarize at 30k), sliding window, prompt compression, selective retention, reset. Full history vs production preset: memory recall 92% vs 38%, cost/turn $0.11 vs $0.24, TTFT 17s vs 21s. Keeping full history wins when cached input is below ~$0.55/MTok. Tool-output capping on DeepSeek cut cost 38% at identical memory accuracy with cache hit ratio 96.0% vs 95.9%. **Does not vary order or layout; only content.** Nearest practitioner neighbor.
- **ProjectDiscovery (Neo) anecdote** [search-verified via secondary blogs; primary post not fetched]: moving one dynamic identifier out of the prefix raised cache hit rate from 7% to 74-84% and cut spend 59%. Cost-only.
- **The Complexity Trap: Simple Observation Masking Is as Efficient as LLM Summarization** (Lindenbauer et al., 2508.21433 [V], DL4C @ NeurIPS 2025). SWE-agent on SWE-bench Verified, 5 model configs: masking halves cost vs raw agent while matching or slightly exceeding summarization's solve rate; hybrid saves a further 7-11%. **No prompt caching accounting.**
- **Less Context, Better Agents** (Lodha et al., 2606.10209 [V], Jun 2026). 50 MCP tool tasks on Dynamics 365, GPT-5 and Claude Sonnet 4.5: pruning to last 5 tool pairs 79% vs full history 71% completion at one-third the tokens; pruning+summarization 91.6%. **No cache hit or USD cost.**
- **What Does Context Compression Cost an Agent?** (Liu, 2608.16370 [V], Aug 2026). Dropping vs fact-preserving compression on a planning env and ALFWorld: completion unchanged but retrieval calls triple (GPT-5.5: 21.0 to 63.9), i.e. hidden interaction cost. No caching.
- **CliffCompaction** (Nguyen, Cho, Chen, Dettmers, 2609.26779 [V], Sep 2026), **Slipstream** (2605.08580 [V]), **Self-Compacting LM Agents** (2606.23525 [V]), **ACM** (2607.23809 [V]), **When Can Agents Forget Their Reasoning?** (2609.29875 [V]; reports cache-read tokens falling 33.3% as a side effect), **ReFold** (2610.07863, title seen in search, not API-verified [U]), **Persistent Context Graphs** (2609.40118 [U]). All are compaction *methods*; none is a controlled layout-vs-accuracy-vs-cached-cost study.
- **TokenPilot: Cache-Efficient Context Management for LLM Agents** (Xu et al., 2606.17016 [V], Jun 2026). Explicitly frames "a critical trade-off between text sparsity and prompt cache continuity"; Ingestion-Aware Compaction stabilizes prefixes, Lifecycle-Aware Eviction batches evictions. PinchBench and Claw-Eval: 56-87% cost reduction, cache hit rate 38.7% to 79.2%, "competitive task performance". **Nearest agent-side neighbor.** It is a system; it does not isolate ordering from pruning, and performance is reported as "competitive", not as a measured accuracy cost.
- **ContextPipe: Database-Inspired Context Assembly for Long-Horizon Agents** (Xu, Zhang, Sun, et al., 2609.00749 [V], Sep 2026). Compares an "append-only context construction policy" to a cache-aware optimizer on a SWE-bench Pro subset: -31% tokens, -23% LLM calls, -9% latency "at the cost of a lower KV cache-hit ratio". Confirms the trade-off exists but reports it as a system side-effect, not as an accuracy frontier.
- **CacheRouter** (Zha et al., 2608.22708 [V], Aug 2026). Dual-path tool routing that keeps the main model's tool prefix fixed; 91-95% token-level cache hit rate; cost 8-12% of no-cache at DeepSeek prices. Cost only.
- **Tool Attention Is All You Need** (Sadani, Kumar, 2604.21816 [V], Apr 2026). Tool gating / lazy schema loading; 95% fewer tool tokens, but task-success numbers are *projections*, not live measurements. The "mask vs remove" question remains empirically open.
- **Cache-Aware Prompt Compression: A Two-Tier Cost Model for LLM API Caching** (Song, 2607.15516 [V], Jul 2026). Measures on Anthropic Sonnet 4.6 that hit rate plateaus at ~0.83 below a ~3,500-token threshold; query-aware compression invalidates the cache; CAPC pairs query-agnostic compression with cache_control. LongBench-v2 quality within 0.05; tau-bench retail 50 tasks: reward 36/50 identical to vanilla, query-aware compression +40% cost. **Nearest API-side neighbor**; no reordering arm, compression not ordering.
- **Don't Break the Cache: An Evaluation of Prompt Caching for Long-Horizon Agentic Tasks** (Lumer et al., 2601.06007 [V], Jan 2026). OpenAI/Anthropic/Google, DeepResearch Bench, 500+ sessions, 10k-token system prompts; full-context vs system-only vs exclude-tool-results caching; 41-80% cost and 13-31% TTFT savings; ablations over 500-50k prompt tokens and 3-50 tool calls. **Measures cost and TTFT only; task accuracy is not an outcome.**
- **Beyond the Context Window** (Pollertlam, Kornsuwannawit, 2603.04814 [V], Mar 2026). Mem0 fact memory vs long-context GPT-5-mini on LongMemEval/LoCoMo/PersonaMemv2 with a cost model that includes caching; break-even ~10 turns at 100k context. Accuracy and cost, but memory-architecture, not layout.
- **Context Engineering 2.0** (2510.26493 [V]) and **A Survey of Context Engineering for LLMs** (2507.13334 [V]): surveys; neither reports the layout-vs-cache frontier.

### 3.2 Provider mechanics (fetched 2026-10-10)
- **Anthropic** [D] (platform.claude.com prompt-caching page): prefix hierarchy tools -> system -> messages; change at any level invalidates it and everything after. Up to 4 breakpoints; automatic top-level `cache_control` uses one slot. 5-min write 1.25x, 1-h write 2.0x, read 0.1x (newer models show 0.05x/0.025x read multipliers on the page). Minimums: 512 tokens for the newest families, 1,024 for Sonnet 4.x/Opus 4/4.1/4.8, 2,048 for Opus 4.7/Haiku 3.5, 4,096 for Opus 4.5/4.6 and Haiku 4.5. Usage fields: `cache_creation_input_tokens`, `cache_read_input_tokens`, `input_tokens` (uncached remainder), plus `cache_creation.ephemeral_5m_input_tokens / ephemeral_1h_input_tokens`. 20-block lookback window per breakpoint (consecutive tool_use / tool_result blocks count as one). Changing tool definitions, tool_choice, images, thinking/effort settings all invalidate at documented levels. Page states that caching does not change outputs.
- **OpenAI** [D] (developers.openai.com prompt-caching guide): automatic for prompts >= 1,024 tokens; `usage.prompt_tokens_details.cached_tokens` (Chat Completions) / `usage.input_tokens_details.cached_tokens` (Responses). Pre-GPT-5.6 models: discount model-dependent (historically 50% on 4o-family, 75-90% on GPT-5 family), no write charge, cache lifetime 5-10 min inactivity up to 1 h, `prompt_cache_key` for routing, `prompt_cache_retention: "24h"` option, caching in 128-token increments. GPT-5.6+: explicit mode with `prompt_cache_breakpoint`, 1.25x write, 0.1x read, 30-min TTL option. Guidance: static first, dynamic last.
- **Gemini** [D] (ai.google.dev caching): implicit caching default on 2.5+; minimums 2,048 (2.5 Flash/Pro), 4,096 (3.x); reported in `usage_metadata.cached_content_token_count` (and `total_cached_tokens` in some SDK surfaces); cached input ~75-90% cheaper per pricing pages (e.g. 3.1 Pro $0.20 vs $2.00 per MTok). Guidance: put large common content at the beginning. Explicit caching has TTL and per-hour storage charges.
- **DeepSeek** [D] (api-docs.deepseek.com): automatic prefix caching, cache units at fixed intervals (64-token granularity historically), `prompt_cache_hit_tokens` / `prompt_cache_miss_tokens` in usage; cache hit priced at roughly 1/20 to 1/30 of miss (fetched pricing page: deepseek-flash $0.006 hit vs $0.30 miss peak per MTok; v4-pro $0.044 vs $1.32). Cache cleared after hours to days. Best-effort, not guaranteed.
- **OpenRouter** [D] (openrouter.ai docs: prompt-caching, usage-accounting): usage is always included now (`usage: {include: true}` deprecated). Fields: `usage.cost` (credits, USD-denominated), `usage.prompt_tokens_details.cached_tokens` (read), `usage.prompt_tokens_details.cache_write_tokens`, `usage.completion_tokens_details.reasoning_tokens`, `usage.cost_details.upstream_inference_cost` (BYOK only), and `cache_discount` in the response body (negative on Anthropic writes, positive on reads). Streaming: usage arrives in the final chunk. Provider matrix on the doc page: OpenAI (implicit; explicit on GPT-5.6+), Anthropic (implicit + explicit `cache_control`, 4 breakpoints), Google Gemini 2.5+ (implicit + explicit; only the final `cache_control` honored), DeepSeek (implicit), Groq (implicit, Kimi K2), xAI Grok (implicit, 0.25x read, free write), Moonshot (implicit, 0.25x read), Alibaba Qwen (explicit only: qwen3-max, qwen-plus, qwen3.6-plus, qwen3-coder; 0.1x read, 1.25x write), Z.AI (implicit). Block-level `cache_control` and `prompt_cache_breakpoint` markers are translated across providers. Sticky routing keeps the same upstream for 10 min of inactivity when read price < input price; `session_id` header/body supported; manual `provider.order` disables it. Anthropic minimums mirror Anthropic docs; Gemini minimums showed unrendered placeholders on the page (use Google's 2,048/4,096). Open-weight providers (Together, Fireworks, DeepInfra, etc.) are not listed as supporting caching through OpenRouter; treat their cached_tokens as zero unless observed.
- **vLLM** [D] (docs.vllm.ai design/metrics): prefix caching is on by default in V1 (`--no-enable-prefix-caching` to disable); Prometheus counters `vllm:prefix_cache_queries` and `vllm:prefix_cache_hits` (both in tokens), hit rate = hits/queries; logs print a hit rate over the last 1k block queries. Per-request `prompt_tokens_details.cached_tokens` requires `--enable-prompt-tokens-details`; GitHub issue #16162 reported this returned null on V1 in 2025 -- **verify on the version you deploy; fallback is to serialize requests and diff `/metrics` counters around each call, or use the offline `LLM.generate` path where `RequestOutput.num_cached_tokens` is populated [U: field name from memory, confirm]**.

---

## 4. Agent benchmarks: feasibility for ~1,000-3,000 API calls

| Benchmark | ID | Shape | Feasible at workshop budget? |
|---|---|---|---|
| tau-bench (retail 115 tasks, airline 50) | 2406.12045 [V], ICLR 2025 | Simulated user + tools, 10-30 agent turns/task, pass^k | Yes with a cheap model; retail subset of 50 tasks x 4 layouts = 200 episodes ~ 3-6k calls incl. user-sim. Public cost reports: ~$0.6/task with frontier agent+user. Use a small user-sim model. |
| tau2-bench (retail, airline, telecom 114) | 2506.07982 [V] | Dual-control; adds telecom | Same as tau-bench; telecom is harder, use retail. |
| BFCL v3 multi-turn (base / miss-func / miss-param / long-context, 200 each) | gorilla.cs.berkeley.edu [D-search] | Executable multi-turn function calling; long-context category exists | **Best fit**: deterministic tools, no user-sim cost, state-based scoring, 200-task long-context split is tailor-made for stale/distractor layout tests. |
| ToolSandbox (Apple) | 2408.04682 [V] | Stateful tools + simulated user | Feasible; smaller community uptake. |
| AppWorld (750 tasks) | 2407.18901 [V] | Interactive coding over 9 apps, unit-test scoring | Costly (long code traces); a 30-task slice possible but not recommended. |
| LongMemEval_S (~115k tokens, 500 q) | 2410.10813 [V], ICLR 2025 | Chat-history QA with knowledge-update + abstention | Good for a single-call *layout* test (reorder sessions by relevance vs chronological), but each call is ~115k tokens: 500 q x 4 layouts = 2,000 calls x 115k = 230M input tokens; only affordable with caching and a sub-$0.15/MTok model, or on a 100-question subset. |
| LoCoMo | 2402.17753 [V], ACL 2024 | Very long multi-session conversations | Moderate; weaker on knowledge updates than LongMemEval. |
| MultiChallenge | 2501.17399 [V] | Multi-turn instruction retention, inference memory | Cheap (short contexts), but not tool-using. |
| RULER / HELMET / BABILong / NoLiMa | 2404.06654 / 2410.02694 / 2406.10149 / 2502.05167 [V] | Synthetic/long-context, position-controllable | Useful for a controlled single-call positional arm; not agentic. |
| MINT | 2309.10691 [V] | Multi-turn tools + feedback | Older; feasible. |
| AgentBench, WebArena, SWE-bench Lite/Verified, Spider 2.0 | 2308.03688 / -- / -- / 2411.07763 [V] | Heavy environments | Too costly or too noisy for $30; skip. |
| ALFWorld | -- | Text game, cheap, long horizons | Feasible and used by 2608.16370 for compression-cost study; no tools-schema realism. |

Recommendation: **BFCL v3 multi-turn (long-context + base splits) as the primary arm; tau2-bench retail subset as the secondary live arm; a 100-question LongMemEval_S slice as the single-call positional arm** if budget remains.

---

## 5. Cost / accuracy trade-off studies
- **AI Agents That Matter** (Kapoor, Stroebl, Siegel, Nadgir, Narayanan; 2407.01502 [V]; TMLR 2025): cost-controlled evaluation; Pareto frontier of accuracy vs inference cost; simple baselines match complex agents at up to 50x lower cost. The methodological anchor for reporting USD-per-success.
- **What Moves the Pareto Frontier in Tool-Using Agents?** (Simhadri; ACL 2026 SRW, aclanthology 2026.acl-srw.82 [D]): budgeted evaluation of ReAct variants on HotPotQA/FEVER/GSM8K with Gemini 2.5 Flash; sampling spends 3-5x tokens for small gains.
- **Budget-Aware Tool Use Enables Effective Agent Scaling** (Liu et al.; 2511.17006 [V]; COLM 2026): budget tracker plus BATS improve cost-performance scaling curves.
- **Stop Wasting Your Tokens** (2510.26585 [V]), **AgentTaxo** (ICLR 2025 workshop; [U] arXiv ID not checked): token-distribution analyses in multi-agent systems.
- **Beyond the Context Window** (2603.04814 [V]) and **Bouchard 2026 blog**: the only two sources that put *cached* pricing into an accuracy-vs-cost comparison; neither varies layout.
- **Cache-Aware Prompt Compression** (2607.15516 [V]): first API-side measurement of realistic hit rates (rho ~0.83 plateau) and of compression's negative ROI under caching.

Nobody reports **cost per correct task under measured cache hits as a function of context layout**.

---

## 6. Critical pre-emption check: what already exists, and what each does NOT do

Searched phrasings: "prompt caching accuracy tradeoff", "cache-friendly prompt ordering accuracy", "prefix caching vs reranking", "KV cache hit rate vs task success", "append-only context accuracy agents", "stable prefix accuracy degradation", "cache-aware prompt design evaluation", "prompt caching position bias", "does prompt caching hurt accuracy", "cache-optimized context", "context layout agent ablation cache", "prompt caching lost in the middle tension", "stable prefix dynamic suffix recency", "recitation / todo.md evaluation", "tool masking vs removal accuracy", "OpenHands condenser caching".

Found (closest first):
1. **Don't Break the Cache** (2601.06007): compares caching *strategies* (where breakpoints go, what to exclude) on a real agent benchmark across three providers with real cost. Does NOT measure task accuracy or vary information order; treats caching as output-neutral.
2. **TokenPilot** (2606.17016): names the sparsity-vs-cache-continuity trade-off and reports hit rate and cost. Does NOT run a controlled layout factorial, does NOT separate ordering from pruning, reports accuracy only as "competitive", open-source agent harness benchmarks (PinchBench, Claw-Eval) rather than standard ones.
3. **Cache-Aware Prompt Compression** (2607.15516): real Anthropic cache telemetry, tau-bench 50-task accuracy check, cost model. Does NOT test ordering/relevance-reordering or stale-content retention; compression only; single provider.
4. **CacheWeaver** (2606.19667): cache-aware *ordering* of retrieved evidence vs retrieval order, quality checked. Does NOT involve agents, multi-turn, stale observations, or API pricing; vLLM-only, single-turn RAG.
5. **Bouchard / Towards AI "Why We Stopped Compacting"** (Aug 2026 blog): full-history-with-caching vs compaction with measured memory recall, cost, TTFT, and a cached-price break-even. Does NOT vary order or position, is a blog on one tutor app, no public benchmark.
6. **Do RAG Systems Really Suffer From Positional Bias?** (2505.15561, EMNLP 2025): shows relevance-based reordering ~ random shuffle in realistic RAG. Does NOT consider agents, multi-turn history, stale tool outputs, or caching; it is the null-hypothesis paper you must beat or confirm.
7. **ContextPipe** (2609.00749): append-only vs optimized assembly on SWE-bench Pro subset; notes lower KV hit ratio. Does NOT report an accuracy-vs-cached-cost frontier; system paper.
8. **Less Context, Better Agents** (2606.10209), **Complexity Trap** (2508.21433), **Masking Stale Observations** (2606.00408), **What Does Context Compression Cost** (2608.16370): pruning/masking vs full history with accuracy. None accounts for cache hits or cache-priced cost; none tests order-only manipulations.
9. **Leyline / Irminsul / Request Order Matters** (2606.01065, 2605.05696, 2610.05833): serving-side fixes for the append-only constraint. Do NOT evaluate the API-level discipline practitioners actually follow.
10. **Manus / Anthropic / ProjectDiscovery** guidance: prescribe the layouts. No accuracy measurement at all.

No paper or blog was found that (a) holds content fixed and varies only layout, (b) in a multi-turn tool-using agent, (c) reports provider-reported cached tokens and USD, and (d) reports accuracy. The combination is open.

---

## 7. Practical confirmations
- OpenRouter: `usage.prompt_tokens_details.cached_tokens` (reads), `usage.prompt_tokens_details.cache_write_tokens`, `usage.cost` (always present now), `cache_discount` in body, `cost_details.upstream_inference_cost` only for BYOK. Caching providers via OpenRouter as of the fetched doc: Anthropic Claude (explicit `cache_control`, up to 4 breakpoints, also implicit), OpenAI (implicit >= 1,024 tokens; explicit breakpoints GPT-5.6+), Gemini 2.5+ (implicit 2,048/4,096 min; explicit cache_control honored as a single final breakpoint), DeepSeek (implicit), Groq Kimi K2, xAI Grok, Moonshot, Z.AI (implicit), Alibaba Qwen (explicit only). Use `session_id` to keep sticky routing deterministic; pin `provider.order` only if you accept losing sticky routing.
- Minimum cacheable prefix: Anthropic 512-4,096 depending on model (Haiku 4.5 is 4,096, which matters for a cheap arm); OpenAI 1,024; Gemini 2,048 (2.5) / 4,096 (3.x); DeepSeek none stated (64-token cache units). Design the stable prefix (system + tools) to exceed 4,096 tokens so every provider can cache it.
- vLLM: hit metrics exist as token counters at `/metrics`; per-request `cached_tokens` is gated by `--enable-prompt-tokens-details` and had a V1 bug; verify or diff counters. Modal arm is feasible.

---

## 8. Pre-emption verdict: ALIVE-BUT-CROWDED

Reasoning. The specific measurement is unclaimed, and the gap is recognizable from the literature itself: the systems papers (Sec. 2) prove non-prefix reuse costs accuracy and build fixes; the context-management papers (Sec. 3) prove pruning changes accuracy and cost but ignore caching; the one agent caching evaluation (2601.06007) ignores accuracy; the one RAG ordering-under-caching paper (2606.19667) ignores agents and pricing. However, the field is converging on exactly this intersection in 2026 (TokenPilot in June, CAPC in July, ContextPipe in September, Request Order Matters in October), so a 2027 submission must move quickly and be framed as a *measurement/frontier* paper, not a method paper. Two threats: (i) 2505.15561's finding that reordering does not matter in realistic RAG may generalize to agent histories, giving a null for the order-only arm (a publishable null if pre-registered, but weaker); (ii) a provider could release "position-independent" API caching (Irminsul/Leyline-style) that dissolves the constraint; cite these as motivation, not risk.

Five nearest works and what each does not do:
1. 2601.06007 Don't Break the Cache: no accuracy outcome; no layout/order manipulation.
2. 2606.17016 TokenPilot: method paper; no controlled factorial; order and pruning confounded; non-standard benchmarks.
3. 2607.15516 CAPC: compression only; no ordering or stale-retention arm; single provider; 50 tau-bench tasks.
4. 2606.19667 CacheWeaver: single-turn RAG on vLLM; no agents, no pricing, no stale observations.
5. 2505.15561 Do RAG Systems Really Suffer: RAG not agents; no caching; its null is a hypothesis to test in the agent setting.
(Runner-up: Bouchard 2026 blog; content not order; no public benchmark.)

---

## 9. Recommended sharpening

### 9.1 Problem statement (sharpened)
"Prompt caching rewards one specific context layout: a byte-stable prefix that is only ever appended to. We ask whether that layout, *holding the information content constant*, costs accuracy relative to layouts that re-rank, prune, or restate, and whether the cache discount pays for the loss. We report the first accuracy-vs-measured-cost frontier for context layouts in tool-using agents, using provider-reported cached-token counts and billed USD rather than modeled costs."

Key differentiators to state in the intro: (1) order-only manipulations separated from content manipulations (nobody has done this with caching); (2) real `cached_tokens`/`cache_read_input_tokens` and `usage.cost`, not price-sheet arithmetic; (3) a hybrid layout (L4) that is both cache-stable and recency-friendly, which is the practical recommendation if it dominates.

### 9.2 Factorial design (layout x task x model)
Layouts (content held fixed between L1, L2, L4; L3 is the content-changing control):
- **L1 Cache-optimal (append-only)**: tools + system first; every past turn and tool result kept verbatim in chronological order; newest observation and user message last; tools masked via `tool_choice`/allowed-tools rather than removed; no summaries.
- **L2 Relevance-reordered**: identical blocks, but prior tool results/observations re-sorted each turn by relevance to the current sub-goal (embedding similarity or a fixed heuristic), most relevant last (adjacent to the question). Prefix changes every turn, so cache reads should collapse.
- **L3 Pruned/compacted (accuracy-optimized)**: stale/superseded tool results dropped or replaced by placeholders (observation masking, Lindenbauer et al.), and/or periodic LLM summary. Changes content; the standard "context engineering" arm.
- **L4 Stable-prefix + recitation hybrid**: L1 prefix untouched, plus a short appended block each turn that restates the goal, the current state, and pointers to which earlier observations are current vs superseded (Manus "recitation" / R&R reprompting). Costs a few hundred extra uncached tokens per turn but keeps the prefix stable.
Optional L5: L1 with stale tool outputs explicitly *marked* ("[superseded by step 7]") in place, which preserves bytes of earlier blocks? No: it edits earlier blocks and breaks the prefix; keep only as a diagnostic if budget allows.

Tasks:
- T1: BFCL v3 multi-turn, long-context split (200) plus base split (200): deterministic, cheap, has stale-information pressure by construction.
- T2: tau2-bench retail subset (50 tasks), live, with a small user-simulator model; pass^1 and pass^2.
- T3 (optional, single-call): LongMemEval_S 100-question slice with "knowledge-update" and "abstention" categories over-sampled; layouts = chronological (cache-optimal) vs relevance-sorted sessions vs pruned-to-top-k sessions vs chronological + question repeated at both ends.

Models (3, chosen so each has caching through OpenRouter and a low price): one Anthropic Haiku-class (explicit cache_control, 0.1x reads), one OpenAI mini/nano-class (implicit), one Gemini Flash-class or DeepSeek (implicit, cheapest reads). Add a Modal vLLM open-weight arm (e.g., a Qwen3 8B-30B) for mechanism checks (attention to stale blocks) if GPU credits exist; measure hits from `/metrics`.

Budget sketch at $30: approximate per-episode input volume = sum over turns of prompt length; for BFCL long-context, ~15 turns x ~8k tokens = ~120k input tokens/episode. 400 tasks x 4 layouts = 1,600 episodes = ~190M input tokens per model, too much for all three models at uncached prices. Make it fit: (a) run the full 4-layout factorial on 100 BFCL tasks (50 long-context + 50 base) on one cheap model (~48M tokens; at $0.10-0.40/MTok uncached, L1/L4 will be mostly cached so expect $5-12), (b) replicate L1 vs L3 vs L4 on the second and third models on 50 tasks each (~$8-12), (c) tau2 retail 30 tasks x L1/L3/L4 on the cheapest model (~$5). Confirm current list prices at run time; the numbers above are order-of-magnitude. Use OpenRouter `usage.cost` as the ground-truth spend and stop at $28.

### 9.3 Measurement
- Per call: `prompt_tokens`, `prompt_tokens_details.cached_tokens`, `cache_write_tokens`, `completion_tokens`, `usage.cost`, provider id, latency. Derive cache-read fraction = cached_tokens / prompt_tokens, cumulative USD per episode, USD per correct task, and per-layout Pareto frontier (Kapoor et al. style).
- Warm-cache protocol: run turns sequentially within a 5-minute window; log any cache miss on a prefix that was previously written (provider-side eviction) and exclude or flag it. Use `session_id` on OpenRouter to hold sticky routing.
- Accuracy: BFCL state-match; tau2 pass^k; LongMemEval judged accuracy with the official judge prompt. Pre-register per-turn "stale-trap" annotations (turns where an earlier observation has been superseded) to test H1 at the step level.
- Mechanism (optional, open-weight arm): attention mass on superseded vs current tool-result blocks under L1 vs L4.

### 9.4 Pre-registrable directional hypotheses
- H1 (stale-retention cost): L1 accuracy < L3 accuracy on stale-trap steps, with the gap increasing with trajectory length; on non-trap steps the gap is not significant.
- H2 (order-only effect is small): L2 does not significantly beat L1 in accuracy (consistent with 2505.15561) but drops cache-read fraction below 20% and raises USD/task by >= 3x at 0.1x read pricing, so L2 is dominated on the frontier.
- H3 (hybrid dominates): L4 recovers >= 50% of the L1-to-L3 accuracy gap while retaining >= 80% of L1's cache-read fraction, placing it on or inside the frontier for all three models.
- H4 (model-dependence): the L1-vs-L3 accuracy gap shrinks with model capability (per Masking Stale Observations and Context Rot), so the "confusion" cost is largest for the cheapest models, which are exactly the ones for which caching saves the least absolute USD.
- H5 (price-threshold): the layout that minimizes USD-per-correct flips from L3 to L1/L4 when the cache-read price falls below a threshold; estimate it per model and compare to the Bouchard $0.55/MTok break-even and the 2603.04814 break-even.

### 9.5 Framing and threats to validity to pre-empt
- Provider caching is best-effort (DeepSeek, Gemini); report observed hit rates, not assumed ones, and show the distribution.
- Anthropic's 20-block lookback and 4-breakpoint limit can silently break L1 in long episodes; place breakpoints at tools/system and at the last tool_result, and log misses.
- tau-bench user simulators add noise; keep the simulator fixed and cheap, and report pass^2.
- Make clear that caching itself is output-neutral (Anthropic docs say so); the paper is about the *layout discipline*, not the cache.

---

## 10. Candidate references (28 verified + a few flagged)

Positional / long-context
1. Liu et al., Lost in the Middle, arXiv 2307.03172 (TACL 2024) [V]
2. Hsieh et al., Found in the Middle: Calibrating Positional Attention Bias, arXiv 2406.16008 (ACL 2024 Findings) [V]
3. Zhang et al., Found in the Middle: Plug-and-Play Positional Encoding (Ms-PoE), arXiv 2403.04797 [V]
4. An et al., Make Your LLM Fully Utilize the Context, arXiv 2404.16811 (NeurIPS 2024) [V]
5. Cuconasu et al., The Power of Noise, arXiv 2401.14887 (SIGIR 2024) [V]
6. Cuconasu et al., Do RAG Systems Really Suffer From Positional Bias?, arXiv 2505.15561 (EMNLP 2025) [V]
7. Jin et al., Long-Context LLMs Meet RAG, arXiv 2410.05983 [V]
8. Byerly & Khashabi, GOLD PANNING, arXiv 2510.09770 [V]
9. Liu et al., Lost at the End (primacy bias, multimodal RAG), arXiv 2606.16494 [V]
10. Liu et al., Instruction Position Matters in Sequence Generation, arXiv 2308.12097 (ACL 2024 Findings) [V]
11. Agrawal et al., R&R: reprompting for long documents, arXiv 2403.05004 (EMNLP 2024 Findings) [V]
12. Pal et al., Giraffe (question-first vs question-last), arXiv 2308.10882 [V]
13. Hong, Troynikov, Huber, Context Rot, trychroma.com/research/context-rot (Jul 2025) [D]
14. Modarressi et al., NoLiMa, arXiv 2502.05167 [V]
15. Faghih et al., Tool Preferences in Agentic LLMs are Unreliable, arXiv 2505.18135 [V]
16. Zhang et al., Masking Stale Observations Helps Search Agents -- Until It Doesn't, arXiv 2606.00408 [V]
17. Liu, Fang, Qian, When Agent Context Goes Stale, arXiv 2610.05281 [V]

Caching systems
18. Gim et al., Prompt Cache, arXiv 2311.04934 (MLSys 2024) [V]
19. Zheng et al., SGLang / RadixAttention, arXiv 2312.07104 (NeurIPS 2024) [V]
20. Jin et al., RAGCache, arXiv 2404.12457 [V]
21. Yao et al., CacheBlend, arXiv 2405.16444 (EuroSys 2025) [V]
22. Hu et al., EPIC, arXiv 2410.15332 (ICML 2025) [V]
23. Ma et al., Block-Attention, arXiv 2409.15355 (ICLR 2025) [V]
24. Yang, Chen, Chen, APE, arXiv 2502.05431 (ICLR 2025) [V]
25. Agarwal et al., Cache-Craft, arXiv 2502.15734 (SIGMOD 2025) [V]
26. Yang et al., KVLink, arXiv 2502.16002 (NeurIPS 2025) [V]
27. Zhao et al., MPIC, arXiv 2502.01960 [V]
28. Ma, Eitzinger, Koestler, Irminsul, arXiv 2605.05696 [V]; Leyline, arXiv 2606.01065 [V]
29. Gu et al., Request Order Matters, arXiv 2610.05833 [V]
30. Bai & Eisner, Prompt Choreography, arXiv 2512.23049 (TACL) [V]
31. Tan, Gu, Li, CacheWeaver, arXiv 2606.19667 [V]

Context engineering / caching evaluations
32. Lumer et al., Don't Break the Cache, arXiv 2601.06007 [V]
33. Xu et al., TokenPilot, arXiv 2606.17016 [V]
34. Song, Cache-Aware Prompt Compression, arXiv 2607.15516 [V]
35. Xu et al., ContextPipe, arXiv 2609.00749 [V]
36. Zha et al., CacheRouter, arXiv 2608.22708 [V]
37. Lindenbauer et al., The Complexity Trap, arXiv 2508.21433 (DL4C @ NeurIPS 2025) [V]
38. Lodha et al., Less Context, Better Agents, arXiv 2606.10209 [V]
39. Liu, What Does Context Compression Cost an Agent?, arXiv 2608.16370 [V]
40. Nguyen et al., CliffCompaction, arXiv 2609.26779 [V]
41. Pollertlam & Kornsuwannawit, Beyond the Context Window, arXiv 2603.04814 [V]
42. Ji (Manus), Context Engineering for AI Agents: Lessons from Building Manus, manus.im blog, Jul 18 2025 [D]
43. Anthropic, Effective context engineering for AI agents, anthropic.com engineering blog, Sep 2025 [search-verified; not fetched]
44. Bouchard, Context Engineering in 2026: Why We Stopped Compacting Our Agent's Context, louisbouchard.ai, Aug 18 2026 [D]
45. Sadani & Kumar, Tool Attention Is All You Need, arXiv 2604.21816 [V] (note: success numbers are projections)

Cost-aware evaluation
46. Kapoor et al., AI Agents That Matter, arXiv 2407.01502 (TMLR 2025) [V]
47. Simhadri, What Moves the Pareto Frontier in Tool-Using Agents?, ACL 2026 SRW, aclanthology 2026.acl-srw.82 [D]
48. Liu et al., Budget-Aware Tool Use Enables Effective Agent Scaling, arXiv 2511.17006 (COLM 2026) [V]

Benchmarks
49. Yao et al., tau-bench, arXiv 2406.12045 (ICLR 2025) [V]; Barres et al., tau2-bench, arXiv 2506.07982 [V]
50. BFCL v3 multi-turn, gorilla.cs.berkeley.edu/leaderboard (800 multi-turn tasks, 200 long-context) [search-verified]
51. Wu et al., LongMemEval, arXiv 2410.10813 (ICLR 2025) [V]
52. Lu et al., ToolSandbox, arXiv 2408.04682 [V]; Trivedi et al., AppWorld, arXiv 2407.18901 [V]
53. Sirdeshmukh et al., MultiChallenge, arXiv 2501.17399 [V]
54. Hsieh et al., RULER, arXiv 2404.06654 [V]; Yen et al., HELMET, arXiv 2410.02694 [V]; Kuratov et al., BABILong, arXiv 2406.10149 [V]; Maharana et al., LoCoMo, arXiv 2402.17753 [V]

Vendor docs (fetched 2026-10-10) [D]
55. platform.claude.com/en/docs/build-with-claude/prompt-caching
56. developers.openai.com/api/docs/guides/prompt-caching
57. ai.google.dev/gemini-api/docs/caching
58. api-docs.deepseek.com/guides/kv_cache and /quick_start/pricing
59. openrouter.ai/docs/guides/best-practices/prompt-caching and /docs/use-cases/usage-accounting
60. docs.vllm.ai/en/latest/design/metrics/ ; vLLM GitHub issue #16162 (prompt_tokens_details null on V1)

Unverified / flagged
- ReFold (2610.07863), Persistent Context Graphs (2609.40118), Slipstream (2605.08580 [V] title only), Self-Compacting LM Agents (2606.23525 [V] title only), SemPIC (2607.28069 [V] title only): titles seen; abstracts not read.
- AgentTaxo (ICLR 2025 workshop): arXiv ID not checked [U].
- ProjectDiscovery "7% to 84%" case: only secondary blog coverage found; primary post not located [U].
- "Order Matters RAG" as a paper title: no paper with that exact title was found; the ordering literature is covered by refs 5-8 above.
- vLLM `RequestOutput.num_cached_tokens`: field name from memory, confirm in the deployed version [U].
- The fetched Anthropic and OpenRouter pages list model names (e.g., Opus 5.5, GPT-5.6) and multipliers as of 2026-10-10; re-fetch before quoting in the paper.
