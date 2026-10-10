#!/usr/bin/env python3
"""Print the observation history behind each wrong answer in results/audit_candidates.json so it can be hand-coded.
For every candidate it lists, in step order, every tool result that mentions the queried record, the value of the
queried field in that result (listing rows are unpacked), and whether the model's answer equals an earlier (superseded)
value, another record's value, or neither. Usage: python3 audit_view.py [start] [count]"""
import json, sys, pathlib, re
ROOT = pathlib.Path(__file__).resolve().parent.parent
cand = json.load(open(ROOT / "results" / "audit_candidates.json"))
recs = {}
for f in sorted((ROOT / "results" / "raw").glob("*.jsonl")):
    if f.name.startswith("_"): continue
    for line in open(f):
        r = json.loads(line); recs[(r["model"], r["task_id"], r["layout"], r.get("phrasing", 1), r.get("rep", 0), r.get("battery", "none"))] = r
FIELD_KEYS = {"start": ["start"], "end": ["end"], "room": ["room"], "status": ["status"], "priority": ["priority"], "assignee": ["assignee"],
              "qty": ["qty", "quantity"], "bin": ["bin"], "supplier": ["supplier"], "count": [], "attendees": ["attendees"],
              "below_threshold": ["qty", "threshold", "reorder_threshold", "reorder_point"]}

def find_objs(content, rec):
    """Return every JSON object (top-level or nested) whose values mention rec."""
    try:
        d = json.loads(content)
    except Exception:
        return []
    out = []
    def walk(o):
        if isinstance(o, dict):
            if any(v == rec for v in o.values()):
                out.append(o)
            for v in o.values(): walk(v)
        elif isinstance(o, list):
            for v in o: walk(v)
    walk(d)
    return out

start = int(sys.argv[1]) if len(sys.argv) > 1 else 0
count = int(sys.argv[2]) if len(sys.argv) > 2 else 10
for i, c in enumerate(cand["items"][start:start + count], start):
    r = recs.get((c["model"], c["task_id"], c["layout"], c.get("phrasing", 1), c.get("rep", 0), c.get("battery", "none")))
    print(f"\n#{i} {c['model']} {c['task_id']} {c['layout']} step {c['step']} q={c['qkind']} rec={c['record']} trap={c['trap']} chain={c['chain']} stale_present={c['stale_present']}")
    print(f"   answered {c['answer']!r}  actual {c['actual']!r}  raw: {c['answer_raw'][:100]!r}")
    if not r: print("   (episode not found)"); continue
    keys = FIELD_KEYS.get(c["qkind"], [c["qkind"]])
    hist, other_vals = [], {}
    for b in r["transcript"]:
        if b["step"] >= c["step"]: break
        for tr in b["tool_results"]:
            objs = find_objs(tr["content"], c["record"])
            for o in objs:
                for k in keys:
                    if k in o:
                        hist.append((b["step"], tr["name"], k, o[k]))
            # other records' values for the same field (distractor check)
            try:
                d = json.loads(tr["content"])
            except Exception:
                d = None
            def walk(o):
                if isinstance(o, dict):
                    rid = next((v for v in o.values() if isinstance(v, str) and re.match(r"^(EVT|TCK|SKU|ITM)-", v)), None)
                    if rid and rid != c["record"]:
                        for k in keys:
                            if k in o: other_vals.setdefault(str(o[k]), set()).add(rid)
                    for v in o.values(): walk(v)
                elif isinstance(o, list):
                    for v in o: walk(v)
            walk(d)
    for st, nm, k, v in hist:
        print(f"   step {st:2d} {nm:22s} {k}={v!r}")
    ans = str(c["answer"]); vals = [str(v) for _, _, k, v in hist if k == keys[0]]
    tags = []
    if vals and ans in vals[:-1]: tags.append("STALE(earlier value)")
    if vals and ans == vals[-1]: tags.append("LATEST-OBSERVED(scoring mismatch?)")
    if ans in other_vals: tags.append(f"DISTRACTOR({sorted(other_vals[ans])[:3]})")
    if not vals: tags.append("NO-OBSERVATION")
    print("   -> " + (", ".join(tags) if tags else "OTHER"))
