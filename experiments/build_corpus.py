#!/usr/bin/env python3
"""Build and freeze the StaleTrap testbed -> corpus/tasks.json, corpus/tools.json, corpus/FROZEN.json.

Design (frozen at CP2):
  3 domains x 3 templates x 4 lengths (6/12/18/30 tool calls) x 2 distractor levels x 2 seeds = 144 tasks,
  each with two phrasings. Length fixes the composition:
    L=6  : 1 trap thread (chain 1) + 1 neutral thread            -> 2 questions, 3 distractor calls
    L=12 : 2 trap threads (chains 1,2) + 2 neutral threads       -> 4 questions, 5 distractor calls
    L=18 : 3 trap threads (chains 1,2,1) + 3 neutral threads     -> 6 questions, 8 distractor calls
    L=30 : 4 trap threads (chains 1,2,3,2) + 4 neutral threads   -> 8 questions, 14 distractor calls
  A trap thread = read(record.field) ... write(s) that state the new value ... question on the field.
  A neutral thread = read(record.field) ... question on the field (never written).
  Distractor level changes the distractor calls' volume and pressure, not their count:
    low  : compact single-record reads/writes on unrelated records
    high : verbose listing calls, near-miss identifiers (one digit transposed), and writes to OTHER
           fields of thread records.
Deterministic given the seed. Usage: python3 build_corpus.py [--freeze]"""

import argparse
import hashlib
import json
import pathlib
import random

import env
import prompts

ROOT = pathlib.Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"
CORPUS.mkdir(exist_ok=True)

DOMAINS = ["inventory", "calendar", "ticketing"]
LENGTHS = [6, 12, 18, 30]
DISTRACTORS = ["low", "high"]
SEEDS = [0, 1]
COMPOSITION = {6: {"traps": [1], "neutral": 1, "distractors": 3},
               12: {"traps": [1, 2], "neutral": 2, "distractors": 5},
               18: {"traps": [1, 2, 1], "neutral": 3, "distractors": 8},
               30: {"traps": [1, 2, 3, 2], "neutral": 4, "distractors": 14}}
# distance (in tool calls) from the last write of a trap thread, or the read of a neutral thread, to its question
QGAP = {6: (2, 3), 12: (3, 6), 18: (3, 7), 30: (4, 9)}

# template -> (trap field, neutral field). Field names map to read tool, write tools, question kind.
TEMPLATES = {
    "inventory": {"T1": ("qty", "bin"), "T2": ("price", "supplier"), "T3": ("qty+threshold", "price")},
    "calendar": {"T1": ("start", "room"), "T2": ("room", "start"), "T3": ("attendees", "status")},
    "ticketing": {"T1": ("assignee", "priority"), "T2": ("priority", "status"), "T3": ("status", "assignee")},
}
READ_TOOL = {"qty": "get_stock", "bin": "get_stock", "price": "get_price", "threshold": "get_reorder_threshold", "supplier": "get_supplier",
             "start": "get_event", "room": "get_event", "attendees": "get_event", "status": None,
             "assignee": "get_ticket", "priority": "get_ticket"}
QKIND = {"qty": "qty", "bin": "bin", "price": "price", "threshold": "threshold", "supplier": None, "qty+threshold": "below_threshold",
         "start": "start", "room": "room", "attendees": "n_attendees",
         "assignee": "assignee", "priority": "priority"}


# templates whose trap field can be revealed by a listing after an EXTERNAL change (someone else changed the world):
# (domain, template) -> (field, listing tool). Other templates keep own-update traps (the agent's own write reports the value).
EXTERNAL = {("inventory", "T1"): ("qty", "list_bin_contents"), ("inventory", "T3"): ("qty", "list_bin_contents"),
            ("calendar", "T1"): ("start", "get_room_schedule"), ("ticketing", "T1"): ("assignee", "list_tickets"),
            ("ticketing", "T2"): ("priority", "list_tickets")}


def qkind_for(field, domain):
    if field == "status":
        return {"calendar": "status_event", "ticketing": "status_ticket"}[domain]
    if field == "supplier":
        return "supplier"
    return QKIND[field]


def near_miss(rid, rng):
    pre, num = rid.split("-")
    d = list(num)
    i = rng.randrange(len(d) - 1)
    d[i], d[i + 1] = d[i + 1], d[i]
    if "".join(d) == num:
        d[-1] = str((int(d[-1]) + 1) % 10)
    return f"{pre}-{''.join(d)}"


