# Verification of section-10 references in 00_preemption_sweep_2026-10-10.md

Run date: 2026-10-10. Script: `lit_review/verify_refs.py` (arXiv API in batches of 25, abs-page fallback). Verdict OK means the API title matches the sweep's stated title (nickname expansions accepted); PROBLEM means a different paper or the id was not returned.

## arXiv ids

| id | sweep title | API title | verdict |
|---|---|---|---|
| 2307.03172 | Lost in the Middle | lost in the middle: how language models use long contexts | OK |
| 2406.16008 | Found in the Middle: Calibrating Positional Attention Bias | found in the middle: calibrating positional attention bias improves long context utilization | OK |
| 2403.04797 | Found in the Middle: Plug-and-Play Positional Encoding (Ms-PoE) | found in the middle: how language models use long contexts better via plug-and-play positional encoding | OK |
| 2404.16811 | Make Your LLM Fully Utilize the Context | make your llm fully utilize the context | OK |
| 2401.14887 | The Power of Noise | the power of noise: redefining retrieval for rag systems | OK |
| 2505.15561 | Do RAG Systems Really Suffer From Positional Bias? | do rag systems really suffer from positional bias? | OK |
| 2410.05983 | Long-Context LLMs Meet RAG | long-context llms meet rag: overcoming challenges for long inputs in rag | OK |
| 2510.09770 | GOLD PANNING | gold panning: strategic context shuffling for needle-in-haystack reasoning | OK |
| 2606.16494 | Lost at the End (primacy bias, multimodal RAG) | lost at the end: primacy bias in multimodal retrieval-augmented question answering | OK |
| 2308.12097 | Instruction Position Matters in Sequence Generation | instruction position matters in sequence generation with large language models | OK |
| 2403.05004 | R&R: reprompting for long documents | can't remember details in long documents? you need some r&r | OK |
| 2308.10882 | Giraffe (question-first vs question-last) | giraffe: adventures in expanding context lengths in llms | OK |
| 2502.05167 | NoLiMa | nolima: long-context evaluation beyond literal matching | OK |
| 2505.18135 | Tool Preferences in Agentic LLMs are Unreliable | tool preferences in agentic llms are unreliable | OK |
| 2606.00408 | Masking Stale Observations Helps Search Agents -- Until It Doesn't | masking stale observations helps search agents -- until it doesn't: a regime map and its mechanism | OK |
| 2610.05281 | When Agent Context Goes Stale | when agent context goes stale: incoherence in volatile agent context | OK |
| 2311.04934 | Prompt Cache | prompt cache: modular attention reuse for low-latency inference | OK |
| 2312.07104 | SGLang / RadixAttention | sglang: efficient execution of structured language model programs | OK |
| 2404.12457 | RAGCache | ragcache: efficient knowledge caching for retrieval-augmented generation | OK |
| 2405.16444 | CacheBlend | cacheblend: fast large language model serving for rag with cached knowledge fusion | OK |
| 2410.15332 | EPIC | epic: efficient position-independent caching for serving large language models | OK |
| 2409.15355 | Block-Attention | block-attention for efficient prefilling | OK |
| 2502.05431 | APE | ape: faster and longer context-augmented generation via adaptive parallel encoding | OK |
| 2502.15734 | Cache-Craft | cache-craft: managing chunk-caches for efficient retrieval-augmented generation | OK |
| 2502.16002 | KVLink | kvlink: accelerating large language models via efficient kv cache reuse | OK |
| 2502.01960 | MPIC | mpic: position-independent multimodal context caching system for efficient mllm serving | OK |
| 2605.05696 | Irminsul | irminsul: mla-native position-independent caching for agentic llm serving | OK |
| 2606.01065 | Leyline | leyline: kv cache directives for agentic inference | OK |
| 2610.05833 | Request Order Matters | request order matters: cache-history sensitivity in selective kv-cache reuse for rolling agents | OK |
| 2512.23049 | Prompt Choreography | accelerating language model workflows with prompt choreography | OK |
| 2606.19667 | CacheWeaver | cacheweaver: cache-aware evidence ordering for efficient grounded rag inference | OK |
| 2601.06007 | Don't Break the Cache | don't break the cache: an evaluation of prompt caching for long-horizon agentic tasks | OK |
| 2606.17016 | TokenPilot | tokenpilot: cache-efficient context management for llm agents | OK |
| 2607.15516 | Cache-Aware Prompt Compression | cache-aware prompt compression:a two-tier cost model for llm api caching | OK |
| 2609.00749 | ContextPipe | contextpipe: database-inspired context assembly for long-horizon agents | OK |
| 2608.22708 | CacheRouter | cacherouter: a dual-path tool routing architecture with cache-preserving main-model isolation for long-tail tool discovery | OK |
| 2508.21433 | The Complexity Trap | the complexity trap: simple observation masking is as efficient as llm summarization for agent context management | OK |
| 2606.10209 | Less Context, Better Agents | less context, better agents: efficient context engineering for long-horizon tool-using llm agents | OK |
| 2608.16370 | What Does Context Compression Cost an Agent? | what does context compression cost an agent? interaction costs unrevealed by task-completion metrics | OK |
| 2609.26779 | CliffCompaction | cliffcompaction: cost-efficient compaction for long-horizon coding agents | OK |
| 2603.04814 | Beyond the Context Window | beyond the context window: a cost-performance analysis of fact-based memory vs. long-context llms for persistent agents | OK |
| 2604.21816 | Tool Attention Is All You Need | tool attention is all you need: dynamic tool gating and lazy schema loading for eliminating the mcp/tools tax in scalable agentic workflows | OK |
| 2407.01502 | AI Agents That Matter | ai agents that matter | OK |
| 2511.17006 | Budget-Aware Tool Use Enables Effective Agent Scaling | budget-aware tool use enables effective agent scaling | OK |
| 2406.12045 | tau-bench | tau-bench: a benchmark for tool-agent-user interaction in real-world domains | OK |
| 2506.07982 | tau2-bench | tau2-bench: evaluating conversational agents in a dual-control environment | OK |
| 2410.10813 | LongMemEval | longmemeval: benchmarking chat assistants on long-term interactive memory | OK |
| 2408.04682 | ToolSandbox | toolsandbox: a stateful, conversational, interactive evaluation benchmark for llm tool use capabilities | OK |
| 2407.18901 | AppWorld | appworld: a controllable world of apps and people for benchmarking interactive coding agents | OK |
| 2501.17399 | MultiChallenge | multichallenge: a realistic multi-turn conversation evaluation benchmark challenging to frontier llms | OK |
| 2404.06654 | RULER | ruler: what's the real context size of your long-context language models? | OK |
| 2410.02694 | HELMET | helmet: how to evaluate long-context language models effectively and thoroughly | OK |
| 2406.10149 | BABILong | babilong: testing the limits of llms with long context reasoning-in-a-haystack | OK |
| 2402.17753 | LoCoMo | evaluating very long-term conversational memory of llm agents | OK |
| 2610.07863 | ReFold | refold: training-free reversible inter-turn context folding for long-horizon agents | OK |
| 2609.40118 | Persistent Context Graphs | persistent context graphs for efficient memory compaction in llm agents | OK |
| 2605.08580 | Slipstream | slipstream: trajectory-grounded compaction validation for long-horizon agents | OK |
| 2606.23525 | Self-Compacting LM Agents | self-compacting language model agents | OK |
| 2607.28069 | SemPIC | sempic: learning semantic position-independent kv caches | OK |

