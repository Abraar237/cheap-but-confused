#!/usr/bin/env python3
"""Build paper figures 2-6 from results/analysis.json only. Each figure prints the numbers it drew.
fig2_stale   : trap vs neutral accuracy by layout, per model (and by trap kind)
fig3_frontier: episode success vs billed USD per episode, layouts as points, per model; USD per correct task annotated
fig4_dose    : L1-L3 (and L4-L1) trap gap by episode length and distractor level, per model
fig5_cache   : cached-token fraction by turn index per layout (the mechanism of the cost side)
fig6_threshold: USD per correct task vs counterfactual cache-read price multiplier, per model"""

import json
import pathlib
import sys

import matplotlib.pyplot as plt
import numpy as np

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import style as S  # noqa: E402

S.apply()
ROOT = HERE.parent
A = json.load(open(ROOT / "results" / "analysis.json"))
OUT = ROOT / "paper" / "iclr" / "assets"
OUT.mkdir(parents=True, exist_ok=True)
DOCS = ROOT / "docs" / "assets"
DOCS.mkdir(parents=True, exist_ok=True)

LABEL = {"google/gemini-2.5-flash": "Gemini 2.5 Flash", "google/gemini-3.1-flash-lite": "Gemini 3.1 Flash-Lite", "google/gemini-3.5-flash-lite": "Gemini 3.5 Flash-Lite", "google/gemini-3.6-flash": "Gemini 3.6 Flash",
         "anthropic/claude-haiku-5.5": "Claude Haiku 5.5", "openai/gpt-5-mini": "GPT-5 mini", "openai/gpt-5-nano": "GPT-5 nano", "openai/gpt-5.6-luna": "GPT-5.6 Luna"}
LAYOUTS = ["L1", "L2", "L3", "L4"]
LNAME = {"L1": "L1 cache-optimal", "L2": "L2 reordered", "L3": "L3 pruned", "L4": "L4 hybrid"}
LCOL = {"L1": S.SLATE, "L2": S.SHELF, "L3": S.HOT, "L4": S.GOOD}
MODELS = [m for m in LABEL if m in A["models"]] + [m for m in A["models"] if m not in LABEL]


def lab(m):
    return LABEL.get(m, m)


def save(fig, name):
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight")
    fig.savefig(DOCS / f"{name}.png", bbox_inches="tight", dpi=200)
    plt.close(fig)
    print("wrote", name)


def err(v):
    m, (lo, hi) = v["mean"], v["ci"]
    if lo is None or hi is None:
        return [[0], [0]]
    return [[m - lo], [hi - m]]


def fig2_stale():
    """Accuracy by layout on three kinds of question step: trap steps whose update was the agent's own write,
    trap steps whose update was external (revealed inside a listing row), and neutral steps."""
    n = len(MODELS)
    fig, axes = plt.subplots(1, n, figsize=(4.4 * n + 1, 3.9), squeeze=False)
    drew = {}
    KINDS = [("own", "trap: own update", 1.0, None), ("external", "trap: external update", 1.0, None), ("neutral", "neutral step", 0.35, "//")]
    for ax, m in zip(axes[0], MODELS):
        Ls = [L for L in LAYOUTS if L in A["models"][m]["layouts"]]
        w = 0.26
        for i, L in enumerate(Ls):
            d = A["models"][m]["layouts"][L]
            vals = {"own": d.get("by_trap_kind", {}).get("own", {}).get("acc"), "external": d.get("by_trap_kind", {}).get("external", {}).get("acc"), "neutral": d["neutral_acc"]["mean"]}
            for j, (k, label, alpha, hatch) in enumerate(KINDS):
                v = vals[k]
                if v is None:
                    continue
                x = i + (j - 1) * w
                ax.bar(x, v, w * 0.92, color=LCOL[L], alpha=alpha, hatch=hatch, edgecolor="white" if hatch else "none", linewidth=0.6, label=label if i == 0 else None)
                if k == "external":
                    ax.errorbar(x, d["trap_acc"]["mean"] * 0 + v, yerr=None, color="none")
                    ax.text(x, v + 0.02, f"{v:.2f}", ha="center", fontsize=8, color=LCOL[L], fontweight="bold")
                else:
                    ax.text(x, v + 0.02, f"{v:.2f}", ha="center", fontsize=6.5, color=S.MUTED)
            drew[(m, L)] = {k: (round(v, 3) if v is not None else None) for k, v in vals.items()}
        ax.set_xticks(range(len(Ls)))
        ax.set_xticklabels([LNAME[L].replace(" ", "\n", 1) for L in Ls], fontsize=8)
        ax.set_ylim(0, 1.12)
        ax.set_ylabel("step accuracy")
        S.eyebrow(ax, lab(m), y=1.06)
        S.clean(ax)
    best = max(axes[0], key=lambda a: len(a.get_legend_handles_labels()[0]))
    h, l = best.get_legend_handles_labels()
    fig.legend(h, l, frameon=False, fontsize=8, loc="lower center", bbox_to_anchor=(0.5, -0.06), ncol=3)
    fig.suptitle("THE SAME INFORMATION, FOUR LAYOUTS: ONLY EXTERNAL-UPDATE TRAPS SEPARATE THEM", x=0.01, ha="left", fontsize=9, color=S.MUTED, y=1.04)
    fig.tight_layout()
    save(fig, "fig2_stale")
    print("fig2:", drew)


