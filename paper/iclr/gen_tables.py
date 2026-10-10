#!/usr/bin/env python3
"""Emit every results table in the paper from results/analysis.json (and the audit file it summarises).
Writes paper/iclr/generated/*.tex. No number in any table is typed by hand."""
import json, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[2]
A = json.load(open(ROOT / "results" / "analysis.json"))
OUT = ROOT / "paper" / "iclr" / "generated"
OUT.mkdir(exist_ok=True)
LABEL = {"google/gemini-2.5-flash": "Gemini 2.5 Flash", "google/gemini-3.1-flash-lite": "Gemini 3.1 Flash-Lite", "google/gemini-3.6-flash": "Gemini 3.6 Flash",
         "anthropic/claude-haiku-5.5": "Claude Haiku 5.5", "openai/gpt-5-mini": "GPT-5 mini"}
ORDER = ["google/gemini-2.5-flash", "google/gemini-3.1-flash-lite", "google/gemini-3.6-flash"]
MODELS = [m for m in ORDER if m in A["models"]] + [m for m in A["models"] if m not in ORDER]
LAYOUTS = ["L1", "L2", "L3", "L4"]
LNAME = {"L1": "L1 append-only", "L2": "L2 reordered", "L3": "L3 pruned", "L4": "L4 hybrid"}
BH_T = A["bh"]["effective_threshold"]
TESTS = A["tests"]

def lab(m): return LABEL.get(m, m)
def f3(x): return "--" if x is None else f"{x:.3f}"
def f2(x): return "--" if x is None else f"{x:.2f}"
def cents(x): return "--" if x is None else f"{x * 100:.2f}"
def pct(x): return "--" if x is None else f"{x * 100:.1f}"
def pv(p):
    if p is None: return "--"
    return "$<$0.0001" if p < 1e-4 else f"{p:.4f}" if p < 0.01 else f"{p:.3f}"
def survives(key):
    t = TESTS.get(key)
    return bool(t and t.get("bh_survives_05"))
def bold(s, on): return f"\\textbf{{{s}}}" if on else s
def ci(v):
    if v is None or v.get("ci") is None or v["ci"][0] is None: return f3(v["mean"]) if v else "--"
    return f"{v['mean']:.3f} [{v['ci'][0]:.3f}, {v['ci'][1]:.3f}]"
def tex_escape(s): return s.replace("\\", "\\textbackslash{}").replace("_", "\\_").replace("%", "\\%").replace("&", "\\&").replace("#", "\\#").replace("$", "\\$").replace("|", "$|$").replace("<", "$<$").replace(">", "$>$")

# ---------------------------------------------------------------- main results table (per model, per layout)
rows = ["\\begin{tabular}{llrrrrrrr}", "\\toprule",
        "\\textbf{Model} & \\textbf{Layout} & $n$ & \\textbf{Trap acc.} & \\textbf{Neutral acc.} & \\textbf{Success} & \\textbf{Cents/episode} & \\textbf{Cents/correct task} & \\textbf{Cached share} \\\\", "\\midrule"]
for m in MODELS:
    M = A["models"][m]
    first = True
    for L in LAYOUTS:
        if L not in M["layouts"]: continue
        d = M["layouts"][L]
        rows.append(f"{lab(m) if first else ''} & {LNAME[L]} & {d['n']} & {ci(d['trap_acc'])} & {f3(d['neutral_acc']['mean'])} & {f3(d['success']['mean'])} & {cents(d['cost']['mean'])} & {cents(d['usd_per_correct_task'])} & {f3(d['cache_frac']['mean'])} \\\\")
        first = False
    rows.append("\\midrule")
rows[-1] = "\\bottomrule"; rows.append("\\end{tabular}")
open(OUT / "tab_main.tex", "w").write("\n".join(rows) + "\n")