def fresh_id(prefix, used, rng):
    while True:
        rid = f"{prefix}-{rng.randint(1000, 9899)}"
        if rid not in used and len(set(rid[-4:])) >= 3:
            used.add(rid)
            return rid


def hhmm(m):
    return f"{m // 60:02d}:{m % 60:02d}"


class Gen:
    def __init__(self, domain, template, length, distractor, seed):
        self.domain, self.template, self.length, self.distractor, self.seed = domain, template, length, distractor, seed
        self.rng = random.Random(f"{domain}|{template}|{length}|{distractor}|{seed}")
        self.used = set()
        self.state = {"skus": {}, "events": {}, "tickets": {}, "availability": {}, "base_load": {}}
        self.live = {"skus": {}, "events": {}, "tickets": {}, "availability": {}, "base_load": {}}
        self.date = f"2026-10-{14 + self.rng.randrange(4)}"

    def _add(self, coll, rid, rec):
        import copy
        self.state[coll][rid] = copy.deepcopy(rec)
        self.live[coll][rid] = copy.deepcopy(rec)

    def _tweak(self, coll, rid, field, value):
        import copy
        self.state[coll][rid][field] = copy.deepcopy(value)
        self.live[coll][rid][field] = copy.deepcopy(value)

    # ---------- record factories ----------
    def new_sku(self):
        r = self.rng
        rid = fresh_id("SKU", self.used, r)
        self._add("skus", rid, {"qty": r.randint(8, 60), "bin": r.choice(env.BINS), "price": round(r.uniform(3, 80), 2),
                                "threshold": r.randint(5, 25), "supplier": r.choice(env.SUPPLIERS), "lead": r.randint(3, 21)})
        return rid

    def new_event(self):
        r = self.rng
        rid = fresh_id("EVT", self.used, r)
        start = r.choice(range(9 * 60, 16 * 60 + 1, 30))
        dur = r.choice([30, 60, 90])
        self._add("events", rid, {"title": r.choice(["Q4 planning", "Vendor review", "Sprint demo", "Budget sync", "Hiring panel", "Ops standup", "Client call", "Design review"]),
                                  "date": self.date, "start": hhmm(start), "end": hhmm(start + dur), "room": r.choice(env.ROOMS),
                                  "attendees": r.sample(env.PEOPLE, r.randint(2, 4)), "status": "confirmed" if r.random() < 0.65 else "cancelled"})
        return rid

    def new_ticket(self):
        r = self.rng
        rid = fresh_id("TCK", self.used, r)
        self._add("tickets", rid, {"subject": r.choice(["Login loop on mobile", "Invoice total wrong", "Export times out", "SSO redirect fails", "Dashboard latency", "API 502s", "Password reset email", "Report duplicates rows"]),
                                   "priority": r.choice(["P2", "P3", "P4"]), "assignee": r.choice(env.PEOPLE), "status": r.choice(["open", "pending", "in_progress"]),
                                   "tags": r.sample(env.TAGS, r.randint(1, 3)), "comments": r.randint(0, 6)})
        return rid

    def new_record(self):
        return {"inventory": self.new_sku, "calendar": self.new_event, "ticketing": self.new_ticket}[self.domain]()

    # ---------- thread step builders ----------
    def read_step(self, field, rec):
        tool = READ_TOOL[field]
        if tool is None:  # status: read via the domain's record getter
            tool = {"calendar": "get_event", "ticketing": "get_ticket"}[self.domain]
        arg = {"inventory": "sku", "calendar": "event_id", "ticketing": "ticket_id"}[self.domain]
        return {"tool": tool, "args": {arg: rec}}

    def write_step(self, field, rec, k):
        """k-th write (0 or 1) to field of rec: returns (tool, args). Values chosen fresh so each write changes the value."""
        r = self.rng
        if self.domain == "inventory":
            s = self.live["skus"][rec]
            if field == "qty":
                if self.template == "T3":  # compound template: the first write crosses the reorder threshold (yes/no flips);
                    thr = s["threshold"]      # a second write changes the quantity but stays on the same side, so the first value stays stale
                    if k == 0:
                        if s["qty"] > thr:
                            return {"tool": "ship_order", "args": {"sku": rec, "units": s["qty"] - thr + r.randint(0, min(3, thr))}}
                        return {"tool": "receive_shipment", "args": {"sku": rec, "units": thr - s["qty"] + r.randint(1, 15)}}
                    if s["qty"] > thr + 1:
                        return {"tool": "ship_order", "args": {"sku": rec, "units": r.randint(1, s["qty"] - thr - 1)}}
                    if s["qty"] > thr:
                        return {"tool": "receive_shipment", "args": {"sku": rec, "units": r.randint(5, 20)}}
                    if s["qty"] >= 2:
                        return {"tool": "ship_order", "args": {"sku": rec, "units": r.randint(1, s["qty"] - 1)}}
                    return {"tool": "receive_shipment", "args": {"sku": rec, "units": max(1, thr - s["qty"])}}
                return {"tool": "receive_shipment", "args": {"sku": rec, "units": r.randint(10, 40)}} if (k == 0) == (r.random() < 0.5) \
                    else {"tool": "ship_order", "args": {"sku": rec, "units": r.randint(2, max(2, min(7, s["qty"] - 1)))}}
            if field == "price":
                return {"tool": "set_price", "args": {"sku": rec, "price": round(r.uniform(3, 80), 2)}}
            if field == "threshold":
                return {"tool": "set_reorder_threshold", "args": {"sku": rec, "threshold": r.choice([v for v in range(5, 60, 5) if v != s["threshold"]])}}
            if field == "bin":
                return {"tool": "move_stock", "args": {"sku": rec, "to_bin": r.choice([b for b in env.BINS if b != s["bin"]])}}
        if self.domain == "calendar":
            e = self.live["events"][rec]
            e0 = self.state["events"][rec]  # initial values: a second write must not restore them, or the first value stops being stale
            if field == "start":
                cur = int(e["start"][:2]) * 60 + int(e["start"][3:])
                orig = int(e0["start"][:2]) * 60 + int(e0["start"][3:])
                dur = (int(e["end"][:2]) * 60 + int(e["end"][3:])) - cur
                ns = r.choice([m for m in range(9 * 60, 16 * 60 + 1, 30) if m not in (cur, orig)])
                return {"tool": "reschedule_event", "args": {"event_id": rec, "new_start": hhmm(ns), "new_end": hhmm(ns + dur)}}
            if field == "room":
                return {"tool": "move_event_room", "args": {"event_id": rec, "room": r.choice([x for x in env.ROOMS if x not in (e["room"], e0["room"])])}}
            if field == "attendees":
                cand = [p for p in env.PEOPLE if p not in e["attendees"]]
                if k == 0 and len(e["attendees"]) >= 3 and r.random() < 0.4:
                    return {"tool": "remove_attendee", "args": {"event_id": rec, "person": r.choice(e["attendees"])}}
                if k == 1 and len(e["attendees"]) < len(e0["attendees"]) and len(e["attendees"]) >= 2:
                    return {"tool": "remove_attendee", "args": {"event_id": rec, "person": r.choice(e["attendees"])}}
                return {"tool": "add_attendee", "args": {"event_id": rec, "person": r.choice(cand)}}
            if field == "status":
                return {"tool": "cancel_event", "args": {"event_id": rec}}
        if self.domain == "ticketing":
            t = self.live["tickets"][rec]
            t0 = self.state["tickets"][rec]  # initial values: never restore them on a second write
            if field == "assignee":
                return {"tool": "assign_ticket", "args": {"ticket_id": rec, "agent": r.choice([p for p in env.PEOPLE if p not in (t["assignee"], t0["assignee"])])}}
            if field == "priority":
                i = env.PRIORITIES.index(t["priority"])
                if k == 1 and i > 0 and env.PRIORITIES[i - 1] != t0["priority"]:
                    return {"tool": "escalate_ticket", "args": {"ticket_id": rec}}
                return {"tool": "set_priority", "args": {"ticket_id": rec, "priority": r.choice([p for p in env.PRIORITIES if p not in (t["priority"], t0["priority"])])}}
            if field == "status":
                return {"tool": "set_status", "args": {"ticket_id": rec, "status": r.choice([s for s in env.STATUSES if s not in (t["status"], t0["status"])])}}
        raise ValueError((self.domain, field))

    def external_value(self, field, rec, k):
        """Value chosen for an external change to (rec, field); k = index of this update within the thread (0 = first).
        Applied to the live state. Never equals the current or the original value. Returns list of (field, value)."""
        r = self.rng
        if self.domain == "inventory":
            s0, sl = self.state["skus"][rec], self.live["skus"][rec]
            thr = sl["threshold"]
            if self.template == "T3":
                if k == 0:
                    new = thr - r.randint(0, min(3, thr)) if sl["qty"] > thr else thr + r.randint(1, 15)
                else:
                    new = r.randint(thr + 1, thr + 20) if sl["qty"] > thr else r.randint(0, thr)
                    if new == sl["qty"]:
                        new = new + 1 if sl["qty"] > thr else max(0, new - 1)
            else:
                cands = [v for v in range(max(0, sl["qty"] - 9), sl["qty"] + 30) if v not in (sl["qty"], s0["qty"]) and abs(v - sl["qty"]) >= 2]
                new = r.choice(cands)
            sl["qty"] = new
            return [("qty", new)]
        if self.domain == "calendar":
            e0, el = self.state["events"][rec], self.live["events"][rec]
            cur = int(el["start"][:2]) * 60 + int(el["start"][3:]); orig = int(e0["start"][:2]) * 60 + int(e0["start"][3:])
            dur = (int(el["end"][:2]) * 60 + int(el["end"][3:])) - cur
            ns = r.choice([m for m in range(9 * 60, 16 * 60 + 1, 30) if m not in (cur, orig)])
            el["start"], el["end"] = hhmm(ns), hhmm(ns + dur)
            return [("start", el["start"]), ("end", el["end"])]
        t0, tl = self.state["tickets"][rec], self.live["tickets"][rec]
        if field == "assignee":
            new = r.choice([p for p in env.PEOPLE if p not in (tl["assignee"], t0["assignee"])])
            tl["assignee"] = new
            return [("assignee", new)]
        new = r.choice([p for p in env.PRIORITIES if p not in (tl["priority"], t0["priority"])])
        tl["priority"] = new
        return [("priority", new)]

    def reveal_step(self, rec):
        """The listing call whose result contains the trapped record's row (among at least three others)."""
        r = self.rng
        if self.domain == "inventory":
            b = self.live["skus"][rec]["bin"]
            others = [k for k, v in self.state["skus"].items() if v["bin"] == b and k != rec]
            while len(others) < 3:
                k = self.new_sku(); self._tweak("skus", k, "bin", b); others.append(k)
            return {"tool": "list_bin_contents", "args": {"bin": b}}
        if self.domain == "calendar":
            room = self.live["events"][rec]["room"]
            others = [k for k, v in self.state["events"].items() if v["room"] == room and v["status"] == "confirmed" and k != rec]
            while len(others) < 2:
                k = self.new_event(); self._tweak("events", k, "room", room); self._tweak("events", k, "status", "confirmed"); others.append(k)
            return {"tool": "get_room_schedule", "args": {"room": room, "date": self.date}}
        st = self.live["tickets"][rec]["status"]
        others = [k for k, v in self.state["tickets"].items() if v["status"] == st and k != rec]
        while len(others) < 3:
            k = self.new_ticket(); self._tweak("tickets", k, "status", st); others.append(k)
        return {"tool": "list_tickets", "args": {"status": st}}

    def distractor_step(self, thread_records, thread_fields):
        """One distractor tool call. low: compact unrelated read/write. high: verbose listing, near-miss id, or other-field write on a thread record."""
        r = self.rng
        if self.distractor == "low":
            rec = self.new_record()
            if self.domain == "inventory":
                return r.choice([{"tool": "get_price", "args": {"sku": rec}}, {"tool": "get_supplier", "args": {"sku": rec}},
                                 {"tool": "get_reorder_threshold", "args": {"sku": rec}}, {"tool": "set_price", "args": {"sku": rec, "price": round(r.uniform(3, 80), 2)}}])
            if self.domain == "calendar":
                return r.choice([{"tool": "get_event", "args": {"event_id": rec}}, {"tool": "set_event_title", "args": {"event_id": rec, "title": r.choice(["Weekly sync", "Roadmap", "1:1", "Retro"])}},
                                 {"tool": "get_availability", "args": {"person": r.choice(env.PEOPLE), "date": self.date}}])
            return r.choice([{"tool": "get_ticket", "args": {"ticket_id": rec}}, {"tool": "add_comment", "args": {"ticket_id": rec, "text": r.choice(["Customer called back.", "Waiting on logs.", "Repro confirmed."])}},
                             {"tool": "get_sla_policy", "args": {"priority": r.choice(env.PRIORITIES)}}])
        # high pressure
        kind = r.choice(["listing", "nearmiss", "otherfield", "listing"])
        if kind == "listing":
            for _ in range(3):
                self.new_record()
            if self.domain == "inventory":
                b = r.choice(env.BINS)
                for k in list(self.state["skus"])[-3:]:
                    self._tweak("skus", k, "bin", b)
                return {"tool": "list_bin_contents", "args": {"bin": b}}
            if self.domain == "calendar":
                room = r.choice(env.ROOMS)
                for k in list(self.state["events"])[-3:]:
                    self._tweak("events", k, "room", room)
                return {"tool": "get_room_schedule", "args": {"room": room, "date": self.date}}
            st = r.choice(["open", "pending", "in_progress"])
            for k in list(self.state["tickets"])[-3:]:
                self._tweak("tickets", k, "status", st)
            return {"tool": "list_tickets", "args": {"status": st}}
        if kind == "nearmiss":
            base = r.choice(thread_records)
            nm = near_miss(base, r)
            if nm not in self.used:
                self.used.add(nm)
                prefix = base.split("-")[0]
                if prefix == "SKU":
                    rec = dict(self.state["skus"][base]); rec["qty"] = r.randint(8, 60); rec["price"] = round(r.uniform(3, 80), 2); self._add("skus", nm, rec)
                elif prefix == "EVT":
                    rec = json.loads(json.dumps(self.state["events"][base])); rec["room"] = r.choice(env.ROOMS); rec["start"] = hhmm(r.choice(range(9 * 60, 16 * 60 + 1, 30))); self._add("events", nm, rec)
                else:
                    rec = json.loads(json.dumps(self.state["tickets"][base])); rec["assignee"] = r.choice(env.PEOPLE); rec["priority"] = r.choice(env.PRIORITIES); self._add("tickets", nm, rec)
            return self.read_step({"SKU": "qty", "EVT": "start", "TCK": "assignee"}[nm.split("-")[0]], nm)
        # other-field write on a thread record (never a thread field)
        rec = r.choice(thread_records)
        fields = thread_fields[rec]
        if self.domain == "inventory":
            opts = [f for f in ["price", "threshold"] if f not in fields]
        elif self.domain == "calendar":
            opts = [f for f in ["attendees"] if f not in fields] + ["title"]
        else:
            opts = [f for f in ["assignee", "priority"] if f not in fields] + ["tags", "comments"]
        f = r.choice(opts)
        if f == "title":
            return {"tool": "set_event_title", "args": {"event_id": rec, "title": r.choice(["Weekly sync", "Roadmap", "Planning", "Retro"])}}
        if f == "tags":
            return {"tool": "add_tag", "args": {"ticket_id": rec, "tag": r.choice(env.TAGS)}}
        if f == "comments":
            return {"tool": "add_comment", "args": {"ticket_id": rec, "text": r.choice(["Customer called back.", "Waiting on logs.", "Repro confirmed."])}}
        return self.write_step(f, rec, 0)

    # ---------- plan ----------
    def build(self):
        r = self.rng
        comp = COMPOSITION[self.length]
        trap_field, neutral_field = TEMPLATES[self.domain][self.template]
        L = self.length
        threads = []  # each: dict(kind, record, fields, calls=[(pos, step)], qpos)
        thread_records, thread_fields = [], {}
        # allocate positions: sample distinct call positions for all thread calls, then assign in order
        n_thread_calls = sum(1 + c for c in comp["traps"]) + comp["neutral"]
        if trap_field == "qty+threshold":
            n_thread_calls += len(comp["traps"])  # one extra threshold READ per trap (compound question needs two facts)
        for attempt in range(1000):
            pos = sorted(r.sample(range(L), n_thread_calls))
            # neutral reads should not be the very last call; trap reads should be in the first 60%
            ok = True
            # assign greedily: traps first (each needs 1 read + c writes with gaps >= 2), then neutral reads
            cursor = list(pos)
            assign = []
            for c in comp["traps"]:
                need = 1 + c
                picks = []
                for _ in range(need):
                    # choose the earliest remaining position that is >= previous + 2
                    cand = [p for p in cursor if (not picks or p >= picks[-1] + 2)]
                    if not cand:
                        ok = False; break
                    p = cand[0] if not picks else cand[0]
                    picks.append(p); cursor.remove(p)
                if not ok or picks[0] > int(0.6 * L) or picks[-1] >= L - 2:
                    ok = False; break
                assign.append(("trap", picks))
                if trap_field == "qty+threshold":
                    cand = [p for p in cursor if p < L - 1]
                    if not cand:
                        ok = False; break
                    p2 = cand[0]; cursor.remove(p2)
                    assign.append(("trap2", [p2]))
            if not ok:
                continue
            for _ in range(comp["neutral"]):
                if not cursor:
                    ok = False; break
                p = cursor.pop(0)
                if p >= L - 1:
                    ok = False; break
                assign.append(("neutral", [p]))
            if ok:
                break
        else:
            raise RuntimeError("could not place threads")
        # shuffle which trap chain gets which positions is implicit in sampling; now instantiate records and steps
        calls = {}
        questions = []  # (after_call_index, qdict)
        ti = 0
        trap_iter = iter(comp["traps"])
        pending_pair = None
        for kind, picks in assign:
            rec = self.new_record() if kind != "trap2" else pending_pair
            if kind == "trap":
                chain = next(trap_iter)
                f = "qty" if trap_field == "qty+threshold" else trap_field
                ext = EXTERNAL.get((self.domain, self.template))
                if ext and self.domain == "calendar":
                    self._tweak("events", rec, "status", "confirmed")  # must appear on the room schedule
                thread_records.append(rec); thread_fields.setdefault(rec, set()).add(f)
                calls[picks[0]] = dict(self.read_step(f, rec), role="trap_read", thread=f"t{ti}", record=rec, field=f)
                n_own = chain - 1 if ext else chain
                for k in range(n_own):
                    calls[picks[1 + k]] = dict(self.write_step(f, rec, k), role="trap_write", thread=f"t{ti}", record=rec, field=f, write_index=k)
                    env.Executor.call(self._ex(), calls[picks[1 + k]]["tool"], calls[picks[1 + k]]["args"])  # keep live state consistent
                if ext:
                    changes = self.external_value(f, rec, chain - 1)
                    reveal = self.reveal_step(rec)
                    calls[picks[-1]] = dict(reveal, role="trap_reveal", thread=f"t{ti}", record=rec, field=f,
                                            external=[{"record": rec, "field": ff, "value": v} for ff, v in changes])
                qafter = min(L, picks[-1] + r.randint(*QGAP[L]))
                tk = "external" if ext else "own"
                if trap_field == "qty+threshold":
                    pending_pair = rec
                    pending_q = (qafter, {"qkind": "below_threshold", "record": rec, "thread": f"t{ti}", "trap": True, "chain": chain, "trap_kind": tk, "fields": ["qty", "threshold"]})
                else:
                    questions.append((qafter, {"qkind": qkind_for(f, self.domain), "record": rec, "thread": f"t{ti}", "trap": True, "chain": chain, "trap_kind": tk, "fields": [f]}))
                ti += 1
            elif kind == "trap2":
                f = "threshold"
                thread_fields[rec].add(f)
                calls[picks[0]] = dict(self.read_step(f, rec), role="compound_read", thread=f"t{ti - 1}", record=rec, field=f)
                qa, qd = pending_q
                questions.append((min(L, max(qa, picks[0] + 2)), qd))
                pending_pair = None
            else:
                f = neutral_field
                thread_records.append(rec); thread_fields.setdefault(rec, set()).add(f)
                step = self.read_step(f if f != "status" else "status", rec)
                calls[picks[0]] = dict(step, role="neutral_read", thread=f"n{ti}", record=rec, field=f)
                qk = qkind_for(f, self.domain)
                questions.append((min(L, picks[0] + r.randint(*QGAP[L])), {"qkind": qk, "record": rec, "thread": f"n{ti}", "trap": False, "chain": 0, "trap_kind": None, "fields": [f]}))
                ti += 1
        # fill distractors
        for p in range(L):
            if p not in calls:
                calls[p] = dict(self.distractor_step(thread_records, thread_fields), role="distractor", thread=None, record=None, field=None)
        return calls, questions, thread_records

    def _ex(self):
        if not hasattr(self, "_exec"):
            self._exec = env.Executor(self.live)
            self._exec.state = self.live  # scratch state: trap writes applied here so later values stay consistent
        return self._exec


