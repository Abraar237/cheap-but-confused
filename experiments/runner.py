#!/usr/bin/env python3
"""StaleTrap runner: one episode = one task x one layout x one model, turns strictly sequential,
temperature 0, randomised episode order, resume-safe JSONL keyed by model|task|layout|phrasing|rep|battery.
Every call logs OpenRouter's usage (prompt/cached/cache_write/completion/reasoning tokens, billed usage.cost,
provider, latency, finish_reason). Spend is tracked by cost_tracker.py with a $24 hard stop.

Usage:
  python3 runner.py --model google/gemini-2.5-flash-lite --layouts L1,L2,L3,L4 [--limit N] [--tasks REGEX]
                    [--phrasing 1] [--rep 0] [--battery none|nocache|repeat] [--workers 3] [--dry]
Records -> results/raw/<model-slug>.jsonl (one line per episode)."""

import argparse
import concurrent.futures as cf
import hashlib
import json
import pathlib
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.request

import cost_tracker
import env
import layouts

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
RAW = ROOT / "results" / "raw"
RAW.mkdir(parents=True, exist_ok=True)
DEBUG_DIR = ROOT / "results" / "_debug"
URL = "https://openrouter.ai/api/v1/chat/completions"
FAMILY = {"anthropic": "anthropic", "openai": "openai", "google": "google"}
MAX_TOKENS = 700          # tool-call arguments and the JSON answer are short; headroom for reasoning tokens
REASONING = "minimal"     # reasoning tokens bill as output (lesson 8); 'low' where minimal is rejected
TURN_TIMEOUT = 180


def env_key(key):
    for line in open(ROOT / ".env"):
        if line.startswith(key + "="):
            return line.strip().split("=", 1)[1].strip().strip('"').strip("'")
    raise KeyError(key)


class Client:
    def __init__(self, key):
        self.key = key

    def post(self, body, tries=6):
        data = json.dumps(body).encode()
        hdr = {"Authorization": "Bearer " + self.key, "Content-Type": "application/json",
               "HTTP-Referer": "https://github.com/Abraar237/cache-layout-cost", "X-Title": "cache-layout-cost"}
        last = None
        for attempt in range(tries):
            try:
                t0 = time.time()
                with urllib.request.urlopen(urllib.request.Request(URL, data=data, headers=hdr), timeout=TURN_TIMEOUT) as r:
                    return json.load(r), time.time() - t0
            except urllib.error.HTTPError as e:
                msg = e.read().decode()[:600]
                last = f"HTTP {e.code}: {msg}"
                if e.code == 402:
                    raise RuntimeError("OpenRouter credit exhausted: " + msg)
                if e.code in (408, 429, 500, 502, 503, 504, 524, 529) and attempt < tries - 1:
                    time.sleep(min(60, 2 ** attempt + random.random() * 2))
                    continue
                raise RuntimeError(last)
            except (urllib.error.URLError, TimeoutError, ConnectionResetError) as e:
                last = str(e)
                if attempt < tries - 1:
                    time.sleep(2 ** attempt)
                    continue
                raise RuntimeError(last)
        raise RuntimeError(last or "unknown")


ANSWER_RE = re.compile(r'"answer"\s*:\s*("(?:[^"\\]|\\.)*"|-?\d+(?:\.\d+)?|true|false|yes|no)', re.I)


def parse_answer(text):
    if not text:
        return None
    m = ANSWER_RE.search(text)
    if m:
        v = m.group(1)
        if v.startswith('"'):
            return json.loads(v)
        return v
    # fallback: bare JSON or a bare value
    t = text.strip().strip("`")
    try:
        obj = json.loads(t)
        if isinstance(obj, dict) and "answer" in obj:
            return obj["answer"]
    except json.JSONDecodeError:
        pass
    return t if len(t) < 40 else None


def usage_fields(resp):
    u = resp.get("usage") or {}
    ptd = u.get("prompt_tokens_details") or {}
    ctd = u.get("completion_tokens_details") or {}
    return {"prompt_tokens": u.get("prompt_tokens"), "cached_tokens": ptd.get("cached_tokens") or 0,
            "cache_write_tokens": ptd.get("cache_write_tokens") or 0, "completion_tokens": u.get("completion_tokens"),
            "reasoning_tokens": ctd.get("reasoning_tokens") or 0, "cost": float(u.get("cost") or 0.0),
            "cache_discount": resp.get("cache_discount"), "provider": resp.get("provider"), "resp_model": resp.get("model")}


