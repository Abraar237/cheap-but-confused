"""The four context layouts. Input: the episode transcript so far as a list of BLOCKS (one per
completed step) plus the current user turn. Output: an OpenAI-format `messages` list.

Block format (produced by runner.py):
  {"step": int, "kind": "action"|"question", "user": str,
   "assistant": {"content": str|None, "tool_calls": [{"id","name","arguments"(json str)}]},
   "tool_results": [{"tool_call_id","name","content"(json str),"states": [[record, field], ...]}],
   "mentions": [record ids mentioned in this block]}

Layouts (information content identical across L1, L2, L4; L3 changes content):
  L1 cache-optimal   : system + tools first, blocks verbatim in arrival order, newest last.
  L2 relevance-sorted: same blocks, stable-sorted by relevance to the current turn (most relevant LAST);
                       ties keep arrival order. The prefix is rewritten every turn.
  L3 pruned          : arrival order, but every (record, field) value that a LATER result restates is
                       redacted in place to "<superseded at step K>"; a result whose stated fields are all
                       superseded becomes "[result superseded by step K]". Edits earlier bytes, so the
                       prefix breaks at the first edit.
  L4 hybrid          : L1 untouched + a short pointer-only "session note" prepended to the newest user turn
                       (goal, step number, and which earlier observations are current vs superseded per
                       record; NO values). Every turn keeps the note it was sent with, so the history is
                       append-only and the prefix is preserved (a note that is dropped from earlier turns
                       would rewrite the prefix every turn; that variant was run, found to break the cache,
                       and discarded).

Supersession is schema-level and transcript-derived: a result that states (record, field) is superseded
for that field by any later result that states the same (record, field). No hidden state is used."""

import json
import re

ID_RE = re.compile(r"\b(?:SKU|EVT|TCK)-\d{4}\b")


def mentions(text):
    return sorted(set(ID_RE.findall(text or "")))


def supersession(blocks):
    """-> dict[(block_index, result_index)] = {field: later_step, ...} and latest[(record, field)] = step."""
    latest = {}
    order = []
    for bi, b in enumerate(blocks):
        for ri, r in enumerate(b.get("tool_results") or []):
            for rec, f in r.get("states") or []:
                order.append((bi, ri, rec, f, b["step"]))
    sup = {}
    for bi, ri, rec, f, step in order:
        later = [s for (bj, rj, rec2, f2, s) in order if rec2 == rec and f2 == f and s > step]
        if later:
            sup.setdefault((bi, ri), {})[(rec, f)] = min(later)
    for bi, ri, rec, f, step in order:
        latest[(rec, f)] = max(latest.get((rec, f), 0), step)
    return sup, latest


def block_messages(b, redact=None):
    """One block -> list of OpenAI messages. redact: {result_index: {field: step}} for L3."""
    msgs = [{"role": "user", "content": b.get("user_sent") or b["user"]}]  # L4: the note sent with that turn stays in the history (append-only)
    a = b.get("assistant") or {}
    am = {"role": "assistant"}
    if a.get("content"):
        am["content"] = a["content"]
    else:
        am["content"] = None
    if a.get("tool_calls"):
        am["tool_calls"] = [{"id": tc["id"], "type": "function", "function": {"name": tc["name"], "arguments": tc["arguments"]}} for tc in a["tool_calls"]]
    if am.get("content") is None and not am.get("tool_calls"):
        am["content"] = ""
    msgs.append(am)
    for ri, r in enumerate(b.get("tool_results") or []):
        content = r["content"]
        if redact and ri in redact:
            fields = redact[ri]
            try:
                obj = json.loads(content)
            except json.JSONDecodeError:
                obj = None
            # fields: {(record, field): later_step}
            stated = [(rec, f) for rec, f in (r.get("states") or [])]
            if obj is not None and isinstance(obj, dict) and stated and all(k in fields for k in stated):
                content = f"[result superseded by step {min(fields.values())}]"
            elif obj is not None and isinstance(obj, dict):
                for (rec, f), step in fields.items():
                    key = RESULT_KEY.get(f, f)
                    if key in obj and any(isinstance(v, str) and v == rec for v in obj.values()):
                        obj[key] = f"<superseded at step {step}>"
                    for lv in obj.values():
                        if isinstance(lv, list):
                            for row in lv:
                                if isinstance(row, dict) and rec in row.values() and key in row:
                                    row[key] = f"<superseded at step {step}>"
                content = json.dumps(obj)
        msgs.append({"role": "tool", "tool_call_id": r["tool_call_id"], "name": r["name"], "content": content})
    return msgs


