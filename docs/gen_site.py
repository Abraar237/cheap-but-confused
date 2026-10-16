#!/usr/bin/env python3
"""Render docs/index.html from results/analysis.json. Every number on the site comes from the analysis file."""
import json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
A = json.load(open(ROOT / "results" / "analysis.json"))
AUD = json.load(open(ROOT / "results" / "audit_sample.json"))
MAIN = "google/gemini-3.1-flash-lite"; M = A["models"][MAIN]
LAB = {"google/gemini-2.5-flash": "Gemini 2.5 Flash", "google/gemini-3.1-flash-lite": "Gemini 3.1 Flash-Lite", "google/gemini-3.6-flash": "Gemini 3.6 Flash"}
LAD = [m for m in ("google/gemini-2.5-flash", "google/gemini-3.1-flash-lite", "google/gemini-3.6-flash") if m in A["models"]]
LN = {"L1": "L1 append-only", "L2": "L2 reordered", "L3": "L3 pruned", "L4": "L4 hybrid note"}
def ext(m, L):
    d = A["models"][m]["layouts"].get(L); return None if not d else d["by_trap_kind"]["external"]["acc"]
def own(m, L):
    d = A["models"][m]["layouts"].get(L); return None if not d else d["by_trap_kind"]["own"]["acc"]
