#!/usr/bin/env python3
"""Three concept GIFs in the clean flat-chart style: 840x840, white card, flat bars, monospace numerals,
Helvetica labels, replay pill, ~80 ms/frame. Numbers from results/analysis.json (first model in ORDER)."""
import json, math, pathlib
from PIL import Image, ImageDraw, ImageFont

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE.parent / "docs" / "assets" / "gifs"
OUT.mkdir(parents=True, exist_ok=True)
A = json.loads((HERE.parent / "results" / "analysis.json").read_text())
ORDER = ["google/gemini-3.1-flash-lite", "anthropic/claude-haiku-5.5", "openai/gpt-5-mini", "openai/gpt-5-nano"]
LABEL = {"google/gemini-3.1-flash-lite": "Gemini 3.1 Flash-Lite", "anthropic/claude-haiku-5.5": "Claude Haiku 5.5", "openai/gpt-5-mini": "GPT-5 mini", "openai/gpt-5-nano": "GPT-5 nano"}
MODELS = [m for m in ORDER if m in A["models"]] + [m for m in A["models"] if m not in ORDER]
M = MODELS[0]
W = H = 840
INK = (22, 19, 13); INK2 = (58, 53, 43); MUTED = (109, 102, 90); FAINT = (164, 156, 140); RULE = (231, 226, 213); BG = (255, 255, 255)
SLATE = (21, 94, 140); HOT = (179, 0, 107); SHELF = (192, 100, 26); GOOD = (28, 122, 85)
LCOL = {"L1": SLATE, "L2": SHELF, "L3": HOT, "L4": GOOD}
LNAME = {"L1": "L1 cache-optimal", "L2": "L2 reordered", "L3": "L3 pruned", "L4": "L4 hybrid"}
MENLO = "/System/Library/Fonts/Menlo.ttc"; HELV = "/System/Library/Fonts/Helvetica.ttc"
def F(path, size, index=0): return ImageFont.truetype(path, size, index=index)
f_title = F(HELV, 30, 1); f_sub = F(HELV, 15); f_note = F(HELV, 13); f_label = F(HELV, 17); f_num = F(MENLO, 22); f_big = F(MENLO, 40, 1)
N = 110
def ease(t): return 0 if t <= 0 else 1 if t >= 1 else 0.5 - 0.5 * math.cos(math.pi * t)
def seg(t, a, b): return ease((t - a) / (b - a)) if b > a else 1.0
def mix(c1, c2, f): return tuple(int(a + (b - a) * f) for a, b in zip(c1, c2))
def card(d):
    d.rectangle([0, 0, W, H], fill=BG); d.rectangle([14, 14, W - 14, H - 14], outline=RULE, width=2)
