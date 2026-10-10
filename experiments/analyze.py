#!/usr/bin/env python3
"""Single analysis pass: results/raw/*.jsonl -> results/analysis.json. Every number in the paper traces
to this file's output. Seeded; byte-identical on re-run (fixed RNG, sorted iteration, rounded floats).

Unit = task (one frozen episode script). Within-task paired contrasts between layouts (L1-L2, L1-L3,
L4-L1, L4-L3, L2-L3) on: trap-step accuracy, neutral-step accuracy, episode success, billed USD, cache-read
fraction. Tests: two-sided sign-flip permutation on paired task differences (20,000 flips); 95% CIs by task
bootstrap (10,000); a template-cluster sign-flip (exact over all 2^9 patterns) as a robustness column;
interactions (layout x length, layout x distractor, layout x family) by label permutation (5,000);
Benjamini-Hochberg over the full family of primary tests; bold survivors only.

Usage: python3 analyze.py [--audit-export N]"""

import argparse
import glob
import itertools
import json
import os
from collections import defaultdict

import numpy as np

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
RAW = os.path.join(ROOT, "results", "raw")
OUT = os.path.join(ROOT, "results", "analysis.json")
N_BOOT, N_PERM, N_LABEL = 10_000, 20_000, 5_000
LAYOUTS = ["L1", "L2", "L3", "L4"]
CONTRASTS = [("L1", "L2"), ("L1", "L3"), ("L4", "L1"), ("L4", "L3"), ("L2", "L3")]
METRICS = ["trap_acc", "neutral_acc", "success", "cost", "cache_frac", "hist_cache_frac", "q_acc"]
# OpenRouter list prices per 1M tokens, fetched 2026-10-10 (input, cache read, cache write, output)
PRICES = {"google/gemini-2.5-flash-lite": (0.10, 0.01, 0.0833, 0.40), "google/gemini-2.5-flash": (0.30, 0.03, 0.0833, 2.50), "google/gemini-3.1-flash-lite": (0.25, 0.025, 0.0833, 1.50),
          "google/gemini-3.5-flash-lite": (0.30, 0.03, 0.0833, 2.50), "google/gemini-3.6-flash": (0.75, 0.075, 0.0833, 3.75), "anthropic/claude-haiku-5.5": (0.10, 0.01, 0.125, 0.50),
          "openai/gpt-5-mini": (0.25, 0.025, 0.0, 2.00), "openai/gpt-5-nano": (0.05, 0.005, 0.0, 0.40), "openai/gpt-5.6-luna": (0.20, 0.02, 0.25, 1.20)}
CF_MULT = [0.0, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0]   # counterfactual cache-read price as a multiple of the input price
RNG = np.random.default_rng(20261010)


def r4(x):
    return None if x is None or (isinstance(x, float) and np.isnan(x)) else float(round(float(x), 6))


def load():
    rows = []
    for f in sorted(glob.glob(os.path.join(RAW, "*.jsonl"))):
        if os.path.basename(f).startswith("_"):
            continue
        for line in open(f):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r.get("q_total", 0) == 0:
                continue
            live = [t for t in r["turns"] if not t.get("retry_discarded")]
            prefix = r.get("prefix_tokens_turn1") or (live[0]["prompt_tokens"] if live else 0) or 0
            prompt = sum(t["prompt_tokens"] or 0 for t in live)
            cached = sum(t["cached_tokens"] or 0 for t in live)
            # history-only cache fraction: exclude the static prefix from both numerator and denominator (turn 1 excluded entirely)
            hp = sum(max(0, (t["prompt_tokens"] or 0) - prefix) for t in live[1:])
            hc = sum(max(0, min(t["cached_tokens"] or 0, (t["prompt_tokens"] or 0)) - prefix) for t in live[1:])
            hc = sum(max(0, (t["cached_tokens"] or 0) - prefix) for t in live[1:])
            rows.append({**{k: r[k] for k in ("model", "family", "task_id", "domain", "template", "length", "distractor", "seed", "layout", "phrasing", "battery", "rep")},
                         "trap_acc": r["trap_correct"] / r["trap_total"] if r["trap_total"] else np.nan,
                         "neutral_acc": r["neutral_correct"] / r["neutral_total"] if r["neutral_total"] else np.nan,
                         "q_acc": r["q_correct"] / r["q_total"], "success": float(r["episode_success"]),
                         "cost": r["cost"], "prompt_tokens": prompt, "cached_tokens": cached, "completion_tokens": r["completion_tokens"],
                         "reasoning_tokens": r["reasoning_tokens"], "cache_write_tokens": r["cache_write_tokens"],
                         "cache_frac": cached / prompt if prompt else np.nan, "hist_cache_frac": hc / hp if hp > 0 else np.nan,
                         "prefix_tokens": prefix, "n_turns": len(live), "n_retries": r.get("n_retries", 0), "wall_s": r["wall_s"],
                         "action_args_ok": r["action_args_ok"] / r["action_total"] if r["action_total"] else np.nan,
                         "action_exec_ok": float(np.mean([st["exec_ok"] for st in r["steps"] if st["kind"] == "action"])) if r["action_total"] else np.nan,
                         "turns": live, "steps": r["steps"], "key": r["key"]})
    return rows


