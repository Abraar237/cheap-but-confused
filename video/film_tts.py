#!/usr/bin/env python3
"""Narration cues -> ElevenLabs (Matilda, with-timestamps) -> per-word timing database words.json on the film clock.
Fallback (used only if the ElevenLabs key is rejected): macOS `say` with word times estimated from character
counts inside the measured cue duration; words.json then records voice="fallback-say" so nobody mistakes it for
the Matilda track. Re-running with a valid key regenerates everything."""
import base64, json, os, re, subprocess, sys, urllib.request
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.dirname(HERE)
AUDIO = os.path.join(HERE, "audio"); os.makedirs(AUDIO, exist_ok=True)
KEY = None
with open(os.path.join(ROOT, ".env")) as f:
    for line in f:
        line = line.strip()
        if line.startswith("ELEVENLABS_API_KEY="):
            KEY = line.split("=", 1)[1].strip().strip('"').strip("'")
VOICE = "XrExE9yKIg1WjnnlVkGX"  # Matilda
FORCE_FALLBACK = os.environ.get("FILM_TTS_FALLBACK") == "1"

def load_cues():
    cues = []
    for line in open(os.path.join(HERE, "script.md")):
        m = re.match(r"^(p\d+)\.\s+(.*)$", line.strip())
        if m:
            cues.append((m.group(1), m.group(2)))
    return cues

CUES = load_cues()
GAPS = {c: 0.7 for c, _ in CUES}; GAPS.update({"p2": 0.9, "p5": 0.9, "p8": 0.9, "p9": 0.9, "p11": 4.0}); LEAD_IN = 0.6
VOICE_USED = {"name": "ElevenLabs Matilda", "fallback": False}

def tts_eleven(cue_id, text):
    mp3 = os.path.join(AUDIO, f"{cue_id}.mp3"); aln = os.path.join(AUDIO, f"{cue_id}.align.json")
    if os.path.exists(mp3) and os.path.exists(aln):
        return json.load(open(aln))
    req = urllib.request.Request(f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE}/with-timestamps",
        data=json.dumps({"text": text, "model_id": "eleven_multilingual_v2",
                         "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "style": 0.25, "speed": 1.0}}).encode(),
        headers={"xi-api-key": KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=180) as r:
        out = json.load(r)
    open(mp3, "wb").write(base64.b64decode(out["audio_base64"]))
    json.dump(out["alignment"], open(aln, "w"))
    return out["alignment"]

def words_from_alignment(align):
    words, cur, start, end = [], "", None, None
    for i, ch in enumerate(align["characters"]):
        if ch.isspace():
            if cur:
                words.append({"w": cur, "s": start, "e": end}); cur, start = "", None
        else:
            if start is None:
                start = align["character_start_times_seconds"][i]
            cur += ch; end = align["character_end_times_seconds"][i]
    if cur:
        words.append({"w": cur, "s": start, "e": end})
    return words

def dur_of(path):
    return float(subprocess.run(["ffprobe", "-v", "quiet", "-show_entries", "format=duration", "-of", "csv=p=0", path], capture_output=True, text=True).stdout.strip())

def tts_fallback(cue_id, text):
    aiff = os.path.join(AUDIO, f"{cue_id}.aiff"); aln = os.path.join(AUDIO, f"{cue_id}.align.json")
    if not os.path.exists(aiff):
        subprocess.run(["say", "-v", "Samantha", "-r", "165", "-o", aiff, text], check=True)
    d = dur_of(aiff)
    toks = text.split(); total_chars = sum(len(t) + 1 for t in toks); t = 0.15; words = []
    for w in toks:
        share = (len(w) + 1) / total_chars * (d - 0.3)
        words.append({"w": w, "s": round(t, 3), "e": round(t + share * 0.9, 3)}); t += share
    json.dump({"fallback": True, "words": words}, open(aln, "w"))
    return words, aiff

def main():
    global VOICE_USED
    db = {"cues": []}; clock = LEAD_IN; parts = [("silence", LEAD_IN)]
    use_fallback = FORCE_FALLBACK or not KEY
    for cue_id, text in CUES:
        if "PLACEHOLDER" in text:
            sys.exit(f"{cue_id} still has a placeholder; fill script.md first")
        src = None
        if not use_fallback:
            try:
                words = words_from_alignment(tts_eleven(cue_id, text)); src = os.path.join(AUDIO, f"{cue_id}.mp3")
            except urllib.error.HTTPError as e:
                print(f"ElevenLabs HTTP {e.code} on {cue_id}; falling back to macOS say for the whole film", file=sys.stderr)
                use_fallback = True
        if use_fallback:
            words, src = tts_fallback(cue_id, text); VOICE_USED = {"name": "macOS say (Samantha), placeholder", "fallback": True}
        wav = os.path.join(AUDIO, f"{cue_id}.wav")
        subprocess.run(["ffmpeg", "-y", "-v", "quiet", "-i", src, "-ar", "48000", "-ac", "2", wav], check=True)
        d = dur_of(wav)
        db["cues"].append({"id": cue_id, "text": text, "start": clock, "dur": d, "words": words})
        parts.append(("file", wav)); parts.append(("silence", GAPS[cue_id])); clock += d + GAPS[cue_id]
        print(f"{cue_id}: start={clock - d - GAPS[cue_id]:.2f} dur={d:.2f}")
    db["total"] = clock; db["voice"] = VOICE_USED
    print(f"total narration track: {clock:.2f}s  voice={VOICE_USED['name']}")
    inputs, filters, segs = [], [], []
    for idx, (kind, val) in enumerate(parts):
        if kind == "silence":
            filters.append(f"aevalsrc=0:d={val}:s=48000,aformat=channel_layouts=stereo[s{idx}]"); segs.append(f"[s{idx}]")
        else:
            inputs += ["-i", val]; segs.append(f"[{len(inputs) // 2 - 1}:a]")
    fc = ";".join(filters) + ";" + "".join(segs) + f"concat=n={len(segs)}:v=0:a=1[out]"
    raw = os.path.join(AUDIO, "narration_raw.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "quiet"] + inputs + ["-filter_complex", fc, "-map", "[out]", raw], check=True)
    # two-pass loudness normalisation to -14 LUFS integrated, -1.5 dBTP
    norm = os.path.join(AUDIO, "narration.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "quiet", "-i", raw, "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", norm], check=True)
    json.dump(db, open(os.path.join(HERE, "words.json"), "w"), indent=1)
    print("narration.wav", dur_of(norm))

if __name__ == "__main__":
    main()
