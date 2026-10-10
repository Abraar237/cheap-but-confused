"""StaleTrap environment: three stateful tool domains (inventory, calendar, ticketing) with
JSON-schema tool declarations, a deterministic local mock executor, and schema-level
read/write metadata used to decide which earlier observations are superseded.

Every tool declares what it READS and what it WRITES at the (record, field) level. An
observation that states the value of (record, field) is superseded when a LATER observation
states the value of the same (record, field). Writes used in stale-trap threads always report
the new value explicitly in their result, so supersession is well defined and inferable from
the transcript alone (no hidden state is needed by the L3 pruner or the L4 recitation block)."""

import copy
import json

PEOPLE = ["Priya Nair", "Tom Okafor", "Lena Fischer", "Marco Silva", "Aisha Khan", "Diego Ruiz",
          "Hannah Lee", "Yusuf Demir", "Chloe Martin", "Ravi Menon", "Sofia Rossi", "Ben Carter"]
ROOMS = ["Aurora", "Baltic", "Cedar", "Delta", "Everest", "Fjord"]
BINS = ["A-01", "A-07", "B-03", "B-12", "C-04", "C-09", "D-02", "D-11"]
SUPPLIERS = ["Northwind Supply", "Keystone Parts", "Vega Components", "Harbor Goods", "Summit Wholesale"]
PRIORITIES = ["P1", "P2", "P3", "P4"]
STATUSES = ["open", "pending", "in_progress", "resolved"]
TAGS = ["billing", "login", "latency", "mobile", "export", "sso", "api", "ui"]
SLA = {"P1": 4, "P2": 8, "P3": 24, "P4": 72}


def tool(name, desc, props, required, reads=None, writes=None, record_arg=None, domain=None):
    return {"name": name, "description": desc, "parameters": {"type": "object", "properties": props, "required": required},
            "reads": reads or [], "writes": writes or [], "record_arg": record_arg, "domain": domain}


P_SKU = {"sku": {"type": "string", "description": "Stock keeping unit identifier, e.g. SKU-4471."}}
P_EVT = {"event_id": {"type": "string", "description": "Calendar event identifier, e.g. EVT-2093."}}
P_TCK = {"ticket_id": {"type": "string", "description": "Support ticket identifier, e.g. TCK-5810."}}