# ---------------- statistics ----------------
def boot_ci(vals):
    v = np.asarray(vals, float)
    v = v[~np.isnan(v)]
    if len(v) < 2:
        return [None, None]
    idx = RNG.integers(0, len(v), size=(N_BOOT, len(v)))
    m = v[idx].mean(axis=1)
    return [r4(np.percentile(m, 2.5)), r4(np.percentile(m, 97.5))]


def signflip(d):
    d = np.asarray(d, float)
    d = d[~np.isnan(d)]
    if len(d) == 0:
        return None
    obs = abs(d.mean())
    signs = RNG.choice([-1.0, 1.0], size=(N_PERM, len(d)))
    null = np.abs((signs * d).mean(axis=1))
    return float(max(1, (null >= obs - 1e-12).sum()) / N_PERM)


def signflip_cluster(d, clusters):
    """Exact sign-flip over clusters (2^k patterns when k <= 14, else sampled)."""
    d, c = np.asarray(d, float), np.asarray(clusters)
    ok = ~np.isnan(d)
    d, c = d[ok], c[ok]
    if len(d) == 0:
        return None
    uc = sorted(set(c))
    sums = np.array([d[c == u].sum() for u in uc])
    n = len(d)
    obs = abs(sums.sum() / n)
    if len(uc) <= 14:
        pats = np.array(list(itertools.product([-1, 1], repeat=len(uc))), float)
    else:
        pats = RNG.choice([-1.0, 1.0], size=(N_PERM, len(uc)))
    null = np.abs(pats @ sums / n)
    return float(max(1, (null >= obs - 1e-12).sum()) / len(pats))


def dz(d):
    d = np.asarray(d, float)
    d = d[~np.isnan(d)]
    return r4(d.mean() / d.std(ddof=1)) if len(d) > 1 and d.std(ddof=1) > 0 else None


def bh(pvals):
    keys = [k for k, v in pvals.items() if v is not None]
    p = np.array([pvals[k] for k in keys])
    n = len(p)
    order = np.argsort(p)
    q = np.empty(n)
    prev = 1.0
    for rank in range(n - 1, -1, -1):
        i = order[rank]
        prev = min(prev, p[i] * n / (rank + 1))
        q[i] = prev
    return {k: float(q[i]) for i, k in enumerate(keys)}


def label_perm(values, labels, stat):
    """p-value for stat(values, labels) under permutation of labels."""
    values, labels = np.asarray(values, float), np.asarray(labels)
    ok = ~np.isnan(values)
    values, labels = values[ok], labels[ok]
    if len(values) < 4:
        return None, None
    obs = stat(values, labels)
    cnt = 0
    for _ in range(N_LABEL):
        if abs(stat(values, RNG.permutation(labels))) >= abs(obs) - 1e-12:
            cnt += 1
    return r4(obs), float(max(1, cnt) / N_LABEL)


def slope(values, labels):
    x = np.asarray(labels, float)
    if x.std() == 0:
        return 0.0
    return float(np.polyfit(x, values, 1)[0])


def between_var(values, labels):
    groups = [values[labels == g].mean() for g in sorted(set(labels))]
    return float(np.var(groups))


