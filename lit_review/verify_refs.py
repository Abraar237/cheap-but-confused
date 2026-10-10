#!/usr/bin/env python3
"""Verify the arXiv ids listed in section 10 of lit_review/00_preemption_sweep_2026-10-10.md
against the arXiv API and write sweep_refs_verified.csv + sweep_refs_verification.md.

Usage:  python3 lit_review/verify_refs.py          (run from the project root)

Method: batches of <=25 ids to https://export.arxiv.org/api/query, 3 s sleep between
batches. If a batch fails (HTTP error / empty feed / rate-limit), each id in that batch is
fetched one by one from https://arxiv.org/abs/<id> with 2 s sleeps. Titles are compared to
the sweep's stated title with a normalized fuzzy match plus per-entry keyword aliases
(so nickname expansions such as "SGLang / RadixAttention" pass but a different paper fails).
"""
import csv, difflib, html, re, sys, time, urllib.request, urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent
API = "https://export.arxiv.org/api/query?id_list={ids}&max_results=50"
ABS = "https://arxiv.org/abs/{id}"
UA = {"User-Agent": "sweep-ref-verifier/1.0 (research lit review; python-urllib)"}

# (arxiv_id, sweep_title, [alias keywords that must all appear in the API title], angle, relation_to_ours)
# angle in {positional, caching_systems, context_engineering, cost_eval, benchmarks}
REFS = [
 # ---- Positional / long-context (sweep refs 1-17) ----
 ("2307.03172","Lost in the Middle",["lost in the middle"],"positional","Canonical primacy/recency (U-shaped) citation for position of relevant info in long context"),
 ("2406.16008","Found in the Middle: Calibrating Positional Attention Bias",["found in the middle","calibrat"],"positional","Lost-in-the-middle is an attention-level artifact; calibration improves RAG up to ~15 pts"),
 ("2403.04797","Found in the Middle: Plug-and-Play Positional Encoding (Ms-PoE)",["found in the middle","positional encoding"],"positional","Ms-PoE positional-encoding fix for middle penalty; same nickname as 2406.16008, cite both carefully"),
 ("2404.16811","Make Your LLM Fully Utilize the Context",["fully utilize the context"],"positional","IN2 training removes lost-in-the-middle; effect magnitude is model-dependent (H4)"),
 ("2401.14887","The Power of Noise",["power of noise"],"positional","Gold must sit near the query; related distractors hurt most; core citation for gold-vs-question position"),
 ("2505.15561","Do RAG Systems Really Suffer From Positional Bias?",["positional bias"],"positional","Strongest counter-argument: relevance reordering no better than shuffling in realistic RAG; must be addressed"),
 ("2410.05983","Long-Context LLMs Meet RAG",["long-context","rag"],"positional","Retrieval reordering (top passages at extremes) helps; hard negatives hurt; pro-reordering evidence"),
 ("2510.09770","GOLD PANNING",["gold panning"],"positional","Exploits positional bias as a control signal; ordering is a live lever on 2025 models"),
 ("2606.16494","Lost at the End (primacy bias, multimodal RAG)",["lost at the end"],"positional","Primacy (not U-shaped) bias in multimodal RAG; direction of bias is model-family dependent"),
 ("2308.12097","Instruction Position Matters in Sequence Generation",["instruction position"],"positional","Post-instruction placement beats pre-instruction, especially for long inputs"),
 ("2403.05004","R&R: reprompting for long documents",["r&r"],"positional","Reprompting (restating the instruction) improves long-doc QA ~16 pts; direct precedent for the L4 recitation hybrid"),
 ("2308.10882","Giraffe (question-first vs question-last)",["giraffe"],"positional","Question-last beats question-first across context lengths on FreeFormQA"),
 ("2502.05167","NoLiMa",["nolima"],"positional","Long-context degradation without lexical overlap; degradation is about associative retrieval, not just length"),
 ("2505.18135","Tool Preferences in Agentic LLMs are Unreliable",["tool preferences"],"positional","First-listed tool is selected more; agent-side analogue of position bias (tools first, never reordered)"),
 ("2606.00408","Masking Stale Observations Helps Search Agents -- Until It Doesn't",["masking stale observations"],"positional","Regime map for masking old observations across model sizes; no caching/cost analysis; predicts model-dependence"),
 ("2610.05281","When Agent Context Goes Stale",["context goes stale"],"positional","Agents answer from stale tool observations; supports the stale-outputs-kept-for-cache risk; runtime fix, not layout study"),
 # ---- Caching systems (sweep refs 18-31) ----
 ("2311.04934","Prompt Cache",["prompt cache"],"caching_systems","Modular KV reuse via schema at different positions; quality roughly preserved"),
 ("2312.07104","SGLang / RadixAttention",["sglang"],"caching_systems","Radix-tree exact-prefix KV sharing; the open-source exact-prefix caching baseline"),
 ("2404.12457","RAGCache",["ragcache"],"caching_systems","Knowledge-tree KV cache for retrieved docs; exact-prefix reuse, notes order sensitivity"),
 ("2405.16444","CacheBlend",["cacheblend"],"caching_systems","Fuse independently cached chunk KVs with selective recompute; later work shows history-sensitivity"),
 ("2410.15332","EPIC",["position-independent"],"caching_systems","Position-independent caching with LegoLink; up to 8x TTFT with small accuracy loss"),
 ("2409.15355","Block-Attention",["block-attention"],"caching_systems","Encode retrieved blocks independently for any-order reuse; needs fine-tuning to hold accuracy"),
 ("2502.05431","APE",["parallel encoding"],"caching_systems","Adaptive parallel encoding preserving ~98% of sequential-encoding accuracy"),
 ("2502.15734","Cache-Craft",["cache-craft"],"caching_systems","Chunk-cache management for RAG; naive reuse degrades quality; 51% less compute vs prefix caching"),
 ("2502.16002","KVLink",["kvlink"],"caching_systems","Independent encoding costs up to 35% relative QA accuracy; link tokens recover it"),
 ("2502.01960","MPIC",["position-independent"],"caching_systems","Multimodal position-independent context caching with reuse-recompute mixing"),
 ("2605.05696","Irminsul",["irminsul"],"caching_systems","Content-addressed MLA caching on agentic traffic; documents the agent shifted-position problem"),
 ("2606.01065","Leyline",["leyline"],"caching_systems","Serving-side KV directives for edited agent contexts; argues append-only is a serving limitation; closest serving-side cousin"),
 ("2610.05833","Request Order Matters",["request order matters"],"caching_systems","Selective KV reuse for rolling agents gives history-dependent answers (69% to 26% variation)"),
 ("2512.23049","Prompt Choreography",["prompt choreography"],"caching_systems","Global KV cache attending to reordered subsets of prior messages; fine-tunes to close the re-encoding gap"),
 ("2606.19667","CacheWeaver",["cacheweaver"],"caching_systems","Reorder retrieved evidence to maximize prefix reuse; single-turn RAG, no agents, no API cost; nearest RAG-side neighbor"),
 # ---- Context engineering / caching evaluations (sweep refs 32-45) ----
 ("2601.06007","Don't Break the Cache",["break the cache"],"context_engineering","Caching strategies for long-horizon agents across OpenAI/Anthropic/Google; cost and TTFT only, no accuracy"),
 ("2606.17016","TokenPilot",["tokenpilot"],"context_engineering","Names the text-sparsity vs prompt-cache-continuity trade-off; a system, does not isolate ordering from pruning; nearest agent-side neighbor"),
 ("2607.15516","Cache-Aware Prompt Compression",["cache-aware prompt compression"],"context_engineering","Two-tier caching-vs-compression cost model on Anthropic API with tau-bench check; no reordering arm; nearest API-side neighbor"),
 ("2609.00749","ContextPipe",["contextpipe"],"context_engineering","Append-only vs cache-aware context assembly on SWE-bench Pro; confirms trade-off as a side-effect, not an accuracy frontier"),
 ("2608.22708","CacheRouter",["cacherouter"],"context_engineering","Dual-path tool routing keeping the tool prefix fixed; 91-95% cache hit; cost only"),
 ("2508.21433","The Complexity Trap",["complexity trap"],"context_engineering","Observation masking matches LLM summarization at half the cost on SWE-bench; no prompt-caching accounting"),
 ("2606.10209","Less Context, Better Agents",["less context"],"context_engineering","Pruning to last 5 tool pairs beats full history (79% vs 71%) on MCP tasks; no cache hit or USD cost"),
 ("2608.16370","What Does Context Compression Cost an Agent?",["context compression cost"],"context_engineering","Compression keeps completion but triples retrieval calls (hidden interaction cost); no caching"),
 ("2609.26779","CliffCompaction",["cliffcompaction"],"context_engineering","Compaction method; not a controlled layout-vs-accuracy-vs-cached-cost study"),
 ("2603.04814","Beyond the Context Window",["beyond the context window"],"context_engineering","Memory vs long-context with a caching-aware cost model; memory architecture, not layout"),
 ("2604.21816","Tool Attention Is All You Need",["tool attention"],"context_engineering","Tool gating / lazy schema loading; success numbers are projections; mask-vs-remove remains open"),
 # ---- Cost-aware evaluation (sweep refs 46-48) ----
 ("2407.01502","AI Agents That Matter",["agents that matter"],"cost_eval","Cost-controlled evaluation and accuracy-vs-cost Pareto frontier; methodological anchor for USD-per-success"),
 ("2511.17006","Budget-Aware Tool Use Enables Effective Agent Scaling",["budget-aware tool use"],"cost_eval","Budget tracker plus BATS improve cost-performance scaling curves"),
 # ---- Benchmarks (sweep refs 49-54) ----
 ("2406.12045","tau-bench",["tau-bench"],"benchmarks","Simulated-user tool-agent benchmark; retail subset is the secondary live arm"),
 ("2506.07982","tau2-bench",["tau"],"benchmarks","Dual-control successor to tau-bench; adds telecom; use retail"),
 ("2410.10813","LongMemEval",["longmemeval"],"benchmarks","Chat-history QA with knowledge-update and abstention; single-call layout arm candidate"),
 ("2408.04682","ToolSandbox",["toolsandbox"],"benchmarks","Stateful tools plus simulated user; feasible, smaller uptake"),
 ("2407.18901","AppWorld",["appworld"],"benchmarks","Interactive coding over 9 apps; costly, not recommended at workshop budget"),
 ("2501.17399","MultiChallenge",["multichallenge"],"benchmarks","Multi-turn instruction retention; cheap but not tool-using"),
 ("2404.06654","RULER",["ruler"],"benchmarks","Synthetic long-context, position-controllable; single-call positional arm"),
 ("2410.02694","HELMET",["helmet"],"benchmarks","Long-context evaluation suite; single-call positional arm"),
 ("2406.10149","BABILong",["babilong"],"benchmarks","Long-context reasoning benchmark; single-call positional arm"),
 ("2402.17753","LoCoMo",["long-term","conversation"],"benchmarks","Very long multi-session conversations; weaker on knowledge updates than LongMemEval"),
 # ---- Unverified / flagged block in section 10 (titles seen, abstracts not read) ----
 ("2610.07863","ReFold",["refold"],"context_engineering","Flagged in sweep as title-only, not API-verified; compaction method"),
 ("2609.40118","Persistent Context Graphs",["persistent context graph"],"context_engineering","Flagged in sweep as [U]; compaction/memory method"),
 ("2605.08580","Slipstream",["slipstream"],"context_engineering","Flagged title-only; compaction method"),
 ("2606.23525","Self-Compacting LM Agents",["self-compacting"],"context_engineering","Flagged title-only; compaction method"),
 ("2607.28069","SemPIC",["sempic"],"caching_systems","Flagged title-only; learned semantic position-independent KV caches"),
]

