#!/usr/bin/env python3
"""Research film for "Cheap but Confused?": 1920x1080 @ 60 fps, phrase-anchored to video/words.json (from film_tts.py).
Same visual system as the site and the paper figures (cream card, flat bars, Menlo bold titles, Helvetica labels,
monospace numerals, marker-pen annotations landing on the spoken number). Numbers come from results/analysis.json.
Usage: python3 build_film.py check | frames"""
import json, math, pathlib, shutil, sys
from PIL import Image, ImageDraw, ImageFont
HERE = pathlib.Path(__file__).resolve().parent; ROOT = HERE.parent; FRAMES = HERE / "frames"
W, H, FPS = 1920, 1080, 60
INK = (22, 19, 13); INK2 = (58, 53, 43); MUTED = (109, 102, 90); FAINT = (164, 156, 140); RULE = (231, 226, 213); BG = (253, 252, 250)
SLATE = (21, 94, 140); HOT = (179, 0, 107); SHELF = (192, 100, 26); GOOD = (28, 122, 85); PURPLE = (122, 111, 155)
LCOL = {"L1": SLATE, "L2": SHELF, "L3": HOT, "L4": GOOD}
LNAME = {"L1": "L1 append-only", "L2": "L2 reordered", "L3": "L3 pruned", "L4": "L4 hybrid note"}
MENLO = "/System/Library/Fonts/Menlo.ttc"; HELV = "/System/Library/Fonts/Helvetica.ttc"
def F(p, s, i=0): return ImageFont.truetype(p, s, index=i)
f_h1 = F(MENLO, 72, 1); f_h2 = F(MENLO, 50, 1); f_sub = F(HELV, 30); f_lab = F(HELV, 32); f_note = F(HELV, 26); f_eyebrow = F(HELV, 22)
f_num = F(MENLO, 40); f_big = F(MENLO, 120, 1); f_mono = F(MENLO, 30); f_mid = F(MENLO, 60, 1); f_body = F(HELV, 36); f_small = F(MENLO, 24)

A = json.load(open(ROOT / "results" / "analysis.json"))
MAIN = "google/gemini-3.1-flash-lite"
M = A["models"][MAIN]
LAD = [m for m in ("google/gemini-2.5-flash", "google/gemini-3.1-flash-lite", "google/gemini-3.6-flash") if m in A["models"]]
LADLAB = {"google/gemini-2.5-flash": "Gemini 2.5 Flash", "google/gemini-3.1-flash-lite": "Gemini 3.1 Flash-Lite", "google/gemini-3.6-flash": "Gemini 3.6 Flash"}
def ext(m, L):
    d = A["models"][m]["layouts"].get(L)
    return None if not d else d.get("by_trap_kind", {}).get("external", {}).get("acc")
AUD = json.load(open(ROOT / "results" / "audit_sample.json"))
DB = json.load(open(HERE / "words.json")); CUE = {c["id"]: c for c in DB["cues"]}; TOTAL = DB["total"]
URL = "abraar237.github.io/cheap-but-confused"

def at(cue, phrase):
    c = CUE[cue]; words = [w["w"].lower().strip(".,;:!?\"'") for w in c["words"]]; target = [w.lower().strip(".,;:!?\"'") for w in phrase.split()]
    for i in range(len(words) - len(target) + 1):
        if words[i:i + len(target)] == target:
            return c["start"] + c["words"][i]["s"]
    raise KeyError(f"phrase not found in {cue}: {phrase!r}")
def cue_start(cue): return CUE[cue]["start"]
def ease(x): return 0 if x <= 0 else 1 if x >= 1 else 0.5 - 0.5 * math.cos(math.pi * x)
def seg(t, a, b): return ease((t - a) / (b - a)) if b > a else (1.0 if t >= b else 0.0)
def mix(c1, c2, f): return tuple(int(a + (b - a) * f) for a, b in zip(c1, c2))

def base(d, t):
    d.rectangle([0, 0, W, H], fill=BG); d.rectangle([28, 28, W - 28, H - 28], outline=RULE, width=3)
    d.text((70, 62), "C H E A P   B U T   C O N F U S E D ?", font=f_eyebrow, fill=FAINT)
    d.text((W - 70, 62), "R E S E A R C H   F I L M", font=f_eyebrow, fill=FAINT, anchor="ra")
