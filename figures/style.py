"""House figure style for the cache-layout paper. Import everywhere."""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

SLATE = "#155e8c"   # untouched condition / primary series
HOT = "#b3006b"     # the intervention
SHELF = "#c0641a"   # second comparison
GOOD = "#1c7a55"    # third comparison
INK = "#16130d"
INK2 = "#3a352b"
MUTED = "#6d665a"
FAINT = "#a49c8c"
RULE = "#e7e2d5"
SURFACE = "#ffffff"

def apply():
    plt.rcParams.update({
        "font.family": "serif",
        "font.serif": ["Times New Roman", "Times", "Nimbus Roman"],
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE, "savefig.dpi": 300,
        "axes.edgecolor": RULE, "axes.linewidth": 0.8,
        "axes.spines.top": False, "axes.spines.right": False,
        "xtick.color": MUTED, "ytick.color": MUTED,
        "xtick.labelsize": 9, "ytick.labelsize": 9,
        "axes.labelcolor": MUTED, "axes.labelsize": 9.5,
        "text.color": INK,
    })

def eyebrow(ax, text, y=1.06):
    ax.text(0, y, text.upper(), transform=ax.transAxes, fontsize=9,
            color=MUTED, ha="left", va="bottom",
            fontfamily="serif").set_stretch("semi-expanded")

def clean(ax):
    ax.grid(axis="y", color=RULE, lw=0.6, zorder=0)
    ax.set_axisbelow(True)