# field name in env state -> key in the tool result JSON
RESULT_KEY = {"threshold": "reorder_threshold", "load": "open_tickets"}


def relevance(block, current_text):
    cur = set(mentions(current_text))
    if not cur:
        return 0
    return len(cur & set(block.get("mentions") or []))


def recitation(blocks, goal, step_no, current_text):
    sup, latest = supersession(blocks)
    # per record: current fields -> step; superseded steps
    per = {}
    for bi, b in enumerate(blocks):
        for ri, r in enumerate(b.get("tool_results") or []):
            for rec, f in r.get("states") or []:
                d = per.setdefault(rec, {"current": {}, "stale": set()})
                if latest.get((rec, f)) == b["step"]:
                    d["current"][f] = b["step"]
                else:
                    d["stale"].add((b["step"], f))
    lines = []
    n_single = 0
    for rec in sorted(per):
        d = per[rec]
        stale_steps = sorted({s for s, _ in d["stale"]})
        if not stale_steps:
            n_single += 1
            continue
        cur = ", ".join(f"{f} at step {s}" for f, s in sorted(d["current"].items(), key=lambda kv: kv[1]))
        lines.append(f"- {rec}: current {cur}; superseded: step{'s' if len(stale_steps) > 1 else ''} {', '.join(map(str, stale_steps))}")
    if n_single:
        lines.append(f"- {n_single} other record{'s' if n_single != 1 else ''} observed once; those observations are current.")
    note = (f"[Session note before step {step_no}]\nGoal: {goal}\nRule: for every record use the latest observation listed as current; "
            f"observations listed as superseded are no longer valid.\nRecords with updated observations:\n" + ("\n".join(lines) if lines else "- none yet") + "\n[End of note]\n\n")
    return note


def build_messages(layout, system, blocks, current_text, goal, step_no, family, cache_control=True):
    """family: 'anthropic' | 'openai' | 'google'. cache_control applies to Anthropic only (explicit breakpoints)."""
    use_cc = family == "anthropic" and cache_control
    sys_msg = {"role": "system", "content": [{"type": "text", "text": system}]}
    if use_cc:
        sys_msg["content"][0]["cache_control"] = {"type": "ephemeral"}
    msgs = [sys_msg]
    if layout == "L1" or layout == "L4":
        for b in blocks:
            msgs += block_messages(b)
    elif layout == "L2":
        scored = sorted(enumerate(blocks), key=lambda ib: (relevance(ib[1], current_text), ib[0]))
        for _, b in scored:
            msgs += block_messages(b)
    elif layout == "L3":
        sup, _ = supersession(blocks)
        for bi, b in enumerate(blocks):
            red = {ri: f for (bj, ri), f in sup.items() if bj == bi}
            msgs += block_messages(b, redact=red or None)
    else:
        raise ValueError(layout)
    text = current_text
    if layout == "L4":
        text = recitation(blocks, goal, step_no, current_text) + current_text
    um = {"role": "user", "content": [{"type": "text", "text": text}]}
    if use_cc:
        um["content"][0]["cache_control"] = {"type": "ephemeral"}
    msgs.append(um)
    return msgs


def serialise_for_log(msgs):
    """Compact, deterministic text rendering of a messages list (for the appendix and for byte-stability checks)."""
    out = []
    for m in msgs:
        c = m.get("content")
        if isinstance(c, list):
            c = "".join(p.get("text", "") for p in c)
        if m.get("tool_calls"):
            c = (c or "") + " " + json.dumps([{"name": t["function"]["name"], "arguments": t["function"]["arguments"]} for t in m["tool_calls"]])
        out.append(f"{m['role'].upper()}: {c}")
    return "\n".join(out)