def hbar(d, x, y, w, h, frac, color, outline=True):
    if outline: d.rectangle([x, y, x + w, y + h], outline=RULE, width=3)
    fw = int(w * max(0.0, min(1.0, frac)))
    if fw > 6: d.rectangle([x + 3, y + 3, x + fw - 3, y + h - 3], fill=color)
def underline(d, x0, x1, y, g, color=HOT):
    if g <= 0: return
    d.line([(x0, y), (x0 + (x1 - x0) * g, y + 3)], fill=mix(BG, color, 0.55), width=9)
def ring(d, cx, cy, r, g, color=HOT):
    if g <= 0: return
    d.arc([cx - r, cy - r * 0.6, cx + r, cy + r * 0.6], start=-90, end=-90 + 360 * g, fill=mix(BG, color, 0.6), width=7)
def block(d, x, y, w, h, label, col, g, sub=None, strike=False):
    if g <= 0: return
    d.rounded_rectangle([x, y, x + w, y + h], radius=10, outline=mix(BG, col, g), width=3, fill=mix(BG, col, 0.08 * g))
    d.text((x + w / 2, y + h / 2 - (10 if sub else 0)), label, font=f_small, fill=mix(BG, INK, g), anchor="mm")
    if sub: d.text((x + w / 2, y + h / 2 + 18), sub, font=F(HELV, 18), fill=mix(BG, MUTED, g), anchor="mm")
    if strike: d.line([(x + 8, y + h / 2), (x + w - 8, y + h / 2)], fill=mix(BG, HOT, g), width=4)

# ---------------------------------------------------------------- scenes
def context_strip(d, t, y, labels, cols, ta, step=0.22, x0=160, bw=150, bh=70, gap=14):
    for i, (lab, col) in enumerate(zip(labels, cols)):
        block(d, x0 + i * (bw + gap), y, bw, bh, lab, col, seg(t, ta + i * step, ta + i * step + 0.5))