TOOLS = [
    # ---------------- inventory ----------------
    tool("get_stock", "Return the current on-hand quantity and storage bin for one SKU in the main warehouse. The quantity is the live count at the moment of the call; it does not include inbound shipments that have not been received yet.",
         P_SKU, ["sku"], reads=["qty", "bin"], record_arg="sku", domain="inventory"),
    tool("get_price", "Return the current unit sale price (USD) of one SKU as it appears in the storefront catalogue. Prices are updated by set_price; promotional discounts are not reflected here.",
         P_SKU, ["sku"], reads=["price"], record_arg="sku", domain="inventory"),
    tool("get_reorder_threshold", "Return the reorder threshold for one SKU: the on-hand quantity at or below which the purchasing team should raise a purchase order.",
         P_SKU, ["sku"], reads=["threshold"], record_arg="sku", domain="inventory"),
    tool("get_supplier", "Return the primary supplier and quoted lead time in days for one SKU. Lead time is quoted from the day a purchase order is placed.",
         P_SKU, ["sku"], reads=["supplier"], record_arg="sku", domain="inventory"),
    tool("list_bin_contents", "List every SKU stored in one warehouse bin with its on-hand quantity. Useful for cycle counts. Returns an array of {sku, qty} objects ordered by SKU.",
         {"bin": {"type": "string", "description": "Bin code, e.g. B-03."}}, ["bin"], reads=[], record_arg="bin", domain="inventory"),
    tool("receive_shipment", "Record the receipt of an inbound shipment for one SKU. Increases the on-hand quantity by the received units and returns the new on-hand quantity.",
         {**P_SKU, "units": {"type": "integer", "description": "Number of units received (positive integer)."}}, ["sku", "units"],
         reads=[], writes=["qty"], record_arg="sku", domain="inventory"),
    tool("ship_order", "Ship units of one SKU against a customer order. Decreases the on-hand quantity by the shipped units and returns the new on-hand quantity. Fails if insufficient stock.",
         {**P_SKU, "units": {"type": "integer", "description": "Number of units to ship (positive integer)."}}, ["sku", "units"],
         reads=[], writes=["qty"], record_arg="sku", domain="inventory"),
    tool("set_price", "Set the unit sale price (USD) of one SKU in the storefront catalogue. Returns the SKU and the price now in effect.",
         {**P_SKU, "price": {"type": "number", "description": "New unit price in USD, e.g. 12.50."}}, ["sku", "price"],
         reads=[], writes=["price"], record_arg="sku", domain="inventory"),
    tool("move_stock", "Move all on-hand units of one SKU to a different warehouse bin. Returns the SKU and the bin it is now stored in.",
         {**P_SKU, "to_bin": {"type": "string", "description": "Destination bin code, e.g. C-04."}}, ["sku", "to_bin"],
         reads=[], writes=["bin"], record_arg="sku", domain="inventory"),
    tool("set_reorder_threshold", "Set the reorder threshold for one SKU. Returns the SKU and the threshold now in effect.",
         {**P_SKU, "threshold": {"type": "integer", "description": "New reorder threshold in units."}}, ["sku", "threshold"],
         reads=[], writes=["threshold"], record_arg="sku", domain="inventory"),
    # ---------------- calendar ----------------
    tool("get_event", "Return one calendar event: title, date, start and end time (24-hour HH:MM, office local time), room, attendee list and status (confirmed or cancelled).",
         P_EVT, ["event_id"], reads=["start", "end", "room", "attendees", "status"], record_arg="event_id", domain="calendar"),
    tool("get_room_schedule", "List the events booked in one meeting room on one date, with their start and end times. Returns an array ordered by start time.",
         {"room": {"type": "string", "description": "Room name, e.g. Cedar."}, "date": {"type": "string", "description": "ISO date, e.g. 2026-10-14."}},
         ["room", "date"], reads=[], record_arg="room", domain="calendar"),
    tool("get_availability", "Return the free time windows of one person on one date between 09:00 and 18:00 office time, as an array of {from, to} in HH:MM.",
         {"person": {"type": "string", "description": "Full name of the person."}, "date": {"type": "string", "description": "ISO date."}},
         ["person", "date"], reads=[], record_arg="person", domain="calendar"),
    tool("reschedule_event", "Move one calendar event to a new start and end time on the same date. Attendees are notified automatically. Returns the event id and the start and end time now in effect.",
         {**P_EVT, "new_start": {"type": "string", "description": "New start time HH:MM (24-hour)."}, "new_end": {"type": "string", "description": "New end time HH:MM (24-hour)."}},
         ["event_id", "new_start", "new_end"], reads=[], writes=["start", "end"], record_arg="event_id", domain="calendar"),
    tool("move_event_room", "Change the meeting room of one calendar event. Returns the event id and the room now assigned.",
         {**P_EVT, "room": {"type": "string", "description": "New room name."}}, ["event_id", "room"],
         reads=[], writes=["room"], record_arg="event_id", domain="calendar"),
    tool("add_attendee", "Add one person to the attendee list of a calendar event. Returns the event id and the full attendee list now on the invitation.",
         {**P_EVT, "person": {"type": "string", "description": "Full name of the person to add."}}, ["event_id", "person"],
         reads=[], writes=["attendees"], record_arg="event_id", domain="calendar"),
    tool("remove_attendee", "Remove one person from the attendee list of a calendar event. Returns the event id and the full attendee list now on the invitation.",
         {**P_EVT, "person": {"type": "string", "description": "Full name of the person to remove."}}, ["event_id", "person"],
         reads=[], writes=["attendees"], record_arg="event_id", domain="calendar"),
    tool("cancel_event", "Cancel one calendar event and notify attendees. Returns the event id and its status, which will be cancelled.",
         P_EVT, ["event_id"], reads=[], writes=["status"], record_arg="event_id", domain="calendar"),
    tool("set_event_title", "Rename one calendar event. Returns the event id and the title now in effect.",
         {**P_EVT, "title": {"type": "string", "description": "New title."}}, ["event_id", "title"],
         reads=[], writes=["title"], record_arg="event_id", domain="calendar"),
    # ---------------- ticketing ----------------
    tool("get_ticket", "Return one support ticket: subject, priority (P1 highest to P4 lowest), assignee, status, tags and the number of comments.",
         P_TCK, ["ticket_id"], reads=["priority", "assignee", "status", "tags"], record_arg="ticket_id", domain="ticketing"),
    tool("get_agent_load", "Return the number of open tickets currently assigned to one support agent.",
         {"agent": {"type": "string", "description": "Full name of the support agent."}}, ["agent"], reads=["load"], record_arg="agent", domain="ticketing"),
    tool("get_sla_policy", "Return the response-time SLA in hours for a priority level under the current support policy.",
         {"priority": {"type": "string", "enum": PRIORITIES, "description": "Priority level."}}, ["priority"], reads=[], record_arg="priority", domain="ticketing"),
    tool("list_tickets", "List tickets in one status with their id, subject, priority and assignee. Returns an array ordered by ticket id.",
         {"status": {"type": "string", "enum": STATUSES, "description": "Ticket status to filter on."}}, ["status"], reads=[], record_arg="status", domain="ticketing"),
    tool("assign_ticket", "Assign one ticket to a support agent, replacing the previous assignee. Returns the ticket id and the assignee now responsible.",
         {**P_TCK, "agent": {"type": "string", "description": "Full name of the agent."}}, ["ticket_id", "agent"],
         reads=[], writes=["assignee"], record_arg="ticket_id", domain="ticketing"),
    tool("set_priority", "Set the priority of one ticket. Returns the ticket id and the priority now in effect.",
         {**P_TCK, "priority": {"type": "string", "enum": PRIORITIES, "description": "New priority."}}, ["ticket_id", "priority"],
         reads=[], writes=["priority"], record_arg="ticket_id", domain="ticketing"),
    tool("set_status", "Change the status of one ticket. Returns the ticket id and the status now in effect.",
         {**P_TCK, "status": {"type": "string", "enum": STATUSES, "description": "New status."}}, ["ticket_id", "status"],
         reads=[], writes=["status"], record_arg="ticket_id", domain="ticketing"),
    tool("add_tag", "Add a tag to one ticket. Returns the ticket id and the full list of tags now on the ticket.",
         {**P_TCK, "tag": {"type": "string", "description": "Tag to add, lower-case."}}, ["ticket_id", "tag"],
         reads=[], writes=["tags"], record_arg="ticket_id", domain="ticketing"),
    tool("add_comment", "Append an internal comment to one ticket. Returns the ticket id and the new comment count.",
         {**P_TCK, "text": {"type": "string", "description": "Comment text."}}, ["ticket_id", "text"],
         reads=[], writes=["comments"], record_arg="ticket_id", domain="ticketing"),
    tool("escalate_ticket", "Escalate one ticket by one priority level (P4 to P3, P3 to P2, P2 to P1) and flag it for the on-call lead. Returns the ticket id and the priority now in effect.",
         P_TCK, ["ticket_id"], reads=[], writes=["priority"], record_arg="ticket_id", domain="ticketing"),
    # ---------------- messaging and HR (present in the catalogue, never required by any task) ----------------
    tool("send_message", "Send a direct message to one colleague through the internal chat system. The message is delivered immediately and cannot be recalled. Returns the message id and delivery timestamp.",
         {"recipient": {"type": "string", "description": "Full name of the recipient."}, "text": {"type": "string", "description": "Message body, plain text, at most 2,000 characters."},
          "urgent": {"type": "boolean", "description": "Mark the message as urgent (triggers a push notification). Default false."}}, ["recipient", "text"], domain="messaging"),
    tool("post_channel_update", "Post an update to a named team channel. Channel names are lower-case with hyphens, e.g. warehouse-ops. Returns the post id. Posts are visible to every channel member.",
         {"channel": {"type": "string", "description": "Channel name."}, "text": {"type": "string", "description": "Post body."}}, ["channel", "text"], domain="messaging"),
    tool("schedule_message", "Schedule a direct message for later delivery at an office-local time today. Returns the scheduled message id. Scheduled messages can be cancelled with cancel_scheduled_message until they are sent.",
         {"recipient": {"type": "string", "description": "Full name of the recipient."}, "text": {"type": "string", "description": "Message body."}, "send_at": {"type": "string", "description": "Delivery time HH:MM (24-hour), today."}},
         ["recipient", "text", "send_at"], domain="messaging"),
    tool("cancel_scheduled_message", "Cancel a scheduled direct message that has not been sent yet. Returns the message id and its status, which will be cancelled.",
         {"message_id": {"type": "string", "description": "Scheduled message identifier, e.g. MSG-31207."}}, ["message_id"], domain="messaging"),
    tool("get_channel_members", "List the members of a team channel with their roles (owner, member). Returns an array ordered by name.",
         {"channel": {"type": "string", "description": "Channel name."}}, ["channel"], domain="messaging"),
    tool("get_employee", "Return the directory record of one employee: full name, team, manager, office location and employment status.",
         {"person": {"type": "string", "description": "Full name of the employee."}}, ["person"], domain="hr"),
    tool("get_time_off_balance", "Return the remaining paid time off in days for one employee for the current calendar year, split into vacation and sick leave.",
         {"person": {"type": "string", "description": "Full name of the employee."}}, ["person"], domain="hr"),
    tool("request_time_off", "File a paid time off request for one employee covering an inclusive date range. The request goes to the employee's manager for approval. Returns the request id and status (pending).",
         {"person": {"type": "string", "description": "Full name of the employee."}, "start_date": {"type": "string", "description": "First day off, ISO date."}, "end_date": {"type": "string", "description": "Last day off, ISO date."},
          "kind": {"type": "string", "enum": ["vacation", "sick", "unpaid"], "description": "Type of leave."}}, ["person", "start_date", "end_date", "kind"], domain="hr"),
    tool("submit_expense", "Submit an expense claim for one employee. Amounts are in US dollars with two decimals. Returns the claim id and status (submitted). Receipts are attached separately by the employee.",
         {"person": {"type": "string", "description": "Full name of the employee."}, "amount": {"type": "number", "description": "Claim amount in USD."}, "category": {"type": "string", "enum": ["travel", "meals", "equipment", "other"], "description": "Expense category."},
          "memo": {"type": "string", "description": "Short description of the expense."}}, ["person", "amount", "category"], domain="hr"),
    tool("post_job_opening", "Publish a job opening on the internal careers page. Returns the posting id. Postings are visible company-wide within one hour.",
         {"title": {"type": "string", "description": "Job title."}, "team": {"type": "string", "description": "Hiring team."}, "location": {"type": "string", "description": "Office location or Remote."},
          "level": {"type": "string", "enum": ["junior", "mid", "senior", "lead"], "description": "Seniority level."}}, ["title", "team", "location", "level"], domain="hr"),
]
TOOL_BY_NAME = {t["name"]: t for t in TOOLS}


