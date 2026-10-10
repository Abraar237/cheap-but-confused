"""Layout hooks for the T2 (BFCL) arm.

A hook receives a DEEPCOPY of the running OpenAI-style message list that the official harness
has accumulated (system, user, assistant(tool_calls), tool, ... in arrival order) plus the
handler's `inference_data` dict, and returns the list that is actually sent to the API. The
harness's own history, the environment execution, the result file and the state-based checker
never see the re-serialised list. Hooks run right before every API call
(OpenRouterHandler._query_FC).

Blocks: a user turn = the user message plus the assistant tool-call message(s) and tool-result
message(s) that follow it until the next user message. The fixed system message is always first.

  L1  identity: append-only, prefix-stable (the cache-optimal layout).
  L3  practitioner pruner / observation masking by age: the content of every tool-result
      message older than the most recent 2 user turns is replaced by a placeholder; assistant
      tool_call messages stay intact so tool_call_ids still pair. Edits earlier bytes -> the
      cached prefix breaks at the first masked result.
  L4  L1 unchanged + a pointer-only session note prepended to the NEWEST user message:
      goal (first user message), current request, one line per EARLIER tool call (function
      name + first 60 chars of arguments, no results, no values; last 25 calls), and the
      staleness rule. Computed only from messages before the newest user message, so the note
      is byte-stable within a turn and the layout stays append-only.
  L2 is not run on T2 (budget).
"""

PLACEHOLDER = "[tool result from an earlier turn omitted]"
L3_KEEP_TURNS = 2
L4_MAX_CALLS = 25
L4_GOAL_CHARS = 300
L4_ARG_CHARS = 60


def _user_indices(messages):
    return [i for i, m in enumerate(messages) if m.get("role") == "user"]


def l1_identity(messages, inference_data):
    return messages


def l3_mask_by_age(messages, inference_data):
    users = _user_indices(messages)
    if len(users) <= L3_KEEP_TURNS:
        return messages
    cutoff = users[-L3_KEEP_TURNS]  # first message index of the oldest turn that is kept
    n_masked = 0
    for i in range(cutoff):
        m = messages[i]
        if m.get("role") == "tool" and m.get("content") != PLACEHOLDER:
            m["content"] = PLACEHOLDER
            n_masked += 1
    inference_data["_layout_stat"] = {"masked_tool_results": n_masked}
    return messages


def _call_lines(messages, upto):
    """One line per tool call in messages[:upto], numbered by session step."""
    lines = []
    k = 0
    for m in messages[:upto]:
        if m.get("role") != "assistant":
            continue
        for tc in m.get("tool_calls") or []:
            k += 1
            fn = tc.get("function", {})
            args = (fn.get("arguments") or "")[:L4_ARG_CHARS]
            lines.append(f"step {k}: {fn.get('name')}({args})")
    return lines


def _note_for(messages, u_idx, first_u):
    turn_n = sum(1 for m in messages[: u_idx + 1] if m.get("role") == "user")
    goal = str(messages[first_u].get("content") or "")[:L4_GOAL_CHARS]
    current = str(messages[u_idx].get("content") or "")
    lines = _call_lines(messages, u_idx)
    omitted = max(0, len(lines) - L4_MAX_CALLS)
    lines = lines[-L4_MAX_CALLS:]
    calls_txt = "\n".join(lines) if lines else "(none yet)"
    if omitted:
        calls_txt = f"(... {omitted} earlier calls not listed)\n" + calls_txt
    return (
        f"[Session note before turn {turn_n}] Goal so far: {goal}. "
        f"Current request: {current}. "
        f"Earlier tool calls in this session:\n{calls_txt}\n"
        "Rule: results of the most recent calls about the same object are current; earlier ones may be stale. "
        "[End of note]\n\n"
    )


def l4_session_note(messages, inference_data):
    """Persistent variant (v2): EVERY user message carries the note computed from the messages
    that precede it. Those messages never change later, so each note is byte-stable for the rest
    of the episode and the layout stays append-only (v1 decorated only the newest user message,
    which removed the previous turn's note at each turn boundary and broke the cached prefix)."""
    users = _user_indices(messages)
    if not users:
        return messages
    first_u = users[0]
    import copy as _copy
    pristine = _copy.deepcopy(messages)
    stat = {"notes": 0, "note_chars_newest": 0}
    for u in users:
        note = _note_for(pristine, u, first_u)
        # goal text is taken from the ORIGINAL first user message, before decoration
        messages[u]["content"] = note + str(messages[u].get("content") or "")
        stat["notes"] += 1
        stat["note_chars_newest"] = len(note)
    inference_data["_layout_stat"] = stat
    return messages


LAYOUTS = {
    "L1": l1_identity,
    "L3": l3_mask_by_age,
    "L4": l4_session_note,
}
