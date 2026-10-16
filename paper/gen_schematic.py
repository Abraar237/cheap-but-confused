#!/usr/bin/env python3
"""Generate the Figure 1 pipeline schematic with a Gemini image model (Nano Banana) via OpenRouter.

The image is a schematic, not data. Every string is fixed in the prompt and must be checked by eye
after each generation, because image models can misspell.

    python3 paper/gen_schematic.py [out.png] [model]
"""
import base64, json, os, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "paper", "aaai", "assets", "fig1_schematic.png")
MODEL = sys.argv[2] if len(sys.argv) > 2 else "google/gemini-3-pro-image-preview"

PROMPT = """Create a clean scientific diagram for an academic research paper. Flat vector style, pure white background, thin dark-gray outlines, soft pastel fills, a clear sans-serif typeface, generous spacing. No shadows, no gradients, no 3D, no decoration, no title, no watermark. Portrait layout, four sections stacked top to bottom, joined by three short thick downward arrows.

SECTION 1. Small heading: "1. A scripted agent episode". Below it a horizontal row of five small rounded boxes joined by thin arrows, with these labels in order: "read: qty = 40", "write: qty = 62", "listing row: qty = 18", "other calls", "Q: current qty?". The third box has a light orange fill and a small label under it: "external update".

SECTION 2. Small heading: "2. Same information, four layouts". Below it four tall narrow cards side by side, each with a bold label on top and one line of small text under it:
card 1, light blue fill: "L1" and "append-only";
card 2, light purple fill: "L2" and "reordered";
card 3, light green fill: "L3" and "stale value redacted";
card 4, light yellow fill: "L4" and "append-only + note".

SECTION 3. Small heading: "3. Every call billed and cache-metered". Below it a small cloud icon labelled "Gemini via API" with a thin arrow to two small boxes side by side: "accuracy" and "cents + cached tokens".

SECTION 4. Small heading: "4. External-update traps, Gemini 3.1 Flash-Lite". Below it four short horizontal bars, left-aligned, each with a label on the left and a number on the right: "L1" with "65.5%" (bar about two thirds long, light blue), "L2" with "70.5%" (light purple), "L3" with "96.0%" (nearly full, light green), "L4" with "73.5%" (light yellow).

At the very bottom, one line of larger bold text: "Does the cache-friendly layout cost accuracy?"

Spell every quoted string exactly as written. All text must be large and easy to read when the image is printed 8 centimetres wide. Do not add any other words, numbers or labels."""


def main():
    key = None
    for line in open(os.environ.get("ENV_FILE", os.path.join(ROOT, ".env"))):
        if line.startswith("OPENROUTER_API_KEY="):
            key = line.split("=", 1)[1].strip()
    if not key:
        sys.exit("OPENROUTER_API_KEY missing from .env")
    body = {"model": MODEL, "modalities": ["image", "text"],
            "messages": [{"role": "user", "content": PROMPT}],
            "image_config": {"aspect_ratio": "3:4"}}
    req = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions",
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}"})
    try:
        r = json.load(urllib.request.urlopen(req, timeout=300))
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read()[:400].decode('utf-8', 'replace')}")
    for img in r["choices"][0]["message"].get("images", []):
        url = img["image_url"]["url"]
        open(OUT, "wb").write(base64.b64decode(url.split(",", 1)[1]))
        print("wrote", OUT)
        return
    sys.exit("no image in response: " + json.dumps(r)[:400])


if __name__ == "__main__":
    main()