def fig3_frontier():
    n = len(MODELS)
    fig, axes = plt.subplots(1, n, figsize=(4.2 * n + 1, 3.8), squeeze=False)
    drew = {}
    for ax, m in zip(axes[0], MODELS):
        fr = A["models"][m]["frontier"]
        for L in LAYOUTS:
            if L not in fr:
                continue
            x, y = fr[L]["usd_per_episode"] * 100, fr[L]["success"]
            ax.scatter(x, y, s=90 if fr[L]["on_frontier"] else 55, color=LCOL[L], edgecolor="black" if fr[L]["on_frontier"] else "none", zorder=3)
            upc = fr[L]["usd_per_correct_task"]
            ax.annotate(f"{LNAME[L]}\n{upc * 100:.2f}¢ per correct task" if upc else LNAME[L], (x, y), textcoords="offset points", xytext=(6, -4), fontsize=7.5, color=LCOL[L])
            drew[(m, L)] = (round(x, 3), round(y, 3), round(upc * 100, 3) if upc else None)
        ax.set_xlabel("billed USD per episode (cents)")
        ax.set_ylabel("episode success (all questions right)")
        ax.set_ylim(0, 1.05)
        ax.set_xlim(0, max([fr[L]["usd_per_episode"] * 100 for L in fr]) * 1.45)
        S.eyebrow(ax, lab(m) + ": accuracy vs billed cost", y=1.06)
        S.clean(ax)
    fig.suptitle("THE FRONTIER: OUTLINED POINTS ARE PARETO-OPTIMAL", x=0.01, ha="left", fontsize=9, color=S.MUTED, y=1.04)
    fig.tight_layout()
    save(fig, "fig3_frontier")
    print("fig3:", drew)


def fig4_dose():
    n = len(MODELS)
    fig, axes = plt.subplots(1, n, figsize=(4.2 * n + 1, 3.6), squeeze=False)
    drew = {}
    for ax, m in zip(axes[0], MODELS):
        lay = A["models"][m]["layouts"]
        lens = sorted(int(k) for k in lay["L1"]["by_length"])
        for L in LAYOUTS:
            if L not in lay:
                continue
            ys = [lay[L]["by_length"][str(k)]["trap_acc"] for k in lens]
            ax.plot(lens, ys, marker="o", color=LCOL[L], label=LNAME[L], lw=1.6)
            drew[(m, L)] = ys
        ax.set_xticks(lens)
        ax.set_xlabel("tool calls per episode")
        ax.set_ylabel("stale-trap step accuracy")
        ax.set_ylim(0, 1.05)
        S.eyebrow(ax, lab(m) + ": dose-response in length", y=1.06)
        S.clean(ax)
    axes[0][0].legend(frameon=False, fontsize=8, loc="lower left")
    fig.tight_layout()
    save(fig, "fig4_dose")
    print("fig4:", drew)


def fig5_cache():
    n = len(MODELS)
    fig, axes = plt.subplots(1, n, figsize=(4.2 * n + 1, 3.4), squeeze=False)
    drew = {}
    for ax, m in zip(axes[0], MODELS):
        lay = A["models"][m]["layouts"]
        for L in LAYOUTS:
            if L not in lay:
                continue
            prof = lay[L]["cache_profile_by_turn"]
            xs = sorted(int(k) for k in prof)
            ys = [prof[str(k)] for k in xs]
            ax.plot([x + 1 for x in xs], ys, color=LCOL[L], label=f"{LNAME[L]} (overall {lay[L]['cache_frac']['mean']:.2f})", lw=1.6)
            drew[(m, L)] = round(lay[L]["cache_frac"]["mean"], 3)
        ax.set_xlabel("turn within episode")
        ax.set_ylabel("cached share of prompt tokens")
        ax.set_ylim(0, 1.02)
        S.eyebrow(ax, lab(m) + ": where the cache reads come from", y=1.06)
        S.clean(ax)
        ax.legend(frameon=False, fontsize=7.5, loc="lower right")
    fig.tight_layout()
    save(fig, "fig5_cache")
    print("fig5:", drew)


def fig6_threshold():
    n = len(MODELS)
    fig, axes = plt.subplots(1, n, figsize=(4.2 * n + 1, 3.6), squeeze=False)
    drew = {}
    for ax, m in zip(axes[0], MODELS):
        fr = A["models"][m]["frontier"]
        for L in LAYOUTS:
            if L not in fr or "counterfactual_read_price" not in fr[L]:
                continue
            cf = fr[L]["counterfactual_read_price"]
            xs = sorted(float(k) for k in cf)
            ys = [cf[str(k) if str(k) in cf else repr(k)]["usd_per_correct_task"] for k in xs]
            ys = [(y * 100 if y is not None else np.nan) for y in ys]
            ax.plot(xs, ys, marker="o", ms=3.5, color=LCOL[L], label=LNAME[L], lw=1.6)
            drew[(m, L)] = [round(y, 3) if y == y else None for y in ys]
        pr = A["prices_per_mtok_2026-10-10"].get(m)
        if pr:
            ax.axvline(pr[1] / pr[0], color=S.FAINT, lw=1, ls="--")
            ax.text(pr[1] / pr[0], ax.get_ylim()[1] * 0.97, " list price", fontsize=7.5, color=S.MUTED, va="top")
        ax.set_xscale("symlog", linthresh=0.01)
        ax.set_xlabel("cache-read price as a multiple of the input price")
        ax.set_ylabel("USD per correct task (cents)")
        S.eyebrow(ax, lab(m) + ": which layout is cheapest per correct task", y=1.06)
        S.clean(ax)
    axes[0][0].legend(frameon=False, fontsize=8, loc="upper left")
    fig.tight_layout()
    save(fig, "fig6_threshold")
    print("fig6:", drew)


if __name__ == "__main__":
    fig2_stale()
    fig3_frontier()
    fig4_dose()
    fig5_cache()
    fig6_threshold()