def s1(d, t):
    d.text((W // 2, 200), "Cheap but confused?", font=f_h1, fill=INK, anchor="mm")
    d.text((W // 2, 275), "the accuracy cost of cache-optimized context layouts", font=f_sub, fill=MUTED, anchor="mm")
    labs = ["system", "tools", "obs 1", "obs 2", "obs 3", "obs 4", "obs 5", "obs 6", "new"]
    cols = [SLATE, SLATE] + [INK2] * 6 + [GOOD]
    context_strip(d, t, 420, labs, cols, cue_start("p1") + 0.3, step=0.18)
    g = seg(t, at("p1", "Append every"), at("p1", "Append every") + 0.8)
    if g > 0: d.text((160, 530), "append at the end; never reorder, never delete", font=f_lab, fill=mix(BG, INK, g), anchor="lm")
    g2 = seg(t, at("p1", "one tenth"), at("p1", "one tenth") + 0.9)
    if g2 > 0:
        d.rounded_rectangle([160, 620, 900, 760], radius=16, outline=mix(BG, HOT, g2), width=4)
        d.text((190, 660), "cached input tokens", font=f_note, fill=mix(BG, MUTED, g2), anchor="lm")
        d.text((190, 720), "about 0.1x the price", font=F(MENLO, 44, 1), fill=mix(BG, HOT, g2), anchor="lm")
    g3 = seg(t, at("p1", "exactly the same"), at("p1", "exactly the same") + 0.8)
    if g3 > 0:
        d.text((960, 690), "only if the prompt starts with the same bytes", font=f_body, fill=mix(BG, INK, g3), anchor="lm")
        underline(d, 960, 1760, 722, seg(t, at("p1", "same bytes"), at("p1", "same bytes") + 0.7))

def s2(d, t):
    d.text((W // 2, 180), "The side effect: nothing is ever removed", font=f_h2, fill=INK, anchor="mm")
    g = seg(t, at("p2", "When a value"), at("p2", "When a value") + 0.8)
    labs = ["system", "tools", "qty = 55", "ship 10", "listing", "...", "question"]
    cols = [SLATE, SLATE, SHELF, INK2, HOT, INK2, GOOD]
    context_strip(d, t, 380, labs, cols, cue_start("p2") + 0.2, step=0.15)
    g2 = seg(t, at("p2", "the old value"), at("p2", "the old value") + 0.8)
    if g2 > 0:
        d.text((160 + 2 * 164 + 75, 500), "stale", font=f_note, fill=mix(BG, SHELF, g2), anchor="mm")
        d.text((160 + 4 * 164 + 75, 500), "row: qty = 4", font=f_note, fill=mix(BG, HOT, g2), anchor="mm")
        ring(d, 160 + 2 * 164 + 75, 415, 95, seg(t, at("p2", "old value stays"), at("p2", "old value stays") + 0.8), SHELF)
    g3 = seg(t, at("p2", "Does the layout"), at("p2", "Does the layout") + 0.9)
    if g3 > 0:
        d.text((W // 2, 700), "Does the layout that caching rewards cost accuracy,", font=f_body, fill=mix(BG, INK, g3), anchor="mm")
        d.text((W // 2, 760), "when the information in the context is held fixed?", font=f_body, fill=mix(BG, INK, g3), anchor="mm")
        underline(d, 560, 1360, 792, seg(t, at("p2", "held fixed"), at("p2", "held fixed") + 0.7))

def s3(d, t):
    d.text((W // 2, 170), "StaleTrap: a testbed where every stale value is known", font=f_h2, fill=INK, anchor="mm")
    ge = seg(t, cue_start("p3") + 0.2, cue_start("p3") + 0.8)
    if ge > 0: d.text((W // 2, 225), "three domains, 29 tools, a deterministic executor, every trap known by construction", font=f_note, fill=mix(BG, MUTED, ge), anchor="mm")
    doms = [("warehouse", at("p3", "a warehouse")), ("meeting calendar", at("p3", "a meeting")), ("support tickets", at("p3", "a support"))]
    for i, (name, ta) in enumerate(doms):
        g = seg(t, ta, ta + 0.6)
        if g > 0:
            x = 200 + i * 520
            d.rounded_rectangle([x, 260, x + 440, 350], radius=14, outline=mix(BG, SLATE, g), width=4)
            d.text((x + 220, 305), name, font=f_lab, fill=mix(BG, SLATE, g), anchor="mm")
    g = seg(t, at("p3", "six to thirty"), at("p3", "six to thirty") + 1.2)
    if g > 0:
        n = 18
        for i in range(n):
            gi = seg(t, at("p3", "six to thirty") + i * 0.05, at("p3", "six to thirty") + i * 0.05 + 0.3)
            x = 200 + i * 86; col = INK2
            d.rectangle([x, 470, x + 60, 530], fill=mix(BG, col, 0.25 * gi), outline=mix(BG, col, gi), width=2)
        d.text((200, 440), "one episode: 6, 12, 18 or 30 tool calls", font=f_note, fill=mix(BG, MUTED, g), anchor="lm")
    gq = seg(t, at("p3", "Some steps are"), at("p3", "Some steps are") + 0.8)
    if gq > 0:
        for i in (4, 9, 13, 17):
            x = 200 + i * 86
            d.rectangle([x, 470, x + 60, 530], fill=mix(BG, GOOD, 0.5 * gq), outline=mix(BG, GOOD, gq), width=3)
        d.text((200, 580), "question steps: answer from what you have seen, tools off", font=f_note, fill=mix(BG, GOOD, gq), anchor="lm")
    g1 = seg(t, at("p3", "In a trap"), at("p3", "In a trap") + 0.8)
    if g1 > 0:
        d.rounded_rectangle([200, 660, 900, 820], radius=16, outline=mix(BG, HOT, g1), width=4)
        d.text((230, 700), "TRAP STEP", font=f_num, fill=mix(BG, HOT, g1), anchor="lm")
        d.text((230, 760), "a superseded value sits in the context", font=f_note, fill=mix(BG, INK, g1), anchor="lm")
    g2 = seg(t, at("p3", "In a neutral"), at("p3", "In a neutral") + 0.8)
    if g2 > 0:
        d.rounded_rectangle([1000, 660, 1700, 820], radius=16, outline=mix(BG, SLATE, g2), width=4)
        d.text((1030, 700), "NEUTRAL STEP", font=f_num, fill=mix(BG, SLATE, g2), anchor="lm")
        d.text((1030, 760), "nothing in the context competes", font=f_note, fill=mix(BG, INK, g2), anchor="lm")

def s4(d, t):
    d.text((W // 2, 170), "Two kinds of trap", font=f_h2, fill=INK, anchor="mm")
    g1 = seg(t, at("p4", "In an own"), at("p4", "In an own") + 0.8)
    if g1 > 0:
        d.rounded_rectangle([140, 280, 920, 820], radius=18, outline=mix(BG, SLATE, g1), width=4)
        d.text((180, 330), "OWN UPDATE", font=f_num, fill=mix(BG, SLATE, g1), anchor="lm")
        block(d, 180, 400, 300, 70, "get_stock", INK2, g1, "qty = 55")
        block(d, 180, 500, 300, 70, "ship_order 10", SLATE, seg(t, at("p4", "the agent changed"), at("p4", "the agent changed") + 0.6), "reply: qty = 45")
        d.text((180, 660), "the tool reply states the new value", font=f_note, fill=mix(BG, INK, g1), anchor="lm")
        underline(d, 180, 700, 690, seg(t, at("p4", "stated the new"), at("p4", "stated the new") + 0.7), SLATE)
    g2 = seg(t, at("p4", "In an external"), at("p4", "In an external") + 0.8)
    if g2 > 0:
        d.rounded_rectangle([1000, 280, 1780, 820], radius=18, outline=mix(BG, HOT, g2), width=4)
        d.text((1040, 330), "EXTERNAL UPDATE", font=f_num, fill=mix(BG, HOT, g2), anchor="lm")
        block(d, 1040, 400, 300, 70, "get_stock", INK2, g2, "qty = 55")
        gl = seg(t, at("p4", "one row inside"), at("p4", "one row inside") + 0.8)
        if gl > 0:
            d.rounded_rectangle([1040, 500, 1700, 690], radius=10, outline=mix(BG, HOT, gl), width=3, fill=mix(BG, HOT, 0.06 * gl))
            d.text((1070, 530), "list_bin_contents", font=f_small, fill=mix(BG, INK, gl), anchor="lm")
            for i, row in enumerate(["SKU-2249   qty 12", "SKU-8148   qty 4    <- changed by someone else", "SKU-1884   qty 55"]):
                d.text((1070, 575 + i * 34), row, font=F(MENLO, 22), fill=mix(BG, HOT if i == 1 else MUTED, gl), anchor="lm")
        d.text((1040, 720), "the new value appears only as a listing row", font=f_note, fill=mix(BG, INK, g2), anchor="lm")

def s5(d, t):
    d.text((W // 2, 150), "Four layouts, the same information", font=f_h2, fill=INK, anchor="mm")
    ge = seg(t, cue_start("p5") + 0.2, cue_start("p5") + 0.8)
    if ge > 0: d.text((W // 2, 205), "one scripted episode, replayed four times; the agent's replies and tool results are never altered except as the rule says", font=f_note, fill=mix(BG, MUTED, ge), anchor="mm")
    cols = [("L1", "append-only (cache-optimal)", at("p5", "L1 is the"), ["sys", "tools", "o1", "o2", "o3", "o4", "q"], [SLATE, SLATE, INK2, INK2, INK2, INK2, GOOD], None),
            ("L2", "reordered by relevance", at("p5", "L2 reorders"), ["sys", "tools", "o3", "o1", "o4", "o2", "q"], [SLATE, SLATE, INK2, INK2, INK2, INK2, GOOD], None),
            ("L3", "superseded values redacted", at("p5", "L3 keeps"), ["sys", "tools", "o1", "o2", "o3", "o4", "q"], [SLATE, SLATE, HOT, INK2, HOT, INK2, GOOD], {2, 4}),
            ("L4", "L1 + pointer-only note", at("p5", "L4 is L1"), ["sys", "tools", "o1", "o2", "o3", "o4", "note+q"], [SLATE, SLATE, INK2, INK2, INK2, INK2, GOOD], None)]
    for i, (L, sub, ta, labs, cs, strike) in enumerate(cols):
        g = seg(t, ta, ta + 0.7)
        if g <= 0: continue
        y = 250 + i * 170
        d.text((140, y + 35), L, font=f_mid, fill=mix(BG, LCOL[L], g), anchor="lm")
        d.text((140, y + 95), sub, font=f_note, fill=mix(BG, MUTED, g), anchor="lm")
        for j, (lab, c) in enumerate(zip(labs, cs)):
            x = 700 + j * 150
            block(d, x, y + 10, 135, 70, lab, c, seg(t, ta + j * 0.08, ta + j * 0.08 + 0.4), strike=bool(strike and j in strike))
    g = seg(t, at("p5", "without stating"), at("p5", "without stating") + 0.8)
    if g > 0: d.text((700, 950), "the L4 note says which earlier steps are current; it never states a value", font=f_note, fill=mix(BG, GOOD, g), anchor="lm")

def acc_bars(d, t, rows, y0, ta_map, x0=160, bw=1050, bh=56, dy=130, fmt="{:.0f}%", scale=100.0):
    for i, (lab, val, col) in enumerate(rows):
        ta = ta_map[i]
        g = seg(t, ta, ta + 1.1)
        if g <= 0 or val is None: continue
        y = y0 + i * dy
        d.text((x0, y), lab, font=f_lab, fill=mix(BG, INK, min(1, g * 3)), anchor="lm")
        hbar(d, x0, y + 28, bw, bh, val * g, col)
        if g > 0.99: d.text((x0 + bw + 40, y + 56), fmt.format(val * scale), font=f_mid, fill=col, anchor="lm")

def s6(d, t):
    d.text((W // 2, 150), "Result 1: only external-update traps separate the layouts", font=f_h2, fill=INK, anchor="mm")
    ge = seg(t, cue_start("p6") + 0.2, cue_start("p6") + 0.8)
    if ge > 0: d.text((W // 2, 205), "Gemini 3.1 Flash-Lite, 144 episodes per layout, 360 trap and 360 neutral questions", font=f_note, fill=mix(BG, MUTED, ge), anchor="mm")
    g0 = seg(t, at("p6", "Own updates never"), at("p6", "Own updates never") + 0.8)
    if g0 > 0:
        d.text((160, 230), "own-update traps: 100% under every layout", font=f_note, fill=mix(BG, SLATE, g0), anchor="lm")
    g1 = seg(t, at("p6", "Neutral steps never"), at("p6", "Neutral steps never") + 0.8)
    if g1 > 0:
        d.text((1000, 230), "neutral steps: 100% under every layout", font=f_note, fill=mix(BG, SLATE, g1), anchor="lm")
    g2 = seg(t, at("p6", "The whole effect"), at("p6", "The whole effect") + 0.8)
    if g2 > 0: d.text((160, 300), "external-update traps, Gemini 3.1 Flash-Lite, 200 questions per layout", font=f_lab, fill=mix(BG, INK, g2), anchor="lm")
    rows = [(LNAME["L1"], ext(MAIN, "L1"), SLATE), (LNAME["L3"], ext(MAIN, "L3"), HOT), (LNAME["L2"], ext(MAIN, "L2"), SHELF), (LNAME["L4"], ext(MAIN, "L4"), GOOD)]
    tas = [at("p6", "the cache-optimal layout"), at("p6", "The pruned layout"), at("p6", "Reordering barely"), at("p6", "The note recovers")]
    acc_bars(d, t, rows, 360, tas)
    ring(d, 160 + 1050 + 120, 360 + 130 + 56, 150, seg(t, at("p6", "ninety-six percent"), at("p6", "ninety-six percent") + 0.8), HOT)

def s7(d, t):
    d.text((W // 2, 160), "Reading the wrong answers", font=f_h2, fill=INK, anchor="mm")
    n = AUD["n"]; stale = AUD["counts"].get("stale_value", 0)
    g = seg(t, at("p7", "We read forty"), at("p7", "We read forty") + 1.0)
    for i in range(n):
        gi = seg(t, at("p7", "We read forty") + i * 0.02, at("p7", "We read forty") + i * 0.02 + 0.3)
        gs = seg(t, at("p7", "Thirty-four are"), at("p7", "Thirty-four are") + 0.02 * i + 0.4)
        x = 160 + (i % 20) * 80; y = 280 + (i // 20) * 90
        col = HOT if i < stale and gs > 0 else RULE
        d.rectangle([x, y, x + 64, y + 64], fill=mix(BG, col, max(gi * 0.4, gs if i < stale else 0)), outline=mix(BG, FAINT, gi), width=2)
    if g > 0: d.text((160, 500), f"{n} wrong trap answers, hand-coded from their observation history", font=f_note, fill=mix(BG, MUTED, g), anchor="lm")
    g2 = seg(t, at("p7", "Thirty-four are"), at("p7", "Thirty-four are") + 0.8)
    if g2 > 0: d.text((160, 570), f"{stale} of {n}: the answer is a superseded value", font=f_mid, fill=mix(BG, HOT, g2), anchor="lm")
    g3 = seg(t, at("p7", "The agent answers"), at("p7", "The agent answers") + 0.8)
    if g3 > 0:
        block(d, 160, 680, 330, 70, "assign_ticket", SLATE, g3, "reply: assignee = Lena")
        block(d, 540, 680, 330, 70, "list_tickets", HOT, g3, "row: assignee = Priya")
        block(d, 920, 680, 420, 70, "Q: who is assigned?", GOOD, g3, "answer: Lena  (stale)")
        underline(d, 160, 490, 775, seg(t, at("p7", "own earlier write"), at("p7", "own earlier write") + 0.6), SLATE)
        underline(d, 540, 870, 775, seg(t, at("p7", "ignores the listing"), at("p7", "ignores the listing") + 0.6), HOT)

def s8(d, t):
    d.text((W // 2, 150), "Result 2: the bill", font=f_h2, fill=INK, anchor="mm")
    fr = M["frontier"]
    ce = {L: fr[L]["usd_per_episode"] * 100 for L in fr}; cc = {L: fr[L]["usd_per_correct_task"] * 100 for L in fr}
    mx = max(max(ce.values()), max(cc.values())) * 1.15
    g = seg(t, at("p8", "Per episode"), at("p8", "Per episode") + 0.8)
    if g > 0: d.text((160, 230), "cents per episode (billed)", font=f_lab, fill=mix(BG, INK, g), anchor="lm")
    for i, L in enumerate(("L1", "L3")):
        ta = at("p8", "Per episode") if L == "L1" else at("p8", "the pruned layout costs")
        gi = seg(t, ta, ta + 1.0)
        if gi > 0:
            y = 280 + i * 90
            d.text((160, y + 25), LNAME[L], font=f_note, fill=mix(BG, LCOL[L], gi), anchor="lm")
            hbar(d, 460, y, 700, 50, ce[L] / mx * gi, LCOL[L])
            if gi > 0.99: d.text((1190, y + 25), f"{ce[L]:.2f}c", font=f_num, fill=LCOL[L], anchor="lm")
    g2 = seg(t, at("p8", "per correct episode"), at("p8", "per correct episode") + 0.8)
    if g2 > 0: d.text((160, 500), "cents per correct episode", font=f_lab, fill=mix(BG, INK, g2), anchor="lm")
    for i, L in enumerate(("L1", "L3")):
        ta = at("p8", "per correct episode") + 0.3 * (1 - i)
        gi = seg(t, ta, ta + 1.0)
        if gi > 0:
            y = 550 + i * 90
            d.text((160, y + 25), LNAME[L], font=f_note, fill=mix(BG, LCOL[L], gi), anchor="lm")
            hbar(d, 460, y, 700, 50, cc[L] / mx * gi, LCOL[L])
            if gi > 0.99: d.text((1190, y + 25), f"{cc[L]:.2f}c", font=f_num, fill=LCOL[L], anchor="lm")
    ring(d, 1240, 665, 110, seg(t, at("p8", "one point two two"), at("p8", "one point two two") + 0.8), HOT)
    # threshold mini-chart on the right
    g3 = seg(t, at("p8", "repriced every cached"), at("p8", "repriced every cached") + 1.2)
    if g3 > 0:
        x0, y0, w, h = 1380, 300, 420, 400
        d.rectangle([x0, y0, x0 + w, y0 + h], outline=mix(BG, RULE, g3), width=2)
        d.text((x0 + w / 2, y0 - 30), "cents per correct vs cache-read price", font=F(HELV, 20), fill=mix(BG, MUTED, g3), anchor="mm")
        d5 = M["d5"]["cheapest_per_correct_by_read_multiplier"]; mults = list(d5.keys())
        ymax = max(d5[k]["usd_per_correct_task"][L] for k in mults for L in ("L1", "L3")) * 100 * 1.1
        for L in ("L1", "L3"):
            pts = [(x0 + i / (len(mults) - 1) * w, y0 + h - d5[k]["usd_per_correct_task"][L] * 100 / ymax * h) for i, k in enumerate(mults)]
            npts = max(2, int(len(pts) * g3))
            d.line(pts[:npts], fill=mix(BG, LCOL[L], g3), width=5)
            d.text((pts[npts - 1][0] + 8, pts[npts - 1][1]), L, font=f_small, fill=mix(BG, LCOL[L], g3), anchor="lm")
        d.text((x0, y0 + h + 24), "reads free", font=F(HELV, 18), fill=mix(BG, MUTED, g3), anchor="lm")
        d.text((x0 + w, y0 + h + 24), "reads at full price", font=F(HELV, 18), fill=mix(BG, MUTED, g3), anchor="rm")
    g4 = seg(t, at("p8", "At every price"), at("p8", "At every price") + 0.8)
    if g4 > 0:
        d.text((W // 2, 880), "at every cache-read price, pruning is the cheapest per correct answer", font=f_body, fill=mix(BG, HOT, g4), anchor="mm")

def s9(d, t):
    d.text((W // 2, 150), "Across three Gemini models", font=f_h2, fill=INK, anchor="mm")
    g = seg(t, cue_start("p9"), cue_start("p9") + 0.8)
    if g > 0: d.text((160, 230), "external-update trap accuracy, L1 append-only vs L3 pruned", font=f_lab, fill=mix(BG, INK, g), anchor="lm")
    reveal = {"google/gemini-2.5-flash": at("p9", "On Gemini 2.5"), "google/gemini-3.1-flash-lite": cue_start("p9") + 0.6, "google/gemini-3.6-flash": at("p9", "On Gemini 3.6")}
    for i, m in enumerate(LAD):
        gi = seg(t, reveal.get(m, cue_start("p9") + 0.6), reveal.get(m, cue_start("p9") + 0.6) + 1.0)
        if gi <= 0: continue
        y = 300 + i * 190
        d.text((160, y), LADLAB[m], font=f_num, fill=mix(BG, INK, gi), anchor="lm")
        for j, L in enumerate(("L1", "L3")):
            v = ext(m, L)
            if v is None: continue
            yy = y + 40 + j * 62
            d.text((160, yy + 22), L, font=f_note, fill=mix(BG, LCOL[L], gi), anchor="lm")
            hbar(d, 260, yy, 1100, 46, v * gi, LCOL[L])
            if gi > 0.99: d.text((1390, yy + 23), f"{v * 100:.0f}%", font=f_num, fill=LCOL[L], anchor="lm")
    # marker-pen annotations landing on the spoken numbers
    if LAD and LAD[0] == "google/gemini-2.5-flash":
        ring(d, 1440, 300 + 40 + 23, 90, seg(t, at("p9", "forty percent"), at("p9", "forty percent") + 0.7), SLATE)
        ring(d, 1440, 300 + 40 + 62 + 23, 90, seg(t, at("p9", "eighty-four"), at("p9", "eighty-four") + 0.7), HOT)
    if "google/gemini-3.6-flash" in LAD:
        i = LAD.index("google/gemini-3.6-flash"); y = 300 + i * 190
        ring(d, 1440, y + 40 + 23, 90, seg(t, at("p9", "eighty and"), at("p9", "eighty and") + 0.7), SLATE)
        ring(d, 1440, y + 40 + 62 + 23, 90, seg(t, at("p9", "one hundred"), at("p9", "one hundred") + 0.7), HOT)
    g2 = seg(t, at("p9", "Newer models"), at("p9", "Newer models") + 0.8)
    if g2 > 0: d.text((160, 900), "newer models are confused less often; none is cured", font=f_body, fill=mix(BG, INK, g2), anchor="lm")
    g3 = seg(t, at("p9", "pruning is the cheapest"), at("p9", "pruning is the cheapest") + 0.8)
    if g3 > 0:
        d.text((160, 960), "on every model, pruning is the cheapest per correct answer", font=f_body, fill=mix(BG, HOT, g3), anchor="lm")
        underline(d, 160, 1180, 992, seg(t, at("p9", "cheapest layout"), at("p9", "cheapest layout") + 0.7))


def s10(d, t):
    d.text((W // 2, 180), "What this means", font=f_h2, fill=INK, anchor="mm")
    ge = seg(t, cue_start("p10") + 0.2, cue_start("p10") + 0.8)
    if ge > 0: d.text((W // 2, 245), "for anyone who followed the 2025 context-engineering guidance", font=f_note, fill=mix(BG, MUTED, ge), anchor="mm")
    items = [("free when the world only changes through your own agent", at("p10", "the discipline is free"), SLATE),
             ("not free when the world changes behind it", at("p10", "It is not free"), HOT),
             ("a stale copy in the prompt costs a third of the answers", at("p10", "a stale copy"), HOT),
             ("the cheapest fix is to overwrite it, even if that breaks the cache", at("p10", "the cheapest fix"), GOOD)]
    for i, (txt, ta, col) in enumerate(items):
        g = seg(t, ta, ta + 0.7)
        if g > 0:
            y = 330 + i * 130
            d.ellipse([200, y - 12, 224, y + 12], fill=mix(BG, col, g))
            d.text((260, y), txt, font=f_body, fill=mix(BG, INK, g), anchor="lm")
    underline(d, 260, 1500, 330 + 2 * 130 + 32, seg(t, at("p10", "third of the answers"), at("p10", "third of the answers") + 0.7))

def s11(d, t):
    d.text((W // 2, 330), "Cheap but confused?", font=f_h1, fill=INK, anchor="mm")
    g = seg(t, at("p11", "Keep the cache"), at("p11", "Keep the cache") + 0.8)
    d.text((W // 2, 450), "Keep the cache.", font=f_mid, fill=mix(BG, SLATE, g), anchor="mm")
    g2 = seg(t, at("p11", "Do not keep"), at("p11", "Do not keep") + 0.8)
    d.text((W // 2, 540), "Do not keep the stale value.", font=f_mid, fill=mix(BG, HOT, g2), anchor="mm")
    d.text((W // 2, 760), "Mohammed Abraar  ·  Vizuara Research  ·  2026", font=f_lab, fill=MUTED, anchor="mm")
    d.text((W // 2, 820), URL, font=f_num, fill=SLATE, anchor="mm")

SCENES = [("p1", s1), ("p2", s2), ("p3", s3), ("p4", s4), ("p5", s5), ("p6", s6), ("p7", s7), ("p8", s8), ("p9", s9), ("p10", s10), ("p11", s11)]
XFADE = 0.3
def bounds():
    out = []
    for i, (cue, fn) in enumerate(SCENES):
        a = 0.0 if i == 0 else cue_start(cue) - 0.35
        b = cue_start(SCENES[i + 1][0]) - 0.35 if i + 1 < len(SCENES) else TOTAL + 1.5
        out.append((a, b, fn))
    return out
BOUNDS = None
def render_at(t):
    """Scenes never overlap: the outgoing scene fades out over XFADE before its boundary, the incoming scene
    fades in over XFADE after it, so two titles are never on screen together."""
    global BOUNDS
    if BOUNDS is None: BOUNDS = bounds()
    im = Image.new("RGB", (W, H)); d = ImageDraw.Draw(im); base(d, t)
    for a, b, fn in BOUNDS:
        if a <= t < b:
            alpha = min(seg(t, a, a + XFADE) if a > 0 else 1.0, 1 - seg(t, b - XFADE, b))
            if alpha >= 0.999: fn(d, t)
            elif alpha > 0:
                im2 = Image.new("RGB", (W, H)); d2 = ImageDraw.Draw(im2); base(d2, t); fn(d2, t)
                im = Image.blend(im, im2, alpha); d = ImageDraw.Draw(im)
    return im
def main():
    if len(sys.argv) > 1 and sys.argv[1] == "check":
        for a, b, fn in bounds(): print(f"{fn.__name__}: {a:.1f}-{b:.1f}")
        tiles = []
        for cue, fn in SCENES:
            c = CUE[cue]
            for k, tt in enumerate((c["start"] + 1.0, c["start"] + c["dur"] * 0.5, c["start"] + c["dur"] - 0.5)):
                tiles.append(render_at(tt).resize((640, 360)))
        sheet = Image.new("RGB", (640 * 3, 360 * len(SCENES)), (255, 255, 255))
        for i, im in enumerate(tiles): sheet.paste(im, ((i % 3) * 640, (i // 3) * 360))
        sheet.save(HERE / "_contact_check.png")
        print("anchors resolve; contact sheet written"); return
    if FRAMES.exists(): shutil.rmtree(FRAMES)
    FRAMES.mkdir(); total = int((TOTAL + 1.5) * FPS)
    for f in range(total):
        render_at(f / FPS).save(FRAMES / f"f{f:06d}.png", compress_level=1)
        if f % 600 == 0: print(f"{f}/{total}", flush=True)
    print("frames done:", total)
if __name__ == "__main__":
    main()