# ---------------------------------------------------------------- paired contrasts (main text), BH survivors bold
CONTR = ["L1-L2", "L1-L3", "L4-L1", "L4-L3", "L2-L3"]
CNAME = {"L1-L2": "L1 $-$ L2 (order)", "L1-L3": "L1 $-$ L3 (content)", "L4-L1": "L4 $-$ L1 (note)", "L4-L3": "L4 $-$ L3", "L2-L3": "L2 $-$ L3"}
METR = [("trap_acc", "Trap acc."), ("neutral_acc", "Neutral acc."), ("success", "Success"), ("cost", "USD/episode"), ("cache_frac", "Cached share")]
for m in MODELS:
    M = A["models"][m]
    rows = ["\\begin{tabular}{lrrrrr}", "\\toprule", "\\textbf{Contrast} & " + " & ".join(f"\\textbf{{{n}}}" for _, n in METR) + " \\\\", "\\midrule"]
    for c in CONTR:
        cells = []
        for k, _ in METR:
            key = f"{k}:{c}"
            v = M["contrasts"].get(key)
            if v is None: cells.append("--"); continue
            mean = v["mean"]; lo, hi = v["ci"]
            txt = (f"{mean * 100:+.2f}c [{lo * 100:.2f}, {hi * 100:.2f}]" if k == "cost" else f"{mean:+.3f} [{lo:.3f}, {hi:.3f}]") + f", $p$={pv(v['p'])}"
            cells.append(bold(txt, survives(f"{m}:{key}")))
        if any(x != "--" for x in cells):
            rows.append(f"{CNAME[c]} & " + " & ".join(cells) + " \\\\")
    rows += ["\\bottomrule", "\\end{tabular}"]
    open(OUT / f"tab_contrasts_{m.split('/')[-1]}.tex", "w").write("\n".join(rows) + "\n")

# ---------------------------------------------------------------- full test family (appendix)
rows = ["\\begin{longtable}{llrl}", "\\toprule", "\\textbf{Model} & \\textbf{Test} & $p$ & \\textbf{BH} \\\\", "\\midrule", "\\endhead"]
for key in sorted(TESTS, key=lambda k: (MODELS.index(k.split(":")[0]) if k.split(":")[0] in MODELS else 99, k)):
    m, rest = key.split(":", 1)
    rows.append(f"{lab(m) if m in A['models'] else tex_escape(m)} & \\texttt{{{tex_escape(rest)}}} & {pv(TESTS[key]['p'])} & {'survives' if survives(key) else ''} \\\\")
rows += ["\\bottomrule", "\\end{longtable}"]
open(OUT / "tab_tests.tex", "w").write("\n".join(rows) + "\n")
open(OUT / "bh_summary.tex", "w").write(f"The family holds {A['bh']['n_tests']} tests; {A['bh']['n_survive']} survive Benjamini-Hochberg at $q = 0.05$ (effective threshold $p \\le {BH_T:.4f}$).\n")

# ---------------------------------------------------------------- per-cell tables: trap accuracy by length and by distractor, per model
rows = ["\\begin{tabular}{llrrrrrr}", "\\toprule", "\\textbf{Model} & \\textbf{Layout} & \\textbf{6 calls} & \\textbf{12} & \\textbf{18} & \\textbf{30} & \\textbf{low distr.} & \\textbf{high distr.} \\\\", "\\midrule"]
for m in MODELS:
    M = A["models"][m]; first = True
    for L in LAYOUTS:
        if L not in M["layouts"]: continue
        d = M["layouts"][L]
        bl = d["by_length"]; bd = d["by_distractor"]
        rows.append(f"{lab(m) if first else ''} & {LNAME[L]} & " + " & ".join(f3(bl[k]["trap_acc"]) if k in bl else "--" for k in ("6", "12", "18", "30")) + f" & {f3(bd['low']['trap_acc'])} & {f3(bd['high']['trap_acc'])} \\\\")
        first = False
    rows.append("\\midrule")
rows[-1] = "\\bottomrule"; rows.append("\\end{tabular}")
open(OUT / "tab_cells_length.tex", "w").write("\n".join(rows) + "\n")

rows = ["\\begin{tabular}{llrrrrrrrr}", "\\toprule", "\\textbf{Model} & \\textbf{Layout} & \\textbf{own} & \\textbf{external} & \\textbf{chain 1} & \\textbf{chain 2} & \\textbf{chain 3} & \\textbf{inventory} & \\textbf{calendar} & \\textbf{tickets} \\\\", "\\midrule"]
for m in MODELS:
    M = A["models"][m]; first = True
    for L in LAYOUTS:
        if L not in M["layouts"]: continue
        d = M["layouts"][L]; bc = d["by_chain"]; bdm = d["by_domain"]; bk = d.get("by_trap_kind", {})
        rows.append(f"{lab(m) if first else ''} & {LNAME[L]} & " + " & ".join(f3(bk[k]["acc"]) if k in bk else "--" for k in ("own", "external")) + " & " + " & ".join(f3(bc[k]["acc"]) if k in bc else "--" for k in ("1", "2", "3")) + " & " + " & ".join(f3(bdm[k]["trap_acc"]) if k in bdm else "--" for k in ("inventory", "calendar", "ticketing")) + " \\\\")
        first = False
    rows.append("\\midrule")
rows[-1] = "\\bottomrule"; rows.append("\\end{tabular}")
open(OUT / "tab_cells_chain.tex", "w").write("\n".join(rows) + "\n")