def make_task(domain, template, length, distractor, seed):
    g = Gen(domain, template, length, distractor, seed)
    calls, questions, thread_records = g.build()
    # Initial state: the state before any trap write was applied. g._init_snapshot was taken at the first write;
    # records created later (distractors) must be added to it.
    import copy
    init = copy.deepcopy(g.state)  # initial state: never mutated by scripted calls during generation
    # Replay the full scripted plan on the init state to compute scripted answers and supersession annotations.
    ex = env.Executor(init)
    L = length
    steps = []
    stated = {}  # (record, field) -> step index that last stated it
    qs_by_pos = {}
    for qa, qd in questions:
        qs_by_pos.setdefault(qa, []).append(qd)
    si = 0
    external_updates = []
    for p in range(L):
        c = calls[p]
        si += 1
        for e in c.get("external", []):
            ex.apply_external(e["record"], e["field"], e["value"])
            external_updates.append({"before_step": si, **e})
        res, states = ex.call(c["tool"], c["args"])
        assert "error" not in res, (domain, template, length, distractor, seed, c, res)
        if c["role"] == "trap_reveal":
            assert any(rec == c["record"] for rec, _ in states), ("reveal row missing", domain, template, length, distractor, seed, c, res)
        step = {"i": si, "kind": "action", "tool": c["tool"], "args": c["args"], "role": c["role"], "thread": c["thread"],
                "record": c["record"], "field": c["field"], "states": states, "scripted_result": res,
                "user": {1: prompts.action_text(c["tool"], c["args"], 1), 2: prompts.action_text(c["tool"], c["args"], 2)}}
        steps.append(step)
        for qd in qs_by_pos.get(p + 1, []):
            si += 1
            ans = ex.answer(qd)
            qk = qd["qkind"]
            steps.append({"i": si, "kind": "question", "qkind": qk, "record": qd["record"], "thread": qd["thread"], "trap": qd["trap"],
                          "chain": qd["chain"], "trap_kind": qd.get("trap_kind"), "fields": qd["fields"], "scripted_answer": ans,
                          "user": {1: prompts.question_text(qk, qd["record"], 1), 2: prompts.question_text(qk, qd["record"], 2)}})
    tid = f"{domain[:3]}-{template}-L{length}-{distractor}-s{seed}"
    return {"task_id": tid, "domain": domain, "template": template, "length": length, "distractor": distractor, "seed": seed,
            "goal": prompts.GOAL[domain], "init_state": init, "steps": steps, "external_updates": external_updates,
            "trap_kind": "external" if (domain, template) in EXTERNAL else "own",
            "n_questions": sum(1 for s in steps if s["kind"] == "question"), "n_trap": sum(1 for s in steps if s["kind"] == "question" and s["trap"])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", action="store_true")
    args = ap.parse_args()
    tasks = []
    for d in DOMAINS:
        for t in TEMPLATES[d]:
            for L in LENGTHS:
                for dis in DISTRACTORS:
                    for s in SEEDS:
                        tasks.append(make_task(d, t, L, dis, s))
    prompts.QUESTION.setdefault("supplier", ("who is the primary supplier of {record}?", "<supplier name>"))
    json.dump({"tasks": tasks, "design": COMPOSITION, "templates": TEMPLATES}, open(CORPUS / "tasks.json", "w"), indent=1)
    json.dump({"system": prompts.SYSTEM, "tools": env.openai_tools()}, open(CORPUS / "tools.json", "w"), indent=1)
    nq = sum(t["n_questions"] for t in tasks); ntr = sum(t["n_trap"] for t in tasks)
    print(f"{len(tasks)} tasks, {nq} questions ({ntr} trap, {nq - ntr} neutral), {sum(t['length'] for t in tasks)} tool calls")
    if args.freeze:
        h = hashlib.sha256()
        for f in ("tasks.json", "tools.json"):
            h.update((CORPUS / f).read_bytes())
        man = {"frozen": __import__("time").strftime("%Y-%m-%dT%H:%M:%S"), "manifest_sha256": h.hexdigest(), "n_tasks": len(tasks),
               "files": {f: hashlib.sha256((CORPUS / f).read_bytes()).hexdigest() for f in ("tasks.json", "tools.json")}}
        json.dump(man, open(CORPUS / "FROZEN.json", "w"), indent=1)
        print("FROZEN", man["manifest_sha256"])


if __name__ == "__main__":
    main()