NON_ARXIV = [
 ("13","Hong, Troynikov, Huber, Context Rot (Chroma, Jul 2025)","https://www.trychroma.com/research/context-rot"),
 ("42","Ji (Manus), Context Engineering for AI Agents: Lessons from Building Manus (Jul 18 2025)","https://manus.im/blog/Context-Engineering-for-AI-Agents-Lessons-from-Building-Manus"),
 ("43","Anthropic, Effective context engineering for AI agents (Sep 2025)","https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents"),
 ("44","Bouchard, Context Engineering in 2026: Why We Stopped Compacting Our Agent's Context (Aug 18 2026)","BOUCHARD_URL"),
 ("47","Simhadri, What Moves the Pareto Frontier in Tool-Using Agents? (ACL 2026 SRW)","https://aclanthology.org/2026.acl-srw.82/"),
 ("50","BFCL v3 multi-turn leaderboard","https://gorilla.cs.berkeley.edu/leaderboard.html"),
 ("55","Anthropic prompt caching docs","https://platform.claude.com/en/docs/build-with-claude/prompt-caching"),
 ("56","OpenAI prompt caching guide","https://developers.openai.com/api/docs/guides/prompt-caching"),
 ("57","Gemini context caching docs","https://ai.google.dev/gemini-api/docs/caching"),
 ("58","DeepSeek KV cache guide / pricing","https://api-docs.deepseek.com/guides/kv_cache"),
 ("59","OpenRouter prompt caching / usage accounting","https://openrouter.ai/docs/guides/best-practices/prompt-caching"),
 ("60","vLLM metrics design doc / issue #16162","https://docs.vllm.ai/en/latest/design/metrics/"),
]
# Pass the resolved Bouchard URL on the command line if known: python3 verify_refs.py <bouchard_url>
if len(sys.argv) > 1:
    NON_ARXIV = [(n, t, (sys.argv[1] if u == "BOUCHARD_URL" else u)) for n, t, u in NON_ARXIV]

