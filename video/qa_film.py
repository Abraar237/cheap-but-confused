"""Encode the film and run the QA protocol on the actual render: contact sheet every 4 s, sync audit at every
anchor phrase +0.5 s, transition audit at scene boundaries +/-0.3 s, motion/blank audit by frame difference."""
import json, subprocess, pathlib, re, numpy as np
from PIL import Image
HERE = pathlib.Path(__file__).resolve().parent; ROOT = HERE.parent
import build_film as b
FPS = 60
subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", "60", "-i", "frames/f%06d.png", "-i", "audio/narration.wav", "-c:v", "libx264", "-preset", "slow", "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", "-shortest", "film.mp4"], check=True, cwd=HERE)
probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=width,height,r_frame_rate", "-of", "default=nw=1", "film.mp4"], capture_output=True, text=True, cwd=HERE).stdout
loud = subprocess.run(["ffmpeg", "-i", "film.mp4", "-af", "loudnorm=print_format=summary", "-f", "null", "-"], capture_output=True, text=True, cwd=HERE).stderr
lufs = [l.strip() for l in loud.splitlines() if "Input Integrated" in l or "Input True Peak" in l]
print(probe.strip().replace("\n", " "), "|", " | ".join(lufs))
# 1. contact sheet every 4 s
def frame(t): return Image.open(HERE / "frames" / f"f{int(t * FPS):06d}.png")
times = np.arange(0, b.TOTAL, 4.0); tiles = [frame(t).resize((480, 270)) for t in times]
cols = 6; rows = (len(tiles) + cols - 1) // cols; sheet = Image.new("RGB", (480 * cols, 270 * rows), (255, 255, 255))
for i, im in enumerate(tiles): sheet.paste(im, ((i % cols) * 480, (i // cols) * 270))
sheet.save(HERE / "qa_contact_sheet.png"); print("contact sheet", len(tiles), "tiles")
# 2. sync audit: every at() anchor in build_film.py
src = open(HERE / "build_film.py").read(); anchors = sorted({(c, p) for c, p in re.findall(r'at\("(p\d+)", "([^"]+)"\)', src)})
sync = []
for c, p in anchors:
    t = b.at(c, p) + 0.5; sync.append((c, p, round(t, 2)))
tiles = [frame(t).resize((480, 270)) for _, _, t in sync]
rows = (len(tiles) + cols - 1) // cols; sheet = Image.new("RGB", (480 * cols, 270 * rows), (255, 255, 255))
for i, im in enumerate(tiles): sheet.paste(im, ((i % cols) * 480, (i // cols) * 270))
sheet.save(HERE / "qa_sync_sheet.png"); print("sync anchors", len(sync))
# 3. transition audit
bd = b.bounds(); tiles = []
for a, _, fn in bd[1:]:
    for dt in (-0.3, 0.0, 0.3): tiles.append(frame(max(0, a + dt)).resize((480, 270)))
rows = (len(tiles) + 2) // 3; sheet = Image.new("RGB", (480 * 3, 270 * rows), (255, 255, 255))
for i, im in enumerate(tiles): sheet.paste(im, ((i % 3) * 480, (i // 3) * 270))
sheet.save(HERE / "qa_transition_sheet.png")
# 4. motion / blank audit: frame diff every 0.5 s; flag static stretches > 8 s and near-blank > 4 s during narration
prev = None; diffs = []; blanks = []
for t in np.arange(0, b.TOTAL, 0.5):
    im = np.asarray(frame(t).resize((192, 108)).convert("L"), dtype=np.int16)
    ink = float((im < 200).mean())
    if prev is not None: diffs.append((t, float(np.abs(im - prev).mean())))
    blanks.append((t, ink)); prev = im
static = []; run_start = None
for t, d in diffs:
    if d < 0.15:
        run_start = t if run_start is None else run_start
    else:
        if run_start is not None and t - run_start > 8: static.append((run_start, t))
        run_start = None
blank_runs = []; rs = None
for t, ink in blanks:
    if ink < 0.01:
        rs = t if rs is None else rs
    else:
        if rs is not None and t - rs > 4: blank_runs.append((rs, t))
        rs = None
print("static stretches >8s:", [(round(a, 1), round(c, 1)) for a, c in static]); print("near-blank >4s:", blank_runs)
json.dump({"probe": probe, "loudness": lufs, "static": static, "blank": blank_runs, "n_anchors": len(sync)}, open(HERE / "qa_report.json", "w"), indent=1)