def run_episode(cl, model, family, task, layout, phrasing, battery, system, tools, dry=False):
    """Plays one episode. Returns the episode record."""
    ex = env.Executor(task["init_state"])
    blocks = []
    turns = []
    step_scores = []
    goal = task["goal"][str(phrasing)]
    sid = hashlib.md5(f"{model}|{task['task_id']}|{layout}|{phrasing}|{battery}|{time.time()}".encode()).hexdigest()[:16]
    cache_control = battery != "nocache"
    t_start = time.time()
    ext_by_step = {}
    for e in task.get("external_updates", []):
        ext_by_step.setdefault(e["before_step"], []).append(e)
    for si, step in enumerate(task["steps"]):
        for e in ext_by_step.get(step["i"], []):
            ex.apply_external(e["record"], e["field"], e["value"])  # the world changes before this step; the agent is not told
        user_text = step["user"][str(phrasing)]
        if si == 0:
            user_text = goal + "\n\n" + user_text
        msgs = layouts.build_messages(layout, system, blocks, user_text, goal, step["i"], family, cache_control=cache_control)
        body = {"model": model, "temperature": 0, "max_tokens": MAX_TOKENS, "messages": msgs, "tools": tools,
                "tool_choice": "auto" if step["kind"] == "action" else "none",
                "reasoning": {"effort": REASONING}, "usage": {"include": True}, "session_id": sid}
        if family == "anthropic" and not cache_control:
            pass  # breakpoints simply omitted
        if dry:
            print(layouts.serialise_for_log(msgs)[-1500:])
            print("----")
            resp = {"choices": [{"message": {"content": "{\"answer\": 0}"}, "finish_reason": "stop"}], "usage": {}}
            lat = 0
            choice = resp["choices"][0]
            msg = choice.get("message") or {}
            uf = usage_fields(resp)
        else:
            for attempt in range(4):
                resp, lat = cl.post(body)
                choice = (resp.get("choices") or [{}])[0]
                msg = choice.get("message") or {}
                uf = usage_fields(resp)
                cost_tracker.log_call(model, uf["cost"], tag=layout)
                bad = (choice.get("finish_reason") in ("error", None)) or (resp.get("error") is not None) or \
                      (step["kind"] == "action" and not (msg.get("tool_calls") or (msg.get("content") or "").strip())) or \
                      (step["kind"] == "question" and not (msg.get("content") or "").strip())
                if not bad:
                    break
                err = resp.get("error") or choice.get("error") or {k: v for k, v in choice.items() if k not in ("message",)}
                turns.append({"step": step["i"], "kind": step["kind"], "latency": round(lat, 2), "finish": choice.get("finish_reason"),
                              "n_messages": len(msgs), "retry_discarded": True, "error": json.dumps(err)[:400], **uf})
                if attempt == 0:
                    DEBUG_DIR.mkdir(exist_ok=True)
                    (DEBUG_DIR / f"err_{int(time.time())}_{step['i']}.json").write_text(json.dumps(resp)[:20000])
                time.sleep(8 + attempt * 12 + random.random() * 4)
        turn = {"step": step["i"], "kind": step["kind"], "latency": round(lat, 2), "finish": choice.get("finish_reason"),
                "n_messages": len(msgs), **uf}
        turns.append(turn)
        content = msg.get("content")
        if isinstance(content, list):
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        tool_calls = []
        for tc in msg.get("tool_calls") or []:
            fn = tc.get("function") or {}
            name = fn.get("name") or ""
            raw_name = name
            for pre in ("default_api.", "default_api_", "functions.", "tools."):
                if name.startswith(pre) and name[len(pre):] in env.TOOL_BY_NAME:
                    name = name[len(pre):]
            tool_calls.append({"id": tc.get("id") or f"call_{step['i']}_{len(tool_calls)}", "name": name, "arguments": fn.get("arguments") or "{}",
                               **({"raw_name": raw_name} if raw_name != name else {})})
        sent_text = msgs[-1]["content"][0]["text"] if isinstance(msgs[-1].get("content"), list) else msgs[-1].get("content")
        block = {"step": step["i"], "kind": step["kind"], "user": user_text, "user_sent": sent_text,
                 "assistant": {"content": content, "tool_calls": tool_calls}, "tool_results": []}
        ment = set(layouts.mentions(user_text))
        score = {"step": step["i"], "kind": step["kind"]}
        if step["kind"] == "action":
            exp_tool, exp_args = step["tool"], step["args"]
            tool_ok = args_ok = exec_ok = False
            for tc in tool_calls:
                try:
                    args = json.loads(tc["arguments"]) if isinstance(tc["arguments"], str) else dict(tc["arguments"])
                except json.JSONDecodeError:
                    args = {}
                res, states = ex.call(tc["name"], args)
                rtxt = json.dumps(res)
                block["tool_results"].append({"tool_call_id": tc["id"], "name": tc["name"], "content": rtxt, "states": states or []})
                ment |= set(layouts.mentions(rtxt)) | set(layouts.mentions(json.dumps(args)))
                if tc["name"] == exp_tool:
                    tool_ok = True
                    args_ok = all(env.canon(args.get(k)) == env.canon(v) for k, v in exp_args.items()) and set(args) <= set(exp_args) | set(env.TOOL_BY_NAME[exp_tool]["parameters"]["properties"])
                    exec_ok = "error" not in res
            score.update({"role": step["role"], "tool_ok": tool_ok, "args_ok": args_ok, "exec_ok": exec_ok, "n_calls": len(tool_calls),
                          "called": [tc["name"] for tc in tool_calls]})
            if not tool_calls:
                score["no_call_text"] = (content or "")[:200]
        else:
            ans = parse_answer(content)
            actual = ex.answer(step)
            correct = env.canon(ans) == env.canon(actual) if ans is not None else False
            # did the trap materialise? a stale value for (record, field) must be present in context, i.e. some earlier
            # result stated the field with a value different from the current one
            f = step["fields"][0]
            key = layouts.RESULT_KEY.get(f, f)
            stale_present, current_present = False, False
            cur = ex.state_value(step["record"], f)
            for b in blocks:
                for r in b["tool_results"]:
                    for rec, ff in r["states"]:
                        if rec == step["record"] and ff == f:
                            v = None
                            try:
                                obj = json.loads(r["content"])
                                if key in obj and rec in [x for x in obj.values() if isinstance(x, str)]:
                                    v = obj.get(key)
                                else:
                                    for lv in obj.values():
                                        if isinstance(lv, list):
                                            for row in lv:
                                                if isinstance(row, dict) and rec in row.values() and key in row:
                                                    v = row[key]
                            except Exception:
                                v = None
                            if v is None:
                                continue
                            vv = len(v) if isinstance(v, list) else v
                            if env.canon(vv) == env.canon(cur):
                                current_present = True
                            else:
                                stale_present = True
            score.update({"trap": step["trap"], "chain": step["chain"], "trap_kind": step.get("trap_kind"), "qkind": step["qkind"], "record": step["record"],
                          "answer_raw": (content or "")[:300], "answer": ans, "actual": actual, "scripted": step["scripted_answer"],
                          "correct": bool(correct), "correct_scripted": env.canon(ans) == env.canon(step["scripted_answer"]) if ans is not None else False,
                          "stale_present": stale_present, "current_present": current_present, "parsed": ans is not None})
        block["mentions"] = sorted(ment)
        blocks.append(block)
        step_scores.append(score)
    qs = [s for s in step_scores if s["kind"] == "question"]
    acts = [s for s in step_scores if s["kind"] == "action"]
    live_turns = [t for t in turns if not t.get("retry_discarded")]
    rec = {"model": model, "family": family, "task_id": task["task_id"], "prefix_tokens_turn1": live_turns[0]["prompt_tokens"] if live_turns else None,
           "n_retries": sum(1 for t in turns if t.get("retry_discarded")), "n_name_normalised": sum(1 for b in blocks for tc in b["assistant"]["tool_calls"] if tc.get("raw_name")), "domain": task["domain"], "template": task["template"],
           "length": task["length"], "distractor": task["distractor"], "seed": task["seed"], "layout": layout, "phrasing": phrasing,
           "battery": battery, "session_id": sid, "wall_s": round(time.time() - t_start, 1),
           "n_turns": len(turns), "prompt_tokens": sum(t["prompt_tokens"] or 0 for t in turns),
           "cached_tokens": sum(t["cached_tokens"] or 0 for t in turns), "cache_write_tokens": sum(t["cache_write_tokens"] or 0 for t in turns),
           "completion_tokens": sum(t["completion_tokens"] or 0 for t in turns), "reasoning_tokens": sum(t["reasoning_tokens"] or 0 for t in turns),
           "cost": round(sum(t["cost"] for t in turns), 8),
           "q_total": len(qs), "q_correct": sum(1 for s in qs if s["correct"]), "episode_success": all(s["correct"] for s in qs) if qs else None,
           "trap_total": sum(1 for s in qs if s["trap"]), "trap_correct": sum(1 for s in qs if s["trap"] and s["correct"]),
           "neutral_total": sum(1 for s in qs if not s["trap"]), "neutral_correct": sum(1 for s in qs if not s["trap"] and s["correct"]),
           "action_tool_ok": sum(1 for s in acts if s["tool_ok"]), "action_args_ok": sum(1 for s in acts if s["args_ok"]), "action_total": len(acts),
           "turns": turns, "steps": step_scores, "transcript": blocks, "t": time.strftime("%Y-%m-%dT%H:%M:%S")}
    return rec


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--layouts", default="L1,L2,L3,L4")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--tasks", default="", help="regex on task_id")
    ap.add_argument("--phrasing", type=int, default=1)
    ap.add_argument("--rep", type=int, default=0)
    ap.add_argument("--battery", default="none", help="none | nocache (Anthropic breakpoints off) | repeat")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--seed", type=int, default=11)
    args = ap.parse_args()
    family = FAMILY[args.model.split("/")[0]]
    corpus = json.load(open(ROOT / "corpus" / "tasks.json"))
    tools_doc = json.load(open(ROOT / "corpus" / "tools.json"))
    system, tools = tools_doc["system"], tools_doc["tools"]
    frozen = ROOT / "corpus" / "FROZEN.json"
    frozen_sha = json.load(open(frozen))["manifest_sha256"][:16] if frozen.exists() else "UNFROZEN"
    tasks = [t for t in corpus["tasks"] if re.search(args.tasks, t["task_id"])] if args.tasks else corpus["tasks"]
    jobs = [(t, L) for t in tasks for L in args.layouts.split(",")]
    random.Random(args.seed).shuffle(jobs)
    if args.limit:
        jobs = jobs[: args.limit]
    slug = args.model.replace("/", "_")
    out_path = RAW / f"{slug}.jsonl"
    done = set()
    if out_path.exists():
        for line in open(out_path):
            try:
                done.add(json.loads(line)["key"])
            except Exception:
                pass

    def key_of(t, L):
        return hashlib.sha256(f"{args.model}|{t['task_id']}|{L}|{args.phrasing}|{args.rep}|{args.battery}".encode()).hexdigest()[:16]
    todo = [(t, L) for t, L in jobs if key_of(t, L) not in done]
    print(f"{args.model} [{family}] frozen={frozen_sha}: {len(jobs)} episodes, {len(todo)} to do, spend so far ${cost_tracker.total():.3f}", flush=True)
    cl = Client(env_key("OPENROUTER_API_KEY")) if not args.dry else None
    lock = threading.Lock()
    fout = open(out_path, "a")
    prog = {"n": 0, "fail": 0}

    def work(job):
        t, L = job
        try:
            rec = run_episode(cl, args.model, family, t, L, args.phrasing, args.battery, system, tools, dry=args.dry)
        except cost_tracker.CostCapExceeded as e:
            print("HARD STOP:", e, flush=True)
            raise
        except Exception as e:
            with lock:
                prog["fail"] += 1
            print(f"FAIL {t['task_id']} {L}: {str(e)[:300]}", flush=True)
            return
        rec.update({"key": key_of(t, L), "rep": args.rep, "corpus_sha": frozen_sha})
        if args.dry:
            return
        with lock:
            fout.write(json.dumps(rec) + "\n")
            fout.flush()
            prog["n"] += 1
            cr = rec["cached_tokens"] / max(1, rec["prompt_tokens"])
            print(f"[{prog['n']}/{len(todo)}] {t['task_id']:22s} {L} q={rec['q_correct']}/{rec['q_total']} trap={rec['trap_correct']}/{rec['trap_total']} "
                  f"acts={rec['action_args_ok']}/{rec['action_total']} cache={cr:.2f} ${rec['cost']:.4f} ({rec['wall_s']}s) total=${cost_tracker.total():.3f}", flush=True)

    if args.dry:
        for job in todo[:1]:
            work(job)
        return
    try:
        with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
            list(ex.map(work, todo))
    finally:
        fout.close()
    print(f"done: {prog['n']} ok, {prog['fail']} failed; spend ${cost_tracker.total():.3f}")


if __name__ == "__main__":
    main()