def title_block(d, title, sub):
    d.text((W // 2, 62), title, font=f_title, fill=INK, anchor="mm"); d.text((W // 2, 96), sub.upper(), font=f_sub, fill=MUTED, anchor="mm")
def footer(d, text): d.text((W // 2, H - 44), text.upper(), font=f_note, fill=FAINT, anchor="mm")
def hbar(d, x, y, w, h, frac, color):
    d.rectangle([x, y, x + w, y + h], outline=RULE, width=2)
    fw = int(w * max(0.0, min(1.0, frac)))
    if fw > 5: d.rectangle([x + 2, y + 2, x + fw - 2, y + h - 2], fill=color)
def replay(d, t):
    if t > 0.9:
        d.rounded_rectangle([W - 112, H - 86, W - 40, H - 62], radius=12, outline=FAINT, width=1); d.text((W - 76, H - 74), "replay", font=f_note, fill=FAINT, anchor="mm")
def save(frames, name):
    frames[0].save(OUT / name, save_all=True, append_images=frames[1:], duration=80, loop=0, optimize=True)
    print(name, len(frames), "frames,", (OUT / name).stat().st_size // 1024, "KB")

lay = A["models"][M]["layouts"]; fr = A["models"][M]["frontier"]
Ls = [L for L in ("L1", "L2", "L3", "L4") if L in lay]

def gif_trap():
    frames = []
    for fi in range(N):
        t = fi / N; im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im); card(d)
        title_block(d, "Same information, four layouts.", f"external-update trap accuracy, {LABEL.get(M, M)}, {lay['L1']['by_trap_kind']['external']['n']} questions per layout")
        for i, L in enumerate(Ls):
            y = 170 + i * 120; g = seg(t, 0.05 + 0.15 * i, 0.32 + 0.15 * i)
            v = lay[L]["by_trap_kind"]["external"]["acc"]; nv = lay[L]["neutral_acc"]["mean"]; ov = lay[L]["by_trap_kind"]["own"]["acc"]
            d.text((70, y), LNAME[L], font=f_label, fill=INK, anchor="lm")
            hbar(d, 70, y + 22, 540, 32, v * g, LCOL[L])
            if g > 0.98:
                d.text((630, y + 38), f"{v*100:.0f}%", font=f_big, fill=LCOL[L], anchor="lm")
                d.text((70, y + 70), f"own-update traps {ov*100:.0f}%  ·  neutral steps {nv*100:.0f}%  ·  cached {lay[L]['cache_frac']['mean']*100:.0f}%", font=f_note, fill=MUTED, anchor="lm")
        gn = seg(t, 0.7, 0.85)
        if gn > 0:
            gap = lay["L3"]["by_trap_kind"]["external"]["acc"] - lay["L1"]["by_trap_kind"]["external"]["acc"] if "L3" in lay else 0
            d.text((W // 2, 668), f"{gap*100:.0f} points lost when the world changes behind the agent", font=f_num, fill=mix(BG, HOT, gn), anchor="mm")
            d.text((W // 2, 700), "own updates and neutral steps: 100% under every layout", font=f_label, fill=mix(BG, MUTED, gn), anchor="mm")
        footer(d, "StaleTrap · 720 question steps · billed by the provider"); replay(d, t); frames.append(im)
    save(frames, "same-information-four-layouts.gif")

def gif_cost():
    frames = []
    mx = max(fr[L]["usd_per_correct_task"] or 0 for L in Ls) * 1.15
    for fi in range(N):
        t = fi / N; im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im); card(d)
        title_block(d, "What does a correct task cost?", f"billed USD per correct episode, {LABEL.get(M, M)}")
        for i, L in enumerate(Ls):
            y = 170 + i * 120; g = seg(t, 0.05 + 0.15 * i, 0.32 + 0.15 * i)
            v = fr[L]["usd_per_correct_task"] or 0
            d.text((70, y), LNAME[L], font=f_label, fill=INK, anchor="lm")
            hbar(d, 70, y + 22, 540, 32, (v / mx) * g, LCOL[L])
            if g > 0.98:
                d.text((630, y + 38), f"{v*100:.2f}¢", font=f_big, fill=LCOL[L], anchor="lm")
                d.text((70, y + 70), f"{fr[L]['usd_per_episode']*100:.2f}¢ per episode  ·  success {fr[L]['success']*100:.0f}%  ·  cached {fr[L]['cache_frac']*100:.0f}%", font=f_note, fill=MUTED, anchor="lm")
        gn = seg(t, 0.7, 0.85)
        if gn > 0:
            best = min(Ls, key=lambda L: fr[L]["usd_per_correct_task"] or 9)
            d.text((W // 2, 680), f"cheapest per correct task: {LNAME[best]}", font=f_num, fill=mix(BG, GOOD, gn), anchor="mm")
        footer(d, "provider-reported cached tokens and usage.cost · no price-sheet arithmetic"); replay(d, t); frames.append(im)
    save(frames, "cost-per-correct-task.gif")

def gif_cache():
    frames = []
    prof = {L: lay[L]["cache_profile_by_turn"] for L in Ls}
    xs = sorted({int(k) for L in Ls for k in prof[L]})
    for fi in range(N):
        t = fi / N; im = Image.new("RGB", (W, H), BG); d = ImageDraw.Draw(im); card(d)
        title_block(d, "Where the cache reads come from.", f"cached share of prompt tokens by turn, {LABEL.get(M, M)}")
        x0, y0, w, h = 90, 170, 560, 440
        d.rectangle([x0, y0, x0 + w, y0 + h], outline=RULE, width=2)
        for k in (0.25, 0.5, 0.75):
            yy = y0 + h - k * h; d.line([(x0, yy), (x0 + w, yy)], fill=RULE, width=1); d.text((x0 - 8, yy), f"{int(k*100)}%", font=f_note, fill=MUTED, anchor="rm")
        g = seg(t, 0.05, 0.75)
        n_show = max(2, int(len(xs) * g))
        for L in Ls:
            pts = [(x0 + (i / max(1, len(xs) - 1)) * w, y0 + h - prof[L].get(str(k), 0) * h) for i, k in enumerate(xs[:n_show]) if str(k) in prof[L]]
            if len(pts) > 1: d.line(pts, fill=LCOL[L], width=4)
        if g >= 0.75:
            ends = sorted(((y0 + h - prof[L].get(str(xs[n_show - 1]), 0) * h, L) for L in Ls if str(xs[n_show - 1]) in prof[L]), key=lambda e: e[0])
            placed = []
            for yy, L in ends:
                if placed and yy - placed[-1] < 18: yy = placed[-1] + 18
                placed.append(yy)
                d.text((x0 + w + 8, yy), f"{LNAME[L]} {lay[L]['cache_frac']['mean']*100:.0f}%", font=f_note, fill=LCOL[L], anchor="lm")
        d.text((x0 + w // 2, y0 + h + 24), "turn within the episode", font=f_note, fill=MUTED, anchor="mm")
        footer(d, "the static prefix is identical across layouts; the history is where they differ"); replay(d, t); frames.append(im)
    save(frames, "where-the-cache-reads-come-from.gif")

gif_trap(); gif_cost(); gif_cache()