**OK: 59  PROBLEM: 0**

## Non-arXiv items (not API-verifiable)

| sweep # | item | final URL | HTTP | date found on page |
|---|---|---|---|---|
| 13 | Hong, Troynikov, Huber, Context Rot (Chroma, Jul 2025) | https://www.trychroma.com/research/context-rot | 200 |  |
| 42 | Ji (Manus), Context Engineering for AI Agents: Lessons from Building Manus (Jul 18 2025) | https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus | 200 |  |
| 43 | Anthropic, Effective context engineering for AI agents (Sep 2025) | https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents | 200 | 2025-09-29 |
| 44 | Bouchard, Context Engineering in 2026: Why We Stopped Compacting Our Agent's Context (Aug 18 2026) | https://www.louisbouchard.ai/context-engineering-2026/ | 200 | 2026-08-18 |
| 47 | Simhadri, What Moves the Pareto Frontier in Tool-Using Agents? (ACL 2026 SRW) | https://aclanthology.org/2026.acl-srw.82/ | 200 |  |
| 50 | BFCL v3 multi-turn leaderboard | https://gorilla.cs.berkeley.edu/leaderboard.html | 200 |  |
| 55 | Anthropic prompt caching docs | https://platform.claude.com/docs/en/build-with-claude/prompt-caching | 200 |  |
| 56 | OpenAI prompt caching guide | https://developers.openai.com/api/docs/guides/prompt-caching | 200 |  |
| 57 | Gemini context caching docs | https://ai.google.dev/gemini-api/docs/caching | 200 |  |
| 58 | DeepSeek KV cache guide / pricing | https://api-docs.deepseek.com/guides/kv_cache/ | 200 |  |
| 59 | OpenRouter prompt caching / usage accounting | https://openrouter.ai/docs/guides/best-practices/prompt-caching | 200 |  |
| 60 | vLLM metrics design doc / issue #16162 | https://docs.vllm.ai/en/latest/design/metrics/ | 200 |  |

Also non-arXiv in section 10: DeepSeek pricing page (api-docs.deepseek.com/quick_start/pricing), OpenRouter usage-accounting page (openrouter.ai/docs/use-cases/usage-accounting), vLLM GitHub issue #16162, AgentTaxo (ICLR 2025 workshop, no arXiv id given), ProjectDiscovery 7%-to-84% anecdote (primary post not located).

Notes on the three blog posts (fetched 2026-10-10, all HTTP 200): Manus post title confirmed on page ("Context Engineering for AI Agents: Lessons from Building Manus"); the page exposes no machine-readable date, the byline date is Jul 18 2025 (as stated in the sweep). Anthropic post published 2025-09-29 (article:published_time). Bouchard post published 2026-08-18 (article:published_time); page title "Context Engineering in 2026: Why We Stopped Compacting Our...". The arXiv batch API returned HTTP 429 on some runs; the abs-page fallback produced identical titles, and the final run used the API for all 59 ids.