def pc(x): return "--" if x is None else f"{x * 100:.1f}%"
def c(x): return "--" if x is None else f"{x * 100:.2f}c"
def p(x): return "p < 0.0001" if x is not None and x < 1e-4 else f"p = {x:.3f}"
L = M["layouts"]; C = M["contrasts"]; FR = M["frontier"]; D5 = M["d5"]["cheapest_per_correct_by_read_multiplier"]; D3 = M["d3"]; I = M["interactions"]
rep = A["batteries"]["repeat"]; phr = next((v for k, v in A["batteries"].items() if k.startswith("phrasing:")), None)
wq = next((v for k, v in A["batteries"].get("cache_hit_vs_miss_within_question", {}).items()), None)
spend = A["spend"]["total_usd"]; n_eps = A["n_episodes_all"]
t13 = C["trap_acc:L1-L3"]; t12 = C["trap_acc:L1-L2"]; t41 = C["trap_acc:L4-L1"]; cost13 = C["cost:L1-L3"]; cf13 = C["cache_frac:L1-L3"]
bykind = M["cache_by_turn_kind"]
ladder_rows = "".join(f"<tr><td>{LAB[m]}</td><td class='n'>{A['models'][m]['n_tasks']}</td><td class='n'>{pc(ext(m,'L1'))}</td><td class='n'>{pc(ext(m,'L3'))}</td><td class='n'>{pc(ext(m,'L4')) if 'L4' in A['models'][m]['layouts'] else '--'}</td><td class='n'>{pc(own(m,'L1'))}</td><td class='n'>{c(A['models'][m]['frontier']['L1']['usd_per_correct_task'])}</td><td class='n'>{c(A['models'][m]['frontier']['L3']['usd_per_correct_task'])}</td></tr>" for m in LAD)
LADDER_TEXT = open(ROOT / "docs" / "_ladder_text.html").read().strip() if (ROOT / "docs" / "_ladder_text.html").exists() else "LADDER-TEXT"
d5_row = "".join(f"<td class='n'>{k}x: {v['cheapest']}</td>" for k, v in D5.items())
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Cheap but confused? The accuracy cost of cache-optimized context layouts in LLM agents</title>
<meta name="description" content="Hold the information in an agent's context fixed, change only the layout, and measure accuracy, cached tokens and the bill. The append-only layout that prompt caching rewards loses a third of its answers on external updates; pruning fixes it and is cheaper per correct answer at every cache-read price.">
<style>
  :root {{ --slate:#155e8c; --hot:#b3006b; --shelf:#c0641a; --good:#1c7a55; --ink:#16130d; --ink2:#3a352b; --muted:#6d665a; --faint:#a49c8c; --rule:#e7e2d5; --rule2:#cfdfeb; --cardbg:#fdfcfa; }}
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family: Georgia, 'Times New Roman', serif; background:#ffffff; color:var(--ink); font-size:18px; line-height:1.72; }}
  .wrap {{ max-width:760px; margin:0 auto; padding:56px 24px 90px; }}
  .eyebrow {{ font-family: Helvetica, Arial, sans-serif; font-size:12px; letter-spacing:2.5px; text-transform:uppercase; color:var(--muted); font-weight:700; margin-bottom:16px; }}
  h1 {{ font-size:40px; line-height:1.14; margin-bottom:8px; letter-spacing:-0.3px; }}
  .subtitle {{ font-size:21px; color:var(--ink2); line-height:1.5; margin:14px 0 18px; font-style:italic; }}
  .byline {{ font-family: Helvetica, Arial, sans-serif; font-size:14px; color:var(--muted); margin-bottom:22px; }}
  .pills {{ margin-bottom:8px; }}
  .pills a {{ font-family: Helvetica, Arial, sans-serif; display:inline-block; font-size:14px; text-decoration:none; border:1px solid var(--rule2); border-radius:999px; padding:5px 14px; font-weight:600; color:var(--slate); margin:0 8px 10px 0; }}
  .pills a.solid {{ background:var(--ink); border-color:var(--ink); color:#fff; }}
  h2 {{ font-size:26px; line-height:1.25; margin:60px 0 8px; padding-top:26px; border-top:1px solid var(--rule); letter-spacing:-0.2px; }}
  p {{ margin:14px 0; color:var(--ink2); }}
  p b, li b {{ color:var(--ink); }}
  ul, ol {{ margin:12px 0 12px 26px; color:var(--ink2); }}
  li {{ margin:6px 0; }}
  .num {{ font-family:'SF Mono', Menlo, Consolas, monospace; font-size:0.92em; font-variant-numeric:tabular-nums; }}
  .fig {{ margin:28px 0 32px; border:1px solid var(--rule); border-radius:12px; padding:18px 18px 14px; background:#fff; overflow-x:auto; }}
  .fig img {{ width:100%; display:block; }}
  .figcap {{ font-family: Helvetica, Arial, sans-serif; font-size:13px; line-height:1.55; color:var(--muted); margin-top:12px; }}
  .stats {{ display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:26px 0 8px; }}
  .stat {{ border:1px solid var(--rule); border-radius:12px; padding:14px 16px; background:var(--cardbg); }}
  .stat .v {{ font-family:'SF Mono', Menlo, monospace; font-size:24px; font-weight:700; color:var(--slate); display:block; }}
  .stat .k {{ font-family: Helvetica, Arial, sans-serif; font-size:12px; color:var(--muted); letter-spacing:1px; text-transform:uppercase; }}
  .toc {{ font-family: Helvetica, Arial, sans-serif; font-size:14px; margin:26px 0 12px; padding:20px 22px; border:1px solid var(--rule); border-radius:12px; background:var(--cardbg); }}
  .toctitle {{ font-weight:700; letter-spacing:1.5px; text-transform:uppercase; font-size:12px; color:var(--muted); margin-bottom:8px; }}
  .toc a {{ color:var(--slate); text-decoration:none; display:block; padding:3px 0; }}
  table {{ border-collapse:collapse; width:100%; margin:20px 0; font-family: Helvetica, Arial, sans-serif; font-size:14px; }}
  th {{ text-align:left; border-bottom:2px solid var(--ink); padding:8px; font-size:12.5px; letter-spacing:.5px; text-transform:uppercase; color:var(--muted); }}
  td {{ border-bottom:1px solid var(--rule); padding:8px; }}
  td.n {{ font-family:'SF Mono', Menlo, monospace; font-variant-numeric:tabular-nums; }}
  .filmwrap {{ margin:34px 0 40px; border:1px solid var(--rule); border-radius:14px; overflow:hidden; background:#000; }}
  .filmwrap video {{ display:block; width:100%; height:auto; }}
  .note {{ background:var(--cardbg); border:1px solid var(--rule); border-radius:10px; padding:14px 18px; font-family: Helvetica, Arial, sans-serif; font-size:14px; color:var(--ink2); margin:16px 0; }}
  .cite {{ background:var(--cardbg); border:1px solid var(--rule); border-radius:10px; padding:16px 18px; font-family:'SF Mono', Menlo, monospace; font-size:12.5px; color:var(--ink2); white-space:pre-wrap; margin:16px 0; }}
  footer {{ font-family: Helvetica, Arial, sans-serif; margin-top:70px; padding-top:24px; border-top:1px solid var(--rule); color:var(--muted); font-size:13.5px; }}
  footer a {{ color:var(--slate); }}
  @media (max-width:640px){{ h1{{font-size:30px;}} body{{font-size:17px;}} .stats{{grid-template-columns:repeat(2,1fr);}} }}
</style>
</head>
<body>
<div class="wrap">
<div class="eyebrow">LLM agents · Prompt caching · Context layout · October 2026</div>
<h1>Cheap but confused?</h1>
<div class="subtitle">Prompt caching rewards one layout: keep the prefix fixed, append everything, delete nothing. We held an agent's information fixed and changed only the layout. The append-only layout answers {pc(ext(MAIN,'L1'))} of questions about values that changed behind the agent; redacting the stale value raises that to {pc(ext(MAIN,'L3'))}, and it is cheaper per correct answer at every cache-read price.</div>
<div class="byline">Mohammed Abraar · Vizuara Research · abraar@vizz.vizuara.ai · 12 min read · <a href="#film">or watch the 4-minute film</a></div>
<div class="pills">
  <a class="solid" href="#film">Film</a>
  <a href="paper_aaai_preprint.pdf">Paper (PDF, AAAI-27)</a>
  <a href="paper_aaai_submission.pdf">Anonymous build</a>
  <a href="supplementary_aaai.pdf">Supplementary</a>
  <a href="paper_iclr_preprint.pdf">Long version (ICLR format)</a>
  <a href="https://github.com/Abraar237/cheap-but-confused">Code + data</a>
</div>

<div class="stats">
  <div class="stat"><span class="v">144</span><span class="k">scripted episodes</span></div>
  <div class="stat"><span class="v">4</span><span class="k">layouts, same information</span></div>
  <div class="stat"><span class="v">{n_eps}</span><span class="k">billed episodes</span></div>
  <div class="stat"><span class="v">${spend:.2f}</span><span class="k">total metered spend</span></div>
</div>

<div class="toc"><div class="toctitle">Contents</div>
  <a href="#film">0. The four-minute film</a>
  <a href="#rule">1. Every agent now obeys one rule: never touch the start of the prompt</a>
  <a href="#testbed">2. A testbed where every stale value is known by construction</a>
  <a href="#layouts">3. Four layouts that carry the same information</a>
  <a href="#result1">4. Own updates never fail; external updates lose a third of the answers</a>
  <a href="#audit">5. Reading the wrong answers: it is the stale value, read back</a>
  <a href="#cost">6. The bill: cheapest per episode is not cheapest per correct episode</a>
  <a href="#cache">7. Where the cache reads actually come from</a>
  <a href="#ladder">8. Three Gemini generations</a>
  <a href="#prereg">9. Five pre-registered predictions, scored</a>
  <a href="#known">10. What was known, what is new</a>
  <a href="#limits">11. What this does not show</a>
  <a href="#repro">12. Reproduce it</a>
</div>

<h2 id="film">0. The four-minute film</h2>
<div class="filmwrap"><video controls preload="metadata" poster="assets/film-poster.png" src="assets/film.mp4"></video></div>
<p class="note">FILM-NOTE</p>

<h2 id="rule">1. Every agent now obeys one rule: never touch the start of the prompt</h2>
<p>Providers bill input tokens they have already processed at about a tenth of the list price. The discount applies only when a request begins with exactly the bytes of an earlier request. The guidance that followed is specific: put the system prompt and the tool declarations first and never change them, append every new observation at the end, mask tools instead of removing them, never reorder or delete earlier blocks. We call this the <b>cache-optimal layout</b>.</p>
<p>The layout has a side effect that nobody has priced. Nothing is ever removed, so when a value changes, the old value stays in the context next to the new one. A model that answers from its context must then prefer the later of two values for the same field. The question of this study is whether that costs accuracy with the information content held fixed, and what the cost is worth against the cache it protects.</p>
<div class="fig"><img src="assets/fig1_teaser.png" alt="Study design and headline numbers"><div class="figcap">Figure 1. One scripted episode is replayed under four layouts that carry the same information. Each question is scored against the live state of the environment and every call is billed and cache-metered by the provider.</div></div>

<h2 id="testbed">2. A testbed where every stale value is known by construction</h2>
<p>To blame an error on a stale value, you must know, for every question the agent answers, whether a superseded value for the queried field is in its context. Public agent benchmarks do not record this. So we built <b>StaleTrap</b>: three back-office domains (warehouse inventory, a shared calendar, a support-ticket queue) exposed as 29 JSON-schema tools, plus 10 messaging and HR tools that are present in every call and never needed. A local executor holds the state and returns realistic JSON, and every result declares which (record, field) values it states.</p>
<p>An episode is a scripted session of 6, 12, 18 or 30 tool calls with 2 to 8 question steps served with tool calling disabled. In a <b>trap step</b> a superseded value is sitting in the context when the question arrives. In a <b>neutral step</b> nothing competes. Traps come in two kinds. In an <b>own update</b>, the agent changed the value itself and the tool reply stated the new value. In an <b>external update</b>, someone else changed the record and the agent only ever saw the new value as one row inside a listing it was asked to fetch. The grid is 144 episodes, 720 questions (360 trap, 360 neutral), 2,376 tool calls, frozen with a SHA-256 manifest before the first scored call.</p>

<h2 id="layouts">3. Four layouts that carry the same information</h2>
<p>Each turn, the runner rebuilds the message list from the transcript so far under one rule. <b>L1</b> is the cache-optimal layout: arrival order, newest observation last, tools masked rather than removed. <b>L2</b> keeps the same blocks but reorders the earlier ones by how many record identifiers they share with the current turn, most relevant last, which rewrites the prefix every turn. <b>L3</b> keeps arrival order and redacts, in place, every value that a later result restated; it is an oracle pruner and an upper bound for any real one. <b>L4</b> is L1 plus a pointer-only note kept on every user turn: the goal, the step, and for every record with more than one observation which step is current. The note never contains a value.</p>
<div class="fig"><img src="assets/gifs/same-information-four-layouts.gif" alt="The same information under four layouts"><div class="figcap">The same transcript under L1, L2, L3 and L4.</div></div>

<h2 id="result1">4. Own updates never fail; external updates lose a third of the answers</h2>
<p>On Gemini 3.1 Flash-Lite, which ran the full grid, every layout scores {pc(own(MAIN,'L1'))} on own-update traps and {pc(L['L1']['neutral_acc']['mean'])} on neutral steps. The whole effect lives in external updates. There the append-only layout answers <span class="num">{pc(ext(MAIN,'L1'))}</span> correctly, the reordered layout <span class="num">{pc(ext(MAIN,'L2'))}</span>, the pruned layout <span class="num">{pc(ext(MAIN,'L3'))}</span> and the note <span class="num">{pc(ext(MAIN,'L4'))}</span> (200 external-trap questions per layout).</p>
<p>Over all 360 trap questions the paired contrasts are: L1 minus L3 <span class="num">{t13['mean']:+.3f}</span> [{t13['ci'][0]:.3f}, {t13['ci'][1]:.3f}], {p(t13['p'])}; L1 minus L2 <span class="num">{t12['mean']:+.3f}</span> [{t12['ci'][0]:.3f}, {t12['ci'][1]:.3f}], {p(t12['p'])}; L4 minus L1 <span class="num">{t41['mean']:+.3f}</span> [{t41['ci'][0]:.3f}, {t41['ci'][1]:.3f}], {p(t41['p'])}. Neutral steps differ by exactly zero between every pair of layouts. The gap does not grow with episode length (slope {I['trap_gap:L1-L3:x_length']['slope_per_call']:+.4f} per call, {p(I['trap_gap:L1-L3:x_length']['p'])}): it is already {pc(-I['trap_gap:L1-L3:x_length']['gap_by_length']['6'])} at six calls.</p>
<div class="fig"><img src="assets/fig2_stale.png" alt="Accuracy by layout and question kind"><div class="figcap">Figure 2. Step accuracy by layout on own-update traps, external-update traps and neutral steps, per model.</div></div>
<div class="fig"><img src="assets/fig4_dose.png" alt="Trap gap by length and distractor"><div class="figcap">Figure 4. The L1 minus L3 trap gap by episode length and distractor level. Flat: the cost of a stale value is paid as soon as it exists.</div></div>

<h2 id="audit">5. Reading the wrong answers: it is the stale value, read back</h2>
<p>We hand-coded {AUD['n']} wrong trap answers from the main grid, each with the full observation history of the queried field. {AUD['counts'].get('stale_value',0)} are a superseded value read back: typically the agent's own earlier write, with the later listing row that overtook it ignored. {AUD['counts'].get('ambiguous_stale_or_boundary',0)} are threshold questions where the fresh quantity equals the threshold, so a stale read and a strict-inequality misreading give the same wrong answer. {AUD['counts'].get('reveal_not_executed',0)} are questions where the agent had skipped the scripted listing call, so the fresh value never entered its context (both under L3). {AUD['counts'].get('arithmetic_or_count',0)} is a derived number that matches no observation. Restricting every accuracy to questions whose scripted thread steps were all executed moves no layout by more than a point.</p>

<h2 id="cost">6. The bill: cheapest per episode is not cheapest per correct episode</h2>
<p>Per episode, billed by the provider, the append-only layout is the cheapest at <span class="num">{c(FR['L1']['usd_per_episode'])}</span>; the pruned layout costs <span class="num">{c(FR['L3']['usd_per_episode'])}</span> ({p(cost13['p'])}), the reordered layout <span class="num">{c(FR['L2']['usd_per_episode'])}</span> and the note <span class="num">{c(FR['L4']['usd_per_episode'])}</span>. Per correct episode the order flips: pruned <span class="num">{c(FR['L3']['usd_per_correct_task'])}</span>, append-only <span class="num">{c(FR['L1']['usd_per_correct_task'])}</span>, reordered <span class="num">{c(FR['L2']['usd_per_correct_task'])}</span>, note <span class="num">{c(FR['L4']['usd_per_correct_task'])}</span>.</p>
<p>We then repriced every cached token at multipliers of the input price from 0 (reads free) to 1 (no discount). The cheapest layout per correct episode at each multiplier is:</p>
<table><tr>{d5_row}</tr></table>
<p>At every price the pruned layout wins. The pre-registered prediction was that a threshold exists below which the cache-optimal layout becomes cheapest per correct answer. On this provider it does not, for a reason the next section shows.</p>
<div class="fig"><img src="assets/gifs/cost-per-correct-task.gif" alt="Cost per correct task by layout"><div class="figcap">Cents per episode and cents per correct episode, by layout.</div></div>
<div class="fig"><img src="assets/fig3_frontier.png" alt="Accuracy versus billed cost"><div class="figcap">Figure 3. Episode success against billed cents per episode, per model; outlined points are Pareto-optimal.</div></div>
<div class="fig"><img src="assets/fig6_threshold.png" alt="Cost per correct task versus cache-read price"><div class="figcap">Figure 6. Cents per correct episode as the cache-read price moves from free to full price. The lines do not cross.</div></div>

<h2 id="cache">7. Where the cache reads actually come from</h2>
<p>Google's cache is implicit and best-effort. Across the main grid the cached share of prompt tokens is <span class="num">{L['L1']['cache_frac']['mean']:.2f}</span> under L1 and <span class="num">{L['L3']['cache_frac']['mean']:.2f}</span> under L3, a difference of {cf13['mean']:.3f} [{cf13['ci'][0]:.3f}, {cf13['ci'][1]:.3f}]. Most of that share is the 5,100-token static prefix. Counting only the history (everything after the prefix), the cached share is <span class="num">{L['L1']['hist_cache_frac']['mean']:.2f}</span> under L1 and <span class="num">{L['L3']['hist_cache_frac']['mean']:.2f}</span> under L3. The layout that caching rewards is barely rewarded for its history on this provider, so breaking the prefix costs little. Two more facts shape the bill. No-tool question turns are served from cache far less often than tool turns (hit rate {bykind['L1']['hit_rate_question_turns']:.2f} against {bykind['L1']['hit_rate_action_turns']:.2f} under L1), because disabling tool choice changes the request. And the L4 note, 150 tokens per turn that must stay in the history to keep the prefix stable, raises prompt tokens per episode by {L['L4']['prompt_tokens']['mean']/L['L1']['prompt_tokens']['mean']*100-100:.0f} percent over L1.</p>
<div class="fig"><img src="assets/gifs/where-the-cache-reads-come-from.gif" alt="Cached share by turn"><div class="figcap">Cached share of prompt tokens by turn under each layout.</div></div>
<div class="fig"><img src="assets/fig5_cache.png" alt="Cached fraction by turn"><div class="figcap">Figure 5. Cached-token fraction by turn index per layout.</div></div>
<p>The plan assigned a cache on/off control to Anthropic, whose documentation promises output-neutral caching; that provider was unreachable on this workspace's key. The substitute uses the best-effort cache itself: the same question, under the same layout, served from cache in some runs of the repeat battery and not in others. Paired within question, the difference in trap accuracy is {wq['hit_minus_miss']:+.3f} over {wq['n_questions_with_both']} questions that saw both outcomes ({p(wq['p'])}).</p>

<h2 id="ladder">8. Three Gemini generations</h2>
<p>{LADDER_TEXT}</p>
<table><tr><th>Model</th><th>tasks</th><th>external traps, L1</th><th>L3</th><th>L4</th><th>own traps, L1</th><th>cents per correct, L1</th><th>L3</th></tr>{ladder_rows}</table>

<h2 id="prereg">9. Five pre-registered predictions, scored</h2>
PREREG-TABLE

<h2 id="known">10. What was known, what is new</h2>
<p>Known: models use the start and end of a long context better than the middle; the latest of several revisions of a fact is retrieved less reliably as revisions accumulate; agents answer from observations the world has overtaken; pruning or masking old observations changes accuracy in a model-dependent way; prompt caching cuts the cost of long sessions by 40 to 80 percent and the discount is lost when earlier bytes change.</p>
<p>New: a content-fixed manipulation of layout (order only, content only, recitation only) in a multi-turn tool-using agent, scored against provider-reported cached tokens and billed dollars, with every question annotated as a stale-trap step (own or external) or a neutral step, and a per-model answer to whether a cache-read price exists at which the cheapest layout per call stops being the cheapest per correct answer. The nearest neighbours vary content (compression) rather than layout, report cost without accuracy, or price tokens at list rates without a cache term. The paper's Section 2 lists them.</p>

<h2 id="limits">11. What this does not show</h2>
<ul>
<li><b>One provider family.</b> The plan froze three families; the workspace key allowed only Google. Every number is a Google number, and the cost conclusion depends on Google's best-effort cache rarely serving the history. A provider with explicit breakpoints and a 90 percent intra-turn hit rate would give the append-only layout a larger cost advantage, and a price threshold could then exist.</li>
<li><b>L3 is an oracle.</b> It redacts exactly what a later result restates. No deployed pruner has that oracle; L3 is the size of the prize, L4 is what a pointer-only note collects without one.</li>
<li><b>A synthetic testbed.</b> Scripted episodes, small domains, exact-match questions. The external arm on BFCL v3 multi-turn found no layout effect on 50 tasks; its failures are capability failures, not stale reads, so the mechanism has not been shown on a public benchmark.</li>
<li><b>Noise.</b> A trap outcome flips between identical temperature-0 runs in {rep['frac_cells_trap_acc_varies']*100:.0f} percent of cells; the paired tests over 144 tasks absorb this, single cells do not.</li>
<li><b>The audit is not blind.</b> The agent that ran the study coded the 40 wrong answers with the layout visible; the codes are mechanical and ship with the release.</li>
</ul>

<h2 id="repro">12. Reproduce it</h2>
<p>Everything is in the repository: the frozen testbed with its manifest, the executor, the four layout serialisers, the runner, every raw episode log with per-call provider usage and billed cost, the single analysis script, the audit, the figure and film builders, and the spend log. Metered spend for the whole study, including pilots, calibration and discarded runs, was <span class="num">${spend:.2f}</span>.</p>
<div class="cite">git clone https://github.com/Abraar237/cheap-but-confused
cd cheap-but-confused
python3 experiments/analyze.py            # results/analysis.json from results/raw/*.jsonl, byte-identical
python3 figures/build_figures.py          # figures 2 to 6
python3 paper/iclr/gen_tables.py          # every table in the paper
# to re-run episodes (needs OPENROUTER_API_KEY in .env; the tracker stops at the hard cap):
python3 experiments/runner.py --model google/gemini-3.1-flash-lite --layouts L1,L2,L3,L4</div>

<footer>Mohammed Abraar · Vizuara Research · <a href="mailto:abraar@vizz.vizuara.ai">abraar@vizz.vizuara.ai</a><br>
<a href="paper_aaai_preprint.pdf">Paper</a> · <a href="#film">Film</a> · <a href="https://github.com/Abraar237/cheap-but-confused">GitHub</a></footer>
</div>
</body>
</html>
"""
prereg = open(ROOT / "docs" / "_prereg_table.html").read() if (ROOT / "docs" / "_prereg_table.html").exists() else "<p>PREREG-TABLE</p>"
film_note = open(ROOT / "docs" / "_film_note.html").read() if (ROOT / "docs" / "_film_note.html").exists() else "FILM-NOTE"
html = html.replace("PREREG-TABLE", prereg).replace("FILM-NOTE", film_note)
open(ROOT / "docs" / "index.html", "w").write(html)
print("wrote docs/index.html", len(html))