# interactions
rows = ["\\begin{tabular}{llrrrr}", "\\toprule", "\\textbf{Model} & \\textbf{Contrast} & \\textbf{Gap slope per call} ($p$) & \\textbf{High $-$ low distractor} ($p$) & \\textbf{Trap $-$ neutral gap} ($p$) \\\\", "\\midrule"]
for m in MODELS:
    I = A["models"][m]["interactions"]; first = True
    for c in ("L1-L2", "L1-L3", "L4-L1"):
        a = I.get(f"trap_gap:{c}:x_length"); b = I.get(f"trap_gap:{c}:x_distractor"); g = I.get(f"gap:{c}:trap_minus_neutral")
        if not (a or b or g): continue
        rows.append(f"{lab(m) if first else ''} & {CNAME[c]} & " + (f"{a['slope_per_call']:+.4f} ({pv(a['p'])})" if a else "--") + " & " + (f"{b['high_minus_low']:+.3f} ({pv(b['p'])})" if b else "--") + " & " +
                    (bold(f"{g['mean']:+.3f} ({pv(g['p'])})", survives(f"{m}:int:{c}:trap_vs_neutral")) if g else "--") + " \\\\")
        first = False
rows += ["\\bottomrule", "\\end{tabular}"]
open(OUT / "tab_interactions.tex", "w").write("\n".join(rows) + "\n")

# ---------------------------------------------------------------- fidelity
rows = ["\\begin{tabular}{llrrrrr}", "\\toprule", "\\textbf{Model} & \\textbf{Layout} & \\textbf{Action exec.} & \\textbf{Reveal exec.} & \\textbf{Trap acc. (all)} & \\textbf{Trap acc. (thread fully executed)} & $n$ \\textbf{skipped} \\\\", "\\midrule"]
for m in MODELS:
    F = A["models"][m].get("fidelity", {}); first = True
    for L in LAYOUTS:
        if L not in F: continue
        d = F[L]
        rows.append(f"{lab(m) if first else ''} & {LNAME[L]} & {f3(d['action_exec_rate'])} & {f3(d['reveal_exec_rate'])} & {f3(d['trap_acc_all'])} & {f3(d['trap_acc_thread_fully_executed'])} & {d['n_trap_with_skipped_thread_step']} \\\\")
        first = False
    rows.append("\\midrule")
rows[-1] = "\\bottomrule"; rows.append("\\end{tabular}")
open(OUT / "tab_fidelity.tex", "w").write("\n".join(rows) + "\n")

# ---------------------------------------------------------------- D3 / D5 summary per model
rows = ["\\begin{tabular}{lrrrrr}", "\\toprule", "\\textbf{Model} & \\textbf{L3 $-$ L1 gap} & \\textbf{L4 $-$ L1 gap} & \\textbf{Recovery} [CI] & \\textbf{L4/L1 cached share} & \\textbf{Cheapest per correct (billed)} \\\\", "\\midrule"]
for m in MODELS:
    M = A["models"][m]; d3 = M.get("d3", {}); d5 = M.get("d5", {})
    if not d3: continue
    rec = f"{d3['recovery_fraction']:.2f} [{d3['ci'][0]:.2f}, {d3['ci'][1]:.2f}]" if d3.get("recovery_fraction") is not None else "--"
    rows.append(f"{lab(m)} & {d3.get('gap_L3_minus_L1'):+.3f} & {d3.get('gap_L4_minus_L1'):+.3f} & {rec} & {f2(d3.get('cache_frac_L4_over_L1'))} & {d5.get('billed_cheapest_per_correct', '--')} \\\\")
rows += ["\\bottomrule", "\\end{tabular}"]
open(OUT / "tab_d3d5.tex", "w").write("\n".join(rows) + "\n")

# D5 threshold table: cheapest layout per correct task vs cache-read multiplier
mults = None
rows = []
for m in MODELS:
    d5 = A["models"][m].get("d5", {}).get("cheapest_per_correct_by_read_multiplier")
    if not d5: continue
    if mults is None:
        mults = list(d5.keys())
        rows = ["\\begin{tabular}{l" + "r" * len(mults) + "}", "\\toprule", "\\textbf{Model} & " + " & ".join(f"\\textbf{{{k}$\\times$}}" for k in mults) + " \\\\", "\\midrule"]
    rows.append(f"{lab(m)} & " + " & ".join(d5[k]["cheapest"] for k in mults) + " \\\\")
if rows:
    rows += ["\\bottomrule", "\\end{tabular}"]
    open(OUT / "tab_d5.tex", "w").write("\n".join(rows) + "\n")