NOTE = 'Notes on the three blog posts (fetched 2026-10-10, all HTTP 200): Manus post title confirmed on page ("Context Engineering for AI Agents: Lessons from Building Manus"); the page exposes no machine-readable date, the byline date is Jul 18 2025 (as stated in the sweep). Anthropic post published 2025-09-29 (article:published_time). Bouchard post published 2026-08-18 (article:published_time); page title "Context Engineering in 2026: Why We Stopped Compacting Our...". The arXiv batch API returned HTTP 429 on some runs; the abs-page fallback produced identical titles, and the final run used the API for all 59 ids.'

NS = {"a": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}

def norm(s):
    s = html.unescape(s).lower()
    # arXiv renders Greek letters as LaTeX: "$\\tau^2$-bench" -> "tau2-bench"
    s = re.sub(r"\$\\\\?([a-z]+)\^?\{?([0-9]*)\}?\$", r"\1\2", s)
    s = s.replace("$", "").replace("\\", "")
    # the API path returns Unicode Greek instead ("τ^2-bench"): map letters to names, drop superscript markers
    for g, n in (("τ", "tau"), ("α", "alpha"), ("β", "beta"), ("λ", "lambda"), ("μ", "mu"), ("π", "pi"), ("σ", "sigma")):
        s = s.replace(g, n)
    s = re.sub(r"\^\{?([0-9]+)\}?", r"\1", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()

def person(name):
    """Return (surname, 'First Last') from either 'First Last' or 'Last, First' (abs-page meta)."""
    name = name.strip()
    if "," in name:
        last, first = [x.strip() for x in name.split(",", 1)]
        return last.title() if last.islower() else last, f"{first} {last}".strip()
    parts = name.split()
    return (parts[-1] if parts else ""), name

VENUE_WORDS = ("accept", "appear", "publish", "proceedings", "workshop", "findings", "camera", "iclr", "neurips", "nips",
               "icml", "acl", "emnlp", "naacl", "colm", "tacl", "mlsys", "sigmod", "eurosys", "sigir", "tmlr", "kdd",
               "osdi", "sosp", "aaai", "coling", "conference", "journal", "transactions")

def fetch(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.status, r.read().decode("utf-8", "replace")

def parse_feed(xml_text):
    out = {}
    root = ET.fromstring(xml_text)
    for e in root.findall("a:entry", NS):
        eid = e.findtext("a:id", "", NS)
        m = re.search(r"abs/([0-9]{4}\.[0-9]{4,5})", eid)
        if not m:
            continue  # arXiv returns an error entry for unknown ids
        title = norm(e.findtext("a:title", "", NS))
        authors = [html.unescape(a.findtext("a:name", "", NS)).strip() for a in e.findall("a:author", NS)]
        pub = e.findtext("a:published", "", NS)[:10]
        comment = norm(e.findtext("arxiv:comment", "", NS) or "")
        jref = norm(e.findtext("arxiv:journal_ref", "", NS) or "")
        out[m.group(1)] = dict(title=title, authors=authors, published=pub, comment=comment, journal_ref=jref, source="arxiv-api")
    return out

def parse_abs(html_text, aid):
    t = re.search(r'<meta name="citation_title" content="([^"]*)"', html_text)
    au = re.findall(r'<meta name="citation_author" content="([^"]*)"', html_text)
    d = re.search(r'<meta name="citation_date" content="([^"]*)"', html_text)
    if not t:
        return None
    pub = d.group(1).replace("/", "-") if d else ""
    cm = re.search(r'<td class="tablecell comments[^"]*">(.*?)</td>', html_text, re.S)
    jr = re.search(r'<td class="tablecell jref">(.*?)</td>', html_text, re.S)
    strip = lambda x: norm(re.sub(r"<[^>]+>", "", x.group(1))) if x else ""
    return dict(title=norm(t.group(1)), authors=[html.unescape(a).strip() for a in au], published=pub,
                comment=strip(cm), journal_ref=strip(jr), source="abs-page")

def title_ok(sweep_title, aliases, api_title):
    t = norm(api_title)
    if all(a.lower() in t for a in aliases):
        return True
    ratio = difflib.SequenceMatcher(None, norm(sweep_title), t).ratio()
    return ratio >= 0.6

def venue(meta):
    if meta["journal_ref"]:
        return meta["journal_ref"]
    c = meta["comment"]
    if c and any(w in c for w in VENUE_WORDS):
        return c
    return "preprint" if not c else f"preprint (comment: {c})"

def main():
    ids = [r[0] for r in REFS]
    meta = {}
    for i in range(0, len(ids), 25):
        batch = ids[i:i+25]
        try:
            status, body = fetch(API.format(ids=",".join(batch)))
            got = parse_feed(body)
            print(f"batch {i//25+1}: requested {len(batch)}, returned {len(got)}", file=sys.stderr)
            if not got:
                raise RuntimeError("empty feed (rate-limited?)")
            meta.update(got)
        except Exception as ex:
            print(f"batch {i//25+1} failed ({ex}); falling back to abs pages", file=sys.stderr)
        missing = [a for a in batch if a not in meta]
        for a in missing:
            try:
                time.sleep(2)
                _, h = fetch(ABS.format(id=a))
                m = parse_abs(h, a)
                if m:
                    meta[a] = m
                    print(f"  abs-page ok {a}", file=sys.stderr)
            except Exception as ex:
                print(f"  abs-page FAILED {a}: {ex}", file=sys.stderr)
        time.sleep(3)

    rows, table, ok, problem = [], [], 0, 0
    for aid, stitle, aliases, angle, rel in REFS:
        m = meta.get(aid)
        if not m:
            verdict = "MISMATCH: <not returned by arXiv API or abs page>"
            problem += 1
            rows.append([aid, "", "", "", "", "", angle, rel, verdict])
            table.append((aid, stitle, "(not found)", "PROBLEM: not found"))
            continue
        if title_ok(stitle, aliases, m["title"]):
            verified = m["source"]; ok += 1; verdict = "OK"
        else:
            verified = f"MISMATCH: {m['title']}"; problem += 1; verdict = "PROBLEM: different paper"
        people = [person(a) for a in m["authors"]]
        rows.append([aid, m["title"], people[0][0] if people else "",
                     "; ".join(p[1] for p in people), m["published"][:4], venue(m), angle, rel, verified])
        table.append((aid, stitle, m["title"], verdict))

    with open(ROOT / "sweep_refs_verified.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["arxiv_id","title","first_author","authors","year","venue_or_preprint","angle","relation_to_ours","verified"])
        w.writerows(rows)

    # Non-arXiv web sources: HEAD/GET and record final URL + status + any published date found.
    web = []
    for n, label, url in NON_ARXIV:
        if url == "BOUCHARD_URL":
            web.append((n, label, url, "not probed (URL unknown)", "")); continue
        try:
            req = urllib.request.Request(url, headers={**UA, "User-Agent": "Mozilla/5.0 (compatible; sweep-ref-verifier/1.0)"})
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read(400000).decode("utf-8", "replace")
                final, status = r.geturl(), r.status
            dm = (re.search(r'property="article:published_time" content="([^"]+)"', body)
                  or re.search(r'"datePublished":\s*"([^"]+)"', body)
                  or re.search(r'<time[^>]*datetime="([^"]+)"', body))
            date = dm.group(1)[:10] if dm else ""
            web.append((n, label, final, str(status), date))
        except urllib.error.HTTPError as ex:
            web.append((n, label, url, f"HTTP {ex.code}", ""))
        except Exception as ex:
            web.append((n, label, url, f"ERROR {type(ex).__name__}", ""))
        time.sleep(1)

    with open(ROOT / "sweep_refs_verification.md", "w") as f:
        f.write("# Verification of section-10 references in 00_preemption_sweep_2026-10-10.md\n\n")
        f.write(f"Run date: {time.strftime('%Y-%m-%d')}. Script: `lit_review/verify_refs.py` (arXiv API in batches of 25, abs-page fallback). "
                "Verdict OK means the API title matches the sweep's stated title (nickname expansions accepted); "
                "PROBLEM means a different paper or the id was not returned.\n\n")
        f.write("## arXiv ids\n\n| id | sweep title | API title | verdict |\n|---|---|---|---|\n")
        for aid, st, at, vd in table:
            f.write(f"| {aid} | {st} | {at} | {vd} |\n")
        f.write(f"\n**OK: {ok}  PROBLEM: {problem}**\n\n")
        f.write("## Non-arXiv items (not API-verifiable)\n\n| sweep # | item | final URL | HTTP | date found on page |\n|---|---|---|---|---|\n")
        for n, label, final, status, date in web:
            f.write(f"| {n} | {label} | {final} | {status} | {date} |\n")
        f.write("\nAlso non-arXiv in section 10: DeepSeek pricing page (api-docs.deepseek.com/quick_start/pricing), "
                "OpenRouter usage-accounting page (openrouter.ai/docs/use-cases/usage-accounting), vLLM GitHub issue #16162, "
                "AgentTaxo (ICLR 2025 workshop, no arXiv id given), ProjectDiscovery 7%-to-84% anecdote (primary post not located).\n")
        f.write("\n" + NOTE + "\n")
    print(f"OK: {ok}  PROBLEM: {problem}")
    for n, label, final, status, date in web:
        print(f"web {n}: {status} {final} {date}")

if __name__ == "__main__":
    main()