# ---------------- main ----------------
def fidelity(R):
    """Action-fidelity sensitivity check. For every trap question, was every scripted action step in the same thread
    actually executed (tool called with the right arguments) before the question? If a reveal step was skipped, the
    fresh value never entered the context and the question is unanswerable from the transcript. Reports, per layout,
    the execution rate of trap_reveal / trap_write steps and trap accuracy restricted to questions whose thread
    steps were all executed."""
    tasks = {t["task_id"]: t for t in json.load(open(os.path.join(ROOT, "corpus", "tasks.json")))["tasks"]}
    out = {}
    for L in LAYOUTS:
        c = {"reveal_total": 0, "reveal_exec": 0, "write_total": 0, "write_exec": 0, "act_total": 0, "act_exec": 0,
             "trap_total": 0, "trap_correct": 0, "cond_total": 0, "cond_correct": 0, "unrevealed_total": 0, "unrevealed_correct": 0}
        for r in R:
            if r["layout"] != L:
                continue
            T = tasks[r["task_id"]]
            ex = {st["step"]: st for st in r["steps"]}
            for st in r["steps"]:
                if st["kind"] == "action":
                    c["act_total"] += 1; c["act_exec"] += bool(st["exec_ok"])
                    if st["role"] == "trap_reveal":
                        c["reveal_total"] += 1; c["reveal_exec"] += bool(st["exec_ok"])
                    if st["role"] == "trap_write":
                        c["write_total"] += 1; c["write_exec"] += bool(st["exec_ok"])
                elif st["kind"] == "question" and st["trap"]:
                    thread = T["steps"][st["step"] - 1]["thread"]
                    prior = [ex[t["i"]] for t in T["steps"] if t["kind"] == "action" and t.get("thread") == thread and t["i"] < st["step"]]
                    ok = all(p["exec_ok"] for p in prior)
                    c["trap_total"] += 1; c["trap_correct"] += bool(st["correct"])
                    if ok:
                        c["cond_total"] += 1; c["cond_correct"] += bool(st["correct"])
                    else:
                        c["unrevealed_total"] += 1; c["unrevealed_correct"] += bool(st["correct"])
        if c["trap_total"]:
            out[L] = {"action_exec_rate": r4(c["act_exec"] / c["act_total"]), "reveal_exec_rate": r4(c["reveal_exec"] / c["reveal_total"]) if c["reveal_total"] else None,
                      "write_exec_rate": r4(c["write_exec"] / c["write_total"]) if c["write_total"] else None,
                      "trap_acc_all": r4(c["trap_correct"] / c["trap_total"]), "n_trap": c["trap_total"],
                      "trap_acc_thread_fully_executed": r4(c["cond_correct"] / c["cond_total"]) if c["cond_total"] else None, "n_thread_fully_executed": c["cond_total"],
                      "n_trap_with_skipped_thread_step": c["unrevealed_total"], "correct_despite_skipped": c["unrevealed_correct"]}
    return out


def hit_vs_miss_within_question(rows_rep):
    """Within-question version using the repeat battery: the same (task, step) question answered in several runs at an
    identical layout; some runs were served from cache and some were not. Paired difference (hit mean minus miss mean)
    over questions that have at least one of each, sign-flip test."""
    q = {}
    for r in rows_rep:
        tu = {t["step"]: t for t in r["turns"]}
        for st in r["steps"]:
            if st["kind"] == "question" and st["step"] in tu:
                key = (r["model"], r["layout"], r["task_id"], st["step"])
                q.setdefault(key, {"hit": [], "miss": []})["hit" if (tu[st["step"]]["cached_tokens"] or 0) > 0 else "miss"].append(float(st["correct"]))
    out = {}
    for (m, L) in sorted({(k[0], k[1]) for k in q}):
        d = [np.mean(v["hit"]) - np.mean(v["miss"]) for k, v in q.items() if k[0] == m and k[1] == L and v["hit"] and v["miss"]]
        n_q = sum(1 for k in q if k[0] == m and k[1] == L)
        out[f"{m}|{L}"] = {"n_questions": n_q, "n_questions_with_both": len(d), "hit_minus_miss": r4(np.mean(d)) if d else None,
                           "ci": boot_ci(np.array(d)) if len(d) >= 5 else [None, None], "p": signflip(np.array(d)) if len(d) >= 5 else None}
    return out


def cache_by_turn_kind(R):
    """Cache hit rate and cached share on action turns versus no-tool question turns, per layout."""
    out = {}
    for L in LAYOUTS:
        c = {"action": [], "question": []}; f = {"action": [], "question": []}
        for r in R:
            if r["layout"] != L:
                continue
            for t in r["turns"]:
                if t.get("retry_discarded") or t["kind"] not in c:
                    continue
                c[t["kind"]].append((t["cached_tokens"] or 0) > 0); f[t["kind"]].append((t["cached_tokens"] or 0) / max(1, t["prompt_tokens"] or 0))
        if c["action"]:
            out[L] = {"hit_rate_action_turns": r4(np.mean(c["action"])), "hit_rate_question_turns": r4(np.mean(c["question"])) if c["question"] else None,
                      "cached_share_action_turns": r4(np.mean(f["action"])), "cached_share_question_turns": r4(np.mean(f["question"])) if f["question"] else None,
                      "n_action_turns": len(c["action"]), "n_question_turns": len(c["question"])}
    return out