def openai_tools():
    """Tool declarations in OpenAI function-calling format (byte-stable: built once, same order)."""
    return [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}} for t in TOOLS]


def _st(rec, fields):
    return [[rec, f] for f in fields]


class Executor:
    """Deterministic mock backend. State is a dict of records keyed by id. Every call returns a
    JSON-serialisable result plus the flat list of [record, field] pairs it STATES (dedicated reads,
    writes that report the new value, and every row of a listing), so the runner can annotate
    supersession from the transcript alone."""

    def __init__(self, state):
        self.state = copy.deepcopy(state)

    def apply_external(self, record, field, value):
        """A change made by someone else in the world (never by the agent). Applied by the runner before a scripted step."""
        for coll in ("skus", "events", "tickets"):
            if record in self.state[coll]:
                self.state[coll][record][field] = value
                return True
        return False

    def call(self, name, args):
        res, st = self._call(name, args)
        if st is None:
            return res, []
        if isinstance(st, tuple):
            return res, _st(st[0], st[1])
        return res, st

    def _call(self, name, args):
        s = self.state
        t = TOOL_BY_NAME.get(name)
        if t is None:
            return {"error": f"Unknown tool: {name}"}, None
        try:
            if name == "get_stock":
                r = s["skus"][args["sku"]]; return {"sku": args["sku"], "qty": r["qty"], "bin": r["bin"]}, (args["sku"], ["qty", "bin"])
            if name == "get_price":
                r = s["skus"][args["sku"]]; return {"sku": args["sku"], "price": r["price"], "currency": "USD"}, (args["sku"], ["price"])
            if name == "get_reorder_threshold":
                r = s["skus"][args["sku"]]; return {"sku": args["sku"], "reorder_threshold": r["threshold"]}, (args["sku"], ["threshold"])
            if name == "get_supplier":
                r = s["skus"][args["sku"]]; return {"sku": args["sku"], "supplier": r["supplier"], "lead_time_days": r["lead"]}, (args["sku"], ["supplier"])
            if name == "list_bin_contents":
                items = [{"sku": k, "qty": v["qty"]} for k, v in sorted(s["skus"].items()) if v["bin"] == args["bin"]]
                return {"bin": args["bin"], "items": items}, [[it["sku"], "qty"] for it in items]
            if name == "receive_shipment":
                r = s["skus"][args["sku"]]; r["qty"] += int(args["units"])
                return {"ok": True, "sku": args["sku"], "received": int(args["units"]), "qty": r["qty"]}, (args["sku"], ["qty"])
            if name == "ship_order":
                r = s["skus"][args["sku"]]
                if r["qty"] < int(args["units"]):
                    return {"ok": False, "error": f"insufficient stock: {r['qty']} on hand"}, None
                r["qty"] -= int(args["units"])
                return {"ok": True, "sku": args["sku"], "shipped": int(args["units"]), "qty": r["qty"]}, (args["sku"], ["qty"])
            if name == "set_price":
                r = s["skus"][args["sku"]]; r["price"] = round(float(args["price"]), 2)
                return {"ok": True, "sku": args["sku"], "price": r["price"], "currency": "USD"}, (args["sku"], ["price"])
            if name == "move_stock":
                r = s["skus"][args["sku"]]; r["bin"] = args["to_bin"]
                return {"ok": True, "sku": args["sku"], "bin": r["bin"]}, (args["sku"], ["bin"])
            if name == "set_reorder_threshold":
                r = s["skus"][args["sku"]]; r["threshold"] = int(args["threshold"])
                return {"ok": True, "sku": args["sku"], "reorder_threshold": r["threshold"]}, (args["sku"], ["threshold"])
            # calendar
            if name == "get_event":
                r = s["events"][args["event_id"]]
                return {"event_id": args["event_id"], "title": r["title"], "date": r["date"], "start": r["start"], "end": r["end"], "room": r["room"],
                        "attendees": list(r["attendees"]), "status": r["status"]}, (args["event_id"], ["start", "end", "room", "attendees", "status", "title"])
            if name == "get_room_schedule":
                evs = [{"event_id": k, "start": v["start"], "end": v["end"]} for k, v in sorted(s["events"].items(), key=lambda kv: kv[1]["start"])
                       if v["room"] == args["room"] and v["date"] == args["date"] and v["status"] == "confirmed"]
                return {"room": args["room"], "date": args["date"], "events": evs}, [[e["event_id"], f] for e in evs for f in ("start", "end")]
            if name == "get_availability":
                return {"person": args["person"], "date": args["date"], "free": s["availability"].get(args["person"], [{"from": "09:00", "to": "18:00"}])}, None
            if name == "reschedule_event":
                r = s["events"][args["event_id"]]; r["start"] = args["new_start"]; r["end"] = args["new_end"]
                return {"ok": True, "event_id": args["event_id"], "start": r["start"], "end": r["end"]}, (args["event_id"], ["start", "end"])
            if name == "move_event_room":
                r = s["events"][args["event_id"]]; r["room"] = args["room"]
                return {"ok": True, "event_id": args["event_id"], "room": r["room"]}, (args["event_id"], ["room"])
            if name == "add_attendee":
                r = s["events"][args["event_id"]]
                if args["person"] not in r["attendees"]:
                    r["attendees"].append(args["person"])
                return {"ok": True, "event_id": args["event_id"], "attendees": list(r["attendees"])}, (args["event_id"], ["attendees"])
            if name == "remove_attendee":
                r = s["events"][args["event_id"]]
                r["attendees"] = [p for p in r["attendees"] if p != args["person"]]
                return {"ok": True, "event_id": args["event_id"], "attendees": list(r["attendees"])}, (args["event_id"], ["attendees"])
            if name == "cancel_event":
                r = s["events"][args["event_id"]]; r["status"] = "cancelled"
                return {"ok": True, "event_id": args["event_id"], "status": "cancelled"}, (args["event_id"], ["status"])
            if name == "set_event_title":
                r = s["events"][args["event_id"]]; r["title"] = args["title"]
                return {"ok": True, "event_id": args["event_id"], "title": r["title"]}, (args["event_id"], ["title"])
            # ticketing
            if name == "get_ticket":
                r = s["tickets"][args["ticket_id"]]
                return {"ticket_id": args["ticket_id"], "subject": r["subject"], "priority": r["priority"], "assignee": r["assignee"], "status": r["status"],
                        "tags": list(r["tags"]), "comments": r["comments"]}, (args["ticket_id"], ["priority", "assignee", "status", "tags", "comments"])
            if name == "get_agent_load":
                n = sum(1 for v in s["tickets"].values() if v["assignee"] == args["agent"] and v["status"] != "resolved")
                return {"agent": args["agent"], "open_tickets": n + s["base_load"].get(args["agent"], 0)}, (args["agent"], ["load"])
            if name == "get_sla_policy":
                return {"priority": args["priority"], "response_sla_hours": SLA[args["priority"]]}, None
            if name == "list_tickets":
                rows = [{"ticket_id": k, "subject": v["subject"], "priority": v["priority"], "assignee": v["assignee"]}
                        for k, v in sorted(s["tickets"].items()) if v["status"] == args["status"]]
                return {"status": args["status"], "tickets": rows}, [[r["ticket_id"], f] for r in rows for f in ("priority", "assignee")]
            if name == "assign_ticket":
                r = s["tickets"][args["ticket_id"]]; r["assignee"] = args["agent"]
                return {"ok": True, "ticket_id": args["ticket_id"], "assignee": r["assignee"]}, (args["ticket_id"], ["assignee"])
            if name == "set_priority":
                r = s["tickets"][args["ticket_id"]]; r["priority"] = args["priority"]
                return {"ok": True, "ticket_id": args["ticket_id"], "priority": r["priority"]}, (args["ticket_id"], ["priority"])
            if name == "set_status":
                r = s["tickets"][args["ticket_id"]]; r["status"] = args["status"]
                return {"ok": True, "ticket_id": args["ticket_id"], "status": r["status"]}, (args["ticket_id"], ["status"])
            if name == "add_tag":
                r = s["tickets"][args["ticket_id"]]
                if args["tag"] not in r["tags"]:
                    r["tags"].append(args["tag"])
                return {"ok": True, "ticket_id": args["ticket_id"], "tags": list(r["tags"])}, (args["ticket_id"], ["tags"])
            if name == "add_comment":
                r = s["tickets"][args["ticket_id"]]; r["comments"] += 1
                return {"ok": True, "ticket_id": args["ticket_id"], "comments": r["comments"]}, (args["ticket_id"], ["comments"])
            if name == "escalate_ticket":
                r = s["tickets"][args["ticket_id"]]
                i = PRIORITIES.index(r["priority"]); r["priority"] = PRIORITIES[max(0, i - 1)]
                return {"ok": True, "ticket_id": args["ticket_id"], "priority": r["priority"]}, (args["ticket_id"], ["priority"])
            if t["domain"] in ("messaging", "hr"):
                return {"ok": True, "note": f"{name} accepted (no-op in this console)"}, None
        except KeyError as e:
            return {"error": f"Unknown record or missing argument: {e}"}, None
        except (TypeError, ValueError) as e:
            return {"error": f"Bad argument: {e}"}, None
        return {"error": "unhandled"}, None

    def state_value(self, rec, field):
        """Current value of (record, field) in the live state, in the same shape the tool results report it."""
        s = self.state
        for coll in ("skus", "events", "tickets"):
            if rec in s[coll]:
                v = s[coll][rec].get(field)
                return v
        if field == "load":
            return sum(1 for v in s["tickets"].values() if v["assignee"] == rec and v["status"] != "resolved") + s["base_load"].get(rec, 0)
        return None

    # ---- ground truth for questions, read from live state ----
    def answer(self, q):
        s = self.state
        k, rec = q["qkind"], q["record"]
        if k == "qty": return s["skus"][rec]["qty"]
        if k == "price": return s["skus"][rec]["price"]
        if k == "bin": return s["skus"][rec]["bin"]
        if k == "threshold": return s["skus"][rec]["threshold"]
        if k == "supplier": return s["skus"][rec]["supplier"]
        if k == "below_threshold": return "yes" if s["skus"][rec]["qty"] <= s["skus"][rec]["threshold"] else "no"
        if k == "start": return s["events"][rec]["start"]
        if k == "room": return s["events"][rec]["room"]
        if k == "n_attendees": return len(s["events"][rec]["attendees"])
        if k == "status_event": return s["events"][rec]["status"]
        if k == "assignee": return s["tickets"][rec]["assignee"]
        if k == "priority": return s["tickets"][rec]["priority"]
        if k == "sla_hours": return SLA[s["tickets"][rec]["priority"]]
        if k == "status_ticket": return s["tickets"][rec]["status"]
        if k == "n_tags": return len(s["tickets"][rec]["tags"])
        raise KeyError(k)


def canon(v):
    """Canonical form for exact-match scoring."""
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, (int, float)):
        f = float(v)
        return str(int(f)) if f.is_integer() else f"{f:.2f}"
    if isinstance(v, str):
        t = v.strip().strip('"').strip("'").lower()
        t = t.replace("$", "").replace("usd", "").strip()
        if t in ("true", "yes", "y"): return "yes"
        if t in ("false", "no", "n"): return "no"
        try:
            f = float(t.replace(",", ""))
            return str(int(f)) if f.is_integer() else f"{f:.2f}"
        except ValueError:
            pass
        import re
        m = re.fullmatch(r"(\d{1,2}):(\d{2})", t)
        if m:
            return f"{int(m.group(1)):02d}:{m.group(2)}"
        return " ".join(t.split())
    return json.dumps(v, sort_keys=True)
