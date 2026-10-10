#!/usr/bin/env python3
"""Emit appendix_generated.tex from the frozen corpus and (when present) one logged episode per layout:
verbatim system prompt, phrasing templates, the L4 note template, and serialised contexts."""
import json, pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments"))
import layouts, prompts  # noqa

doc = json.load(open(ROOT / "corpus" / "tools.json"))
out = []
def verb(s, maxlen=None):
    s = s.replace("\\end{verbatim}", "\\end {verbatim}")
    return "\\begin{small}\\begin{verbatim}\n" + s + "\n\\end{verbatim}\\end{small}\n"
out.append("\\subsection{System prompt (verbatim, byte-identical across layouts)}\n\\label{app:system}\n" + verb(doc["system"]))
out.append("\\subsection{Tool catalogue}\nThe 39 tool declarations (names, descriptions and JSON schemas) ship in \\texttt{corpus/tools.json}; the names are: " +
           ", ".join("\\texttt{" + t["function"]["name"].replace("_", "\\_") + "}" for t in doc["tools"]) + ".\n")
ex = ["\\subsection{User-turn phrasings}\nEvery action instruction and every question has two phrasings; phrasing 1 is the main grid. Examples (phrasing 1 / phrasing 2):\n\\begin{small}\\begin{verbatim}"]
for tool in ("get_stock", "receive_shipment", "list_tickets", "reschedule_event"):
    ex.append(f"{tool}: {prompts.ACTION[tool][1]}  /  {prompts.ACTION[tool][2]}")
ex.append("")
ex.append("question wrapper 1: " + prompts.NOTOOL[1])
ex.append("question wrapper 2: " + prompts.NOTOOL[2])
ex.append("")
for q in ("qty", "start", "assignee", "below_threshold"):
    ex.append(f"{q}: {prompts.QUESTION[q][0]}  (format {prompts.QUESTION[q][1]})")
ex.append("\\end{verbatim}\\end{small}\n")
out.append("\n".join(ex))
out.append("\\subsection{L4 session note (template)}\n" + verb(layouts.recitation([], "<goal sentence>", 9, "")).replace("- none yet", "- <record>: current <field> at step <k>; superseded: steps <i>, <j>\n- <n> other records observed once; those observations are current."))
# serialised example contexts from a logged episode, if any
raw = sorted((ROOT / "results" / "raw").glob("google_*.jsonl"))
if raw:
    recs = [json.loads(l) for l in open(raw[0])]
    byk = {(r["task_id"], r["layout"]): r for r in recs}
    tasks = sorted({t for t, L in byk if all((t, x) in byk for x in ("L1", "L2", "L3", "L4"))})
    pick = [t for t in tasks if "L12" in t and "high" in t] or tasks
    if pick:
        t = pick[0]
        out.append(f"\\subsection{{One episode under each layout}}\n\\label{{app:layouts}}\nTask \\texttt{{{t}}}, context sent at its final question step (system prompt and tool catalogue omitted; they are identical). Model: {raw[0].stem.replace('_', '/', 1)}.\n")
        for L in ("L1", "L2", "L3", "L4"):
            r = byk[(t, L)]
            blocks = r["transcript"]
            qi = [i for i, b in enumerate(blocks) if b["kind"] == "question"][-1]
            msgs = layouts.build_messages(L, "SYSTEM", blocks[:qi], blocks[qi]["user"], json.load(open(ROOT / "corpus" / "tasks.json"))["tasks"][0]["goal"]["1"] if False else "GOAL", blocks[qi]["step"], "google")
            txt = layouts.serialise_for_log(msgs[1:])
            txt = "\n".join(line[:150] + (" ..." if len(line) > 150 else "") for line in txt.splitlines())
            out.append(f"\\paragraph{{{L}.}}\n" + verb(txt))
pathlib.Path(ROOT / "paper" / "iclr" / "appendix_generated.tex").write_text("\n".join(out))
print("appendix_generated.tex written", len("\n".join(out)))