# ---------------------------------------------------------------- batteries
B = A["batteries"]
lines = []
if "repeat" in B:
    r = B["repeat"]
    lines.append(f"\\textbf{{Repeat battery.}} {r['n_cells']} task cells on L1 were re-run (five runs each, temperature 0). The trap-accuracy outcome differed between runs in {pct(r['frac_cells_trap_acc_varies'])} percent of cells and episode success in {pct(r['frac_cells_success_varies'])} percent; the mean within-cell standard deviation of question accuracy is {f3(r['mean_within_cell_sd_q_acc'])}.")
for k, v in B.items():
    if k.startswith("phrasing:"):
        lines.append(f"\\textbf{{Phrasing battery ({lab(k.split(':', 1)[1])}).}} {v['n_pairs']} episodes were re-run with the second phrasing of every instruction and question. Question accuracy under phrasing 2 minus phrasing 1: {v['q_acc_p2_minus_p1']:+.3f} [{v['ci'][0]:.3f}, {v['ci'][1]:.3f}], sign-flip $p$ = {pv(v['p'])}.")
    if k.startswith("cache_on_off:"):
        lines.append(f"\\textbf{{Cache on/off ({lab(k.split(':', 1)[1])}).}} {v['n_pairs']} paired episodes; question accuracy with caching off minus on: {v['q_acc_nocache_minus_cached']:+.3f} [{v['ci'][0]:.3f}, {v['ci'][1]:.3f}], $p$ = {pv(v['p'])}.")
if not any(k.startswith("cache_on_off:") for k in B):
    lines.append("\\textbf{Cache on/off.} Not run: the only provider that documents output-neutral explicit caching (Anthropic) was unreachable on this workspace's OpenRouter key (a guardrail that blocks every non-Google model; probed before the plan was frozen and again after the main grid). The implicit-cache hit-versus-miss comparison within layout on Google is reported in its place.")
open(OUT / "batteries.tex", "w").write("\n\n".join(lines) + "\n")

# ---------------------------------------------------------------- audit
aud = json.load(open(ROOT / "results" / "audit_sample.json"))
rows = ["\\begin{tabular}{lrrrrr}", "\\toprule", "\\textbf{Code} & \\textbf{L1} & \\textbf{L2} & \\textbf{L3} & \\textbf{L4} & \\textbf{All} \\\\", "\\midrule"]
for code in aud["counts"]:
    rows.append(f"\\texttt{{{tex_escape(code)}}} & " + " & ".join(str(aud["counts_by_layout"].get(L, {}).get(code, 0)) for L in LAYOUTS) + f" & {aud['counts'][code]} \\\\")
rows.append("\\midrule"); rows.append("total & " + " & ".join(str(sum(aud["counts_by_layout"].get(L, {}).values())) for L in LAYOUTS) + f" & {aud['n']} \\\\")
rows += ["\\bottomrule", "\\end{tabular}"]
open(OUT / "tab_audit.tex", "w").write("\n".join(rows) + "\n")
defs = "\\begin{description}\n" + "\n".join(f"\\item[\\texttt{{{tex_escape(k)}}}] {tex_escape(v)}" for k, v in aud["codes"].items()) + "\n\\end{description}\n"
open(OUT / "audit_defs.tex", "w").write(f"Sample: {tex_escape(aud['sampling'])}. Wrong trap answers in the main grid: {aud['n_wrong_total']}. Coder: {tex_escape(aud['coder'])}. Date: {aud['date']}.\n\n" + defs)

# ---------------------------------------------------------------- cost
S = A["spend"]
groups = {}
for k, v in S["by_model"].items():
    g = k.split("|")[0]
    groups[g] = groups.get(g, 0) + v
rows = ["\\begin{tabular}{lr}", "\\toprule", "\\textbf{Item (OpenRouter billed)} & \\textbf{USD} \\\\", "\\midrule"]
for g, v in sorted(groups.items(), key=lambda kv: -kv[1]):
    rows.append(f"\\texttt{{{tex_escape(g)}}} & {v:.2f} \\\\")
rows += ["\\midrule", f"total ({S['n_calls']} calls) & {S['total_usd']:.2f} \\\\", "\\bottomrule", "\\end{tabular}"]
open(OUT / "tab_cost.tex", "w").write("\n".join(rows) + "\n")
open(OUT / "spend_total.tex", "w").write(f"{S['total_usd']:.2f}")
open(OUT / "n_episodes.tex", "w").write(f"{A['n_episodes_all']}")
print("wrote", sorted(p.name for p in OUT.glob("*.tex")))