def hit_vs_miss(R):
    """Google substitute for the cache on/off control. Implicit caching is best-effort, so some question turns are
    served with zero cached tokens (a miss) and others with the prefix and history cached (a hit), at an identical
    layout and identical bytes. If caching changed outputs, accuracy would differ between the two groups.
    Two-sample label permutation over trap questions, per layout."""
    out = {}
    for L in LAYOUTS:
        hit, miss = [], []
        for r in R:
            if r["layout"] != L:
                continue
            tu = {t["step"]: t for t in r["turns"]}
            for st in r["steps"]:
                if st["kind"] == "question" and st["trap"] and st["step"] in tu:
                    t = tu[st["step"]]
                    (hit if (t["cached_tokens"] or 0) > 0 else miss).append(float(st["correct"]))
        if len(hit) >= 5 and len(miss) >= 5:
            a, b = np.array(hit), np.array(miss)
            obs = a.mean() - b.mean()
            pool = np.concatenate([a, b]); n = len(a); cnt = 0; N = 10000
            for _ in range(N):
                RNG.shuffle(pool); cnt += abs(pool[:n].mean() - pool[n:].mean()) >= abs(obs) - 1e-12
            out[L] = {"n_hit": int(len(a)), "n_miss": int(len(b)), "trap_acc_hit": r4(a.mean()), "trap_acc_miss": r4(b.mean()), "hit_minus_miss": r4(obs), "p": r4((cnt + 1) / (N + 1)),
                      "note": "unpaired; hits concentrate in later turns of longer episodes, so this comparison is confounded by length and chain; see within_question (repeat battery) for the paired version"}
            # stratified by (length, chain): mean of within-stratum differences weighted by stratum size
            strata = {}
            for r in R:
                if r["layout"] != L:
                    continue
                tu = {t["step"]: t for t in r["turns"]}
                for st in r["steps"]:
                    if st["kind"] == "question" and st["trap"] and st["step"] in tu:
                        strata.setdefault((r["length"], st["chain"]), {"hit": [], "miss": []})["hit" if (tu[st["step"]]["cached_tokens"] or 0) > 0 else "miss"].append(float(st["correct"]))
            ds = [(np.mean(v["hit"]) - np.mean(v["miss"]), min(len(v["hit"]), len(v["miss"]))) for v in strata.values() if v["hit"] and v["miss"]]
            if ds:
                w = np.array([x[1] for x in ds], float); d = np.array([x[0] for x in ds])
                out[L]["stratified_by_length_chain"] = {"n_strata": len(ds), "weighted_hit_minus_miss": r4(float((d * w).sum() / w.sum()))}
        else:
            out[L] = {"n_hit": int(len(hit)), "n_miss": int(len(miss)), "trap_acc_hit": r4(np.mean(hit)) if hit else None, "trap_acc_miss": r4(np.mean(miss)) if miss else None, "hit_minus_miss": None, "p": None}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit-export", type=int, default=0)
    args = ap.parse_args()
    rows = load()
    main_rows = [r for r in rows if r["battery"] == "none" and r["rep"] == 0 and r["phrasing"] == 1]
    out = {"generated_by": "experiments/analyze.py", "n_episodes_all": len(rows), "n_episodes_main": len(main_rows), "prices_per_mtok_2026-10-10": PRICES}
    tests = {}
    models = sorted({r["model"] for r in main_rows})
    out["models"] = {}
    for m in models:
        R = [r for r in main_rows if r["model"] == m]
        tasks = sorted({r["task_id"] for r in R})
        by = {(r["task_id"], r["layout"]): r for r in R}
        res = {"n_tasks": len(tasks), "n_episodes": len(R), "layouts": {}, "contrasts": {}, "interactions": {}, "frontier": {}, "d3": {}, "d5": {}}
        # per-layout means
        for L in LAYOUTS:
            rs = [r for r in R if r["layout"] == L]
            if not rs:
                continue
            d = {"n": len(rs)}
            for k in METRICS + ["prompt_tokens", "cached_tokens", "completion_tokens", "reasoning_tokens", "cache_write_tokens", "action_args_ok", "n_retries", "prefix_tokens"]:
                v = np.array([r[k] for r in rs], float)
                d[k] = {"mean": r4(np.nanmean(v)), "ci": boot_ci(v)}
            nc = sum(r["success"] for r in rs)
            d["usd_per_correct_task"] = r4(sum(r["cost"] for r in rs) / nc) if nc else None
            d["usd_per_correct_question"] = r4(sum(r["cost"] for r in rs) / sum(r["q_acc"] * len([s for s in r["steps"] if s["kind"] == "question"]) for r in rs)) if rs else None
            # by length / distractor / chain / domain
            d["by_length"] = {str(Lg): {"trap_acc": r4(np.nanmean([r["trap_acc"] for r in rs if r["length"] == Lg])),
                                        "neutral_acc": r4(np.nanmean([r["neutral_acc"] for r in rs if r["length"] == Lg])),
                                        "success": r4(np.nanmean([r["success"] for r in rs if r["length"] == Lg])),
                                        "cost": r4(np.nanmean([r["cost"] for r in rs if r["length"] == Lg])),
                                        "cache_frac": r4(np.nanmean([r["cache_frac"] for r in rs if r["length"] == Lg])), "n": sum(1 for r in rs if r["length"] == Lg)}
                              for Lg in sorted({r["length"] for r in rs})}
            d["by_distractor"] = {dd: {"trap_acc": r4(np.nanmean([r["trap_acc"] for r in rs if r["distractor"] == dd])),
                                       "neutral_acc": r4(np.nanmean([r["neutral_acc"] for r in rs if r["distractor"] == dd]))} for dd in ("low", "high")}
            d["by_trap_kind"] = {tk: {"acc": r4(np.mean([st["correct"] for r in rs for st in r["steps"] if st["kind"] == "question" and st["trap"] and st.get("trap_kind") == tk])),
                                      "n": sum(1 for r in rs for st in r["steps"] if st["kind"] == "question" and st["trap"] and st.get("trap_kind") == tk)} for tk in ("own", "external")}
            d["by_domain"] = {dm: {"trap_acc": r4(np.nanmean([r["trap_acc"] for r in rs if r["domain"] == dm])), "success": r4(np.nanmean([r["success"] for r in rs if r["domain"] == dm]))}
                              for dm in sorted({r["domain"] for r in rs})}
            steps = [s for r in rs for s in r["steps"] if s["kind"] == "question"]
            d["by_chain"] = {str(c): {"acc": r4(np.mean([s["correct"] for s in steps if s["trap"] and s["chain"] == c])), "n": sum(1 for s in steps if s["trap"] and s["chain"] == c)} for c in (1, 2, 3)}
            d["by_qkind"] = {q: {"acc": r4(np.mean([s["correct"] for s in steps if s["qkind"] == q])), "n": sum(1 for s in steps if s["qkind"] == q)} for q in sorted({s["qkind"] for s in steps})}
            d["trap_materialised_rate"] = r4(np.mean([s["stale_present"] for s in steps if s["trap"]])) if any(s["trap"] for s in steps) else None
            d["trap_acc_materialised_only"] = r4(np.mean([s["correct"] for s in steps if s["trap"] and s["stale_present"]])) if any(s["trap"] and s["stale_present"] for s in steps) else None
            d["parse_rate"] = r4(np.mean([s["parsed"] for s in steps]))
            # per-turn cache hit profile (turn index -> mean cached fraction)
            prof = defaultdict(list)
            for r in rs:
                for i, t in enumerate(r["turns"]):
                    if t["prompt_tokens"]:
                        prof[i].append((t["cached_tokens"] or 0) / t["prompt_tokens"])
            d["cache_profile_by_turn"] = {str(i): r4(np.mean(v)) for i, v in sorted(prof.items()) if len(v) >= 5}
            d["turn1_cache_hit_rate"] = r4(np.mean([1.0 if (r["turns"][0]["cached_tokens"] or 0) > 0 else 0.0 for r in rs if r["turns"]]))
            res["layouts"][L] = d
        # paired contrasts
        for a, b in CONTRASTS:
            common = [t for t in tasks if (t, a) in by and (t, b) in by]
            if len(common) < 5:
                continue
            for k in METRICS:
                da = np.array([by[(t, a)][k] for t in common], float)
                db = np.array([by[(t, b)][k] for t in common], float)
                d = da - db
                clusters = [by[(t, a)]["domain"] + ":" + by[(t, a)]["template"] for t in common]
                p = signflip(d)
                key = f"{m}:{k}:{a}-{b}"
                res["contrasts"][f"{k}:{a}-{b}"] = {"mean": r4(np.nanmean(d)), "ci": boot_ci(d), "p": p, "p_template_cluster": signflip_cluster(d, clusters),
                                                   "dz": dz(d), "n_pairs": int((~np.isnan(d)).sum()),
                                                   "ratio": r4(np.nanmean(da) / np.nanmean(db)) if np.nanmean(db) else None}
                if k in ("trap_acc", "neutral_acc", "success", "cost", "cache_frac"):
                    tests[key] = p
        # interactions: does the L1-L3 (and L4-L1) trap gap depend on length / distractor?
        for a, b in (("L1", "L3"), ("L4", "L1"), ("L1", "L2")):
            common = [t for t in tasks if (t, a) in by and (t, b) in by]
            if len(common) < 8:
                continue
            d = np.array([by[(t, a)]["trap_acc"] - by[(t, b)]["trap_acc"] for t in common], float)
            lens = [by[(t, a)]["length"] for t in common]
            dis = [1 if by[(t, a)]["distractor"] == "high" else 0 for t in common]
            s_len, p_len = label_perm(d, lens, slope)
            s_dis, p_dis = label_perm(d, dis, slope)
            res["interactions"][f"trap_gap:{a}-{b}:x_length"] = {"slope_per_call": s_len, "p": p_len,
                                                                 "gap_by_length": {str(Lg): r4(np.nanmean([x for x, l in zip(d, lens) if l == Lg])) for Lg in sorted(set(lens))}}
            res["interactions"][f"trap_gap:{a}-{b}:x_distractor"] = {"high_minus_low": s_dis, "p": p_dis}
            tests[f"{m}:int:{a}-{b}:length"] = p_len
            tests[f"{m}:int:{a}-{b}:distractor"] = p_dis
            # trap vs neutral: is the gap larger on trap steps than on neutral steps? (paired difference of differences)
            dn = np.array([by[(t, a)]["neutral_acc"] - by[(t, b)]["neutral_acc"] for t in common], float)
            dd = d - dn
            p_tn = signflip(dd)
            res["interactions"][f"gap:{a}-{b}:trap_minus_neutral"] = {"mean": r4(np.nanmean(dd)), "ci": boot_ci(dd), "p": p_tn}
            tests[f"{m}:int:{a}-{b}:trap_vs_neutral"] = p_tn
        # D3: recovery fraction of L4 relative to the L1->L3 gap, bootstrap over tasks
        common = [t for t in tasks if all((t, L) in by for L in ("L1", "L3", "L4"))]
        if len(common) >= 8:
            g13 = np.array([by[(t, "L3")]["trap_acc"] - by[(t, "L1")]["trap_acc"] for t in common], float)
            g14 = np.array([by[(t, "L4")]["trap_acc"] - by[(t, "L1")]["trap_acc"] for t in common], float)
            ok = ~np.isnan(g13) & ~np.isnan(g14)
            g13, g14 = g13[ok], g14[ok]
            rec = g14.mean() / g13.mean() if abs(g13.mean()) > 1e-9 else None
            idx = RNG.integers(0, len(g13), size=(N_BOOT, len(g13)))
            num, den = g14[idx].mean(axis=1), g13[idx].mean(axis=1)
            ratios = np.where(np.abs(den) > 1e-9, num / np.where(np.abs(den) > 1e-9, den, 1), np.nan)
            cf1 = np.array([by[(t, "L1")]["cache_frac"] for t in common], float)
            cf4 = np.array([by[(t, "L4")]["cache_frac"] for t in common], float)
            res["d3"] = {"recovery_fraction": r4(rec), "ci": [r4(np.nanpercentile(ratios, 2.5)), r4(np.nanpercentile(ratios, 97.5))] if rec is not None else [None, None],
                         "gap_L3_minus_L1": r4(g13.mean()), "gap_L4_minus_L1": r4(g14.mean()),
                         "cache_frac_L4_over_L1": r4(np.nanmean(cf4) / np.nanmean(cf1)) if np.nanmean(cf1) else None, "n": int(len(g13))}
        # frontier and D5 counterfactual pricing
        pin, pread, pwrite, pout = PRICES.get(m, (None, None, None, None))
        fr = {}
        for L in LAYOUTS:
            rs = [r for r in R if r["layout"] == L]
            if not rs:
                continue
            acc = float(np.mean([r["success"] for r in rs]))
            qacc = float(np.mean([r["q_acc"] for r in rs]))
            cost = float(np.mean([r["cost"] for r in rs]))
            fr[L] = {"success": r4(acc), "q_acc": r4(qacc), "usd_per_episode": r4(cost), "usd_per_correct_task": r4(cost / acc) if acc else None,
                     "cache_frac": r4(np.nanmean([r["cache_frac"] for r in rs]))}
            if pin is not None:
                cf = {}
                for mult in CF_MULT:
                    c = []
                    for r in rs:
                        unc = r["prompt_tokens"] - r["cached_tokens"]
                        c.append((unc * pin + r["cached_tokens"] * mult * pin + r["cache_write_tokens"] * pwrite + r["completion_tokens"] * pout) / 1e6)
                    cf[str(mult)] = {"usd_per_episode": r4(np.mean(c)), "usd_per_correct_task": r4(np.mean(c) / acc) if acc else None}
                fr[L]["counterfactual_read_price"] = cf
                # modelled cost at list prices vs billed (sanity)
                fr[L]["modelled_usd_per_episode_list_prices"] = r4(np.mean([((r["prompt_tokens"] - r["cached_tokens"]) * pin + r["cached_tokens"] * pread + r["cache_write_tokens"] * pwrite + r["completion_tokens"] * pout) / 1e6 for r in rs]))
        # Pareto set on (cost per episode low, success high)
        pts = [(L, fr[L]["usd_per_episode"], fr[L]["success"]) for L in fr]
        dominated = {L for L, c, a in pts if any((c2 <= c and a2 >= a and (c2 < c or a2 > a)) for L2, c2, a2 in pts if L2 != L)}
        for L in fr:
            fr[L]["on_frontier"] = L not in dominated
        res["frontier"] = fr
        res["fidelity"] = fidelity([r for r in R if r["steps"] is not None])
        res["cache_hit_vs_miss"] = hit_vs_miss(R)
        res["cache_by_turn_kind"] = cache_by_turn_kind(R)
        # D5: cheapest layout per correct task as a function of the cache-read multiplier
        if pin is not None and fr:
            d5 = {}
            for mult in CF_MULT:
                cands = {L: fr[L]["counterfactual_read_price"][str(mult)]["usd_per_correct_task"] for L in fr if fr[L]["counterfactual_read_price"][str(mult)]["usd_per_correct_task"] is not None}
                if cands:
                    d5[str(mult)] = {"cheapest": min(cands, key=cands.get), "usd_per_correct_task": {L: r4(v) for L, v in cands.items()}}
            res["d5"]["cheapest_per_correct_by_read_multiplier"] = d5
            flips = [k for k in d5]
            res["d5"]["billed_cheapest_per_correct"] = min(fr, key=lambda L: fr[L]["usd_per_correct_task"] if fr[L]["usd_per_correct_task"] is not None else 1e9)
        out["models"][m] = res

    # layout x family interaction on the L1-L3 trap gap (label permutation of model labels over tasks)
    out["family_interaction"] = {}
    gaps, labs = [], []
    for m in models:
        R = [r for r in main_rows if r["model"] == m]
        by = {(r["task_id"], r["layout"]): r for r in R}
        for t in sorted({r["task_id"] for r in R}):
            if (t, "L1") in by and (t, "L3") in by:
                gaps.append(by[(t, "L1")]["trap_acc"] - by[(t, "L3")]["trap_acc"]); labs.append(m)
    if len(set(labs)) >= 2:
        st, p = label_perm(gaps, labs, between_var)
        out["family_interaction"]["L1-L3_trap_gap_by_model"] = {"between_model_variance": st, "p": p,
                                                              "gap_by_model": {m: r4(np.nanmean([g for g, l in zip(gaps, labs) if l == m])) for m in models}}
        tests["family:int:L1-L3"] = p

    # the same interaction restricted to the tasks every model ran (the ladder subsets are nested)
    if len(models) >= 2:
        common = None
        for m in models:
            ts = {r["task_id"] for r in main_rows if r["model"] == m}
            common = ts if common is None else common & ts
        gaps, labs = [], []
        for m in models:
            by = {(r["task_id"], r["layout"]): r for r in main_rows if r["model"] == m}
            for t in sorted(common):
                if (t, "L1") in by and (t, "L3") in by:
                    gaps.append(by[(t, "L1")]["trap_acc"] - by[(t, "L3")]["trap_acc"]); labs.append(m)
        if len(set(labs)) >= 2 and len(gaps) >= 6:
            st, p = label_perm(gaps, labs, between_var)
            out["family_interaction"]["L1-L3_trap_gap_by_model_common_tasks"] = {"n_common_tasks": len(common), "between_model_variance": st, "p": p,
                "gap_by_model": {m: {"mean": r4(np.mean([g for g, l in zip(gaps, labs) if l == m])), "ci": boot_ci(np.array([g for g, l in zip(gaps, labs) if l == m]))} for m in models}}
            tests["family:int:L1-L3:common"] = p

    # batteries
    out["batteries"] = {}
    rep = [r for r in rows if r["battery"] == "repeat" or r["rep"] > 0]
    if rep:
        rep_cells = {(r["model"], r["task_id"], r["layout"]) for r in rep}
        out["batteries"]["cache_hit_vs_miss_within_question"] = hit_vs_miss_within_question([r for r in rows if (r["model"], r["task_id"], r["layout"]) in rep_cells and r["battery"] in ("none", "repeat") and r["phrasing"] == 1])
        cells = defaultdict(list)
        for r in rep + [r for r in main_rows if any(x["task_id"] == r["task_id"] and x["model"] == r["model"] and x["layout"] == r["layout"] for x in rep)]:
            cells[(r["model"], r["task_id"], r["layout"])].append(r)
        cells = {k: v for k, v in cells.items() if len(v) >= 2}
        out["batteries"]["repeat"] = {"n_cells": len(cells),
                                      "frac_cells_success_varies": r4(np.mean([len({x["success"] for x in v}) > 1 for v in cells.values()])) if cells else None,
                                      "frac_cells_trap_acc_varies": r4(np.mean([len({round(x["trap_acc"], 3) for x in v}) > 1 for v in cells.values()])) if cells else None,
                                      "mean_within_cell_sd_q_acc": r4(np.mean([np.std([x["q_acc"] for x in v], ddof=1) for v in cells.values()])) if cells else None}
    nocache = [r for r in rows if r["battery"] == "nocache"]
    if nocache:
        by_nc = {(r["model"], r["task_id"]): r for r in nocache}
        for m in sorted({r["model"] for r in nocache}):
            pairs = [(by_nc[(m, t)], x) for (mm, t), x in {(r["model"], r["task_id"]): r for r in main_rows if r["layout"] == "L1"}.items() if mm == m and (m, t) in by_nc]
            if pairs:
                d = np.array([a["q_acc"] - b["q_acc"] for a, b in pairs])
                out["batteries"][f"cache_on_off:{m}"] = {"n_pairs": len(pairs), "q_acc_nocache_minus_cached": r4(d.mean()), "ci": boot_ci(d), "p": signflip(d),
                                                         "cache_frac_nocache": r4(np.mean([a["cache_frac"] for a, _ in pairs])), "cache_frac_cached": r4(np.mean([b["cache_frac"] for _, b in pairs])),
                                                         "cost_nocache": r4(np.mean([a["cost"] for a, _ in pairs])), "cost_cached": r4(np.mean([b["cost"] for _, b in pairs]))}
                tests[f"{m}:battery:cache_on_off"] = out["batteries"][f"cache_on_off:{m}"]["p"]
    phr = [r for r in rows if r["phrasing"] == 2 and r["battery"] == "none"]
    if phr:
        by_p = {(r["model"], r["task_id"], r["layout"]): r for r in phr}
        for m in sorted({r["model"] for r in phr}):
            pairs = [(by_p[(m, r["task_id"], r["layout"])], r) for r in main_rows if (m, r["task_id"], r["layout"]) in by_p and r["model"] == m]
            if pairs:
                d = np.array([a["q_acc"] - b["q_acc"] for a, b in pairs])
                out["batteries"][f"phrasing:{m}"] = {"n_pairs": len(pairs), "q_acc_p2_minus_p1": r4(d.mean()), "ci": boot_ci(d), "p": signflip(d)}

    # audit codes (hand-coded file, if present)
    audit_path = os.path.join(ROOT, "results", "audit_sample.json")
    if os.path.exists(audit_path):
        aud = json.load(open(audit_path))
        codes = [a.get("code") for a in aud.get("items", []) if a.get("code")]
        out["audit"] = {"n": len(codes), "by_code": {c: codes.count(c) for c in sorted(set(codes))}, "coder": aud.get("coder"), "date": aud.get("date")}
    if args.audit_export:
        wrong = []
        for r in main_rows:
            for s in r["steps"]:
                if s["kind"] == "question" and not s["correct"]:
                    wrong.append({"model": r["model"], "task_id": r["task_id"], "layout": r["layout"], "step": s["step"], "trap": s["trap"], "chain": s["chain"], "qkind": s["qkind"],
                                  "record": s["record"], "answer": s["answer"], "actual": s["actual"], "answer_raw": s["answer_raw"], "stale_present": s["stale_present"], "code": None, "note": None})
        RNG2 = np.random.default_rng(7)
        # stratify: round-robin over (model, layout)
        groups = defaultdict(list)
        for w in wrong:
            groups[(w["model"], w["layout"])].append(w)
        for g in groups.values():
            RNG2.shuffle(g)
        sample = []
        while len(sample) < args.audit_export and any(groups.values()):
            for k in sorted(groups):
                if groups[k] and len(sample) < args.audit_export:
                    sample.append(groups[k].pop())
        json.dump({"coder": None, "date": None, "codes": ["stale_value", "distractor_record", "arithmetic_or_count", "abstain_or_unparsed", "other"], "n_wrong_total": len(wrong), "items": sample},
                  open(os.path.join(ROOT, "results", "audit_candidates.json"), "w"), indent=1)
        print("audit candidates:", len(sample), "of", len(wrong), "wrong answers")

    q = bh(tests)
    out["tests"] = {k: {"p": tests[k], "q_bh": q.get(k), "bh_survives_05": bool(q.get(k, 1) <= 0.05)} for k in sorted(tests) if tests[k] is not None}
    out["bh"] = {"n_tests": len([k for k in tests if tests[k] is not None]), "n_survive": int(sum(1 for k in q if q[k] <= 0.05)),
                 "effective_threshold": r4(max([tests[k] for k in q if q[k] <= 0.05], default=0.0))}
    spend = os.path.join(ROOT, "results", "spend.json")
    out["spend"] = json.load(open(spend)) if os.path.exists(spend) else None
    json.dump(out, open(OUT, "w"), indent=1, sort_keys=True)
    for m in models:
        print(m)
        for L in LAYOUTS:
            d = out["models"][m]["layouts"].get(L)
            if d:
                print(f"  {L}: n={d['n']} trap={d['trap_acc']['mean']} neutral={d['neutral_acc']['mean']} success={d['success']['mean']} cost=${d['cost']['mean']} cache={d['cache_frac']['mean']} hist_cache={d['hist_cache_frac']['mean']}")
        for k, v in out["models"][m]["contrasts"].items():
            if k.startswith("trap_acc") or k.startswith("cost") or k.startswith("cache_frac:"):
                print(f"  {k}: {v['mean']} {v['ci']} p={v['p']}")
    print("BH", out["bh"])


if __name__ == "__main__":
    main()
