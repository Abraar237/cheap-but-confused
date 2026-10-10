#!/usr/bin/env python
"""Thin wrapper around the official `bfcl` CLI for the T2 arm.

  * pins BFCL_PROJECT_ROOT to experiments/t2_bfcl/bfcl_root (result/, score/, .file_locks/,
    test_case_ids_to_generate.json live there, outside site-packages);
  * registers one OpenRouter model per layout under underscore-free keys
    (the evaluator maps result directory names back with .replace("_", "/"));
  * sub-commands: `set-ids`, `summarize`; everything else is passed to the bfcl CLI.

Usage (from experiments/t2_bfcl, venv python):
  python run_bfcl.py set-ids multi_turn_base=0,2,4 multi_turn_long_context=0,2,4
  python run_bfcl.py generate --model openrouter/google/gemini-3.1-flash-lite-l1 --run-ids --temperature 0
  python run_bfcl.py evaluate --model openrouter/google/gemini-3.1-flash-lite-l1 --test-category multi_turn --partial-eval
  python run_bfcl.py summarize google/gemini-3.1-flash-lite
"""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE / "bfcl_root"
ROOT.mkdir(exist_ok=True)
os.environ["BFCL_PROJECT_ROOT"] = str(ROOT)  # must be set before bfcl_eval is imported
sys.path.insert(0, str(HERE))
PROJECT = HERE.parent.parent
RAW_T2 = PROJECT / "results" / "raw" / "t2"

MODELS = {  # OpenRouter id -> (input $/M, output $/M)
    "google/gemini-3.1-flash-lite": (0.25, 1.5),
    "google/gemini-2.5-flash-lite": (0.10, 0.40),
    "anthropic/claude-haiku-5.5": (0.10, 0.50),
    "openai/gpt-5-mini": (0.25, 2.0),
}
LAYOUT_SUFFIXES = ["l1", "l3", "l4"]
CATEGORIES = ["multi_turn_base", "multi_turn_long_context"]


def registry_key(model_id, layout):
    return f"openrouter/{model_id}-{layout.lower()}"


def cmd_set_ids(specs):
    ids = {}
    for spec in specs:
        cat, nums = spec.split("=")
        ids[cat] = [f"{cat}_{n}" for n in nums.split(",") if n]
    (ROOT / "test_case_ids_to_generate.json").write_text(json.dumps(ids, indent=1))
    print("wrote", ROOT / "test_case_ids_to_generate.json", {k: len(v) for k, v in ids.items()})


def cmd_repair(model_id):
    """Drop entries whose result is an inference-error string from every layout's result files,
    so that a re-run of `generate --run-ids` regenerates exactly those tasks."""
    for lay in LAYOUT_SUFFIXES:
        rdir = ROOT / "result" / registry_key(model_id, lay).replace("/", "_") / "multi_turn"
        for cat in CATEGORIES:
            rf = rdir / f"BFCL_v4_{cat}_result.json"
            if not rf.exists():
                continue
            rows = [json.loads(l) for l in open(rf) if l.strip()]
            bad = [r["id"] for r in rows if isinstance(r.get("result"), str)]
            keep = [r for r in rows if not isinstance(r.get("result"), str)]
            with open(rf, "w") as f:
                for r in keep:
                    f.write(json.dumps(r) + "\n")
            print(f"{lay} {cat}: kept {len(keep)}, removed {len(bad)} error entries: {bad}")


def cmd_summarize(model_id):
    """scores_<layout>_<slug>.json (per-task pass/fail) and t2_summary.json."""
    slug = model_id.replace("/", "_")
    summary = {"model": model_id, "layouts": {}}
    for lay in LAYOUT_SUFFIXES:
        L = lay.upper()
        rdir = ROOT / "result" / registry_key(model_id, lay).replace("/", "_") / "multi_turn"
        sdir = ROOT / "score" / registry_key(model_id, lay).replace("/", "_") / "multi_turn"
        per_task = {}
        for cat in CATEGORIES:
            rf = rdir / f"BFCL_v4_{cat}_result.json"
            sf = sdir / f"BFCL_v4_{cat}_score.json"
            if not rf.exists():
                continue
            ids = [json.loads(l)["id"] for l in open(rf) if l.strip()]
            failed = {}
            if sf.exists():
                rows = [json.loads(l) for l in open(sf) if l.strip()]
                for r in rows[1:]:
                    failed[r["id"]] = r["error"].get("error_type")
            for i in ids:
                per_task[i] = {"category": cat, "pass": i not in failed, "error_type": failed.get(i)}
        # usage
        usage = {}
        aborted_cost = 0.0
        lf = RAW_T2 / f"{L}_{slug}.jsonl"
        if lf.exists():
            lines = [json.loads(l) for l in open(lf) if l.strip()]
            # attempts: (task, episode_uid or 'legacy'); keep the attempt whose last call is latest
            last_ts = {}
            for r in lines:
                key = (r["task_id"], r.get("episode_uid") or "legacy")
                last_ts[key] = max(last_ts.get(key, ""), r["ts"])
            final_attempt = {}
            for (t, uid), ts in last_ts.items():
                if t not in final_attempt or ts > final_attempt[t][1]:
                    final_attempt[t] = (uid, ts)
            for r in lines:
                t = r["task_id"]
                if (r.get("episode_uid") or "legacy") != final_attempt[t][0]:
                    aborted_cost += float(r.get("cost_usd") or 0)
                    continue
                u = usage.setdefault(t, {"cost": 0.0, "prompt": 0, "cached": 0, "completion": 0, "calls": 0,
                                         "turn1_prompt_tokens": None})
                u["cost"] += float(r.get("cost_usd") or 0)
                u["prompt"] += int(r.get("prompt_tokens") or 0)
                u["cached"] += int(r.get("cached_tokens") or 0)
                u["completion"] += int(r.get("completion_tokens") or 0)
                u["calls"] += 1
                if r.get("call_idx") == 0:
                    u["turn1_prompt_tokens"] = r.get("prompt_tokens")
        for t, rec in per_task.items():
            rec.update(usage.get(t, {}))
            if rec.get("prompt"):
                rec["cached_fraction"] = rec["cached"] / rec["prompt"]
        out = RAW_T2 / f"scores_{L}_{slug}.json"
        json.dump(per_task, open(out, "w"), indent=1, sort_keys=True)
        lay_sum = {"n_tasks": len(per_task), "total_cost_usd": round(sum(u["cost"] for u in usage.values()), 6),
                   "n_calls": sum(u["calls"] for u in usage.values()),
                   "aborted_attempts_cost_usd": round(aborted_cost, 6)}
        for cat in CATEGORIES:
            rows = [v for v in per_task.values() if v["category"] == cat]
            if rows:
                lay_sum[cat] = {
                    "n": len(rows),
                    "accuracy": sum(1 for v in rows if v["pass"]) / len(rows),
                    "mean_cost_per_task": sum(v.get("cost", 0) for v in rows) / len(rows),
                    "mean_cached_fraction": sum(v.get("cached_fraction", 0) for v in rows) / len(rows),
                    "mean_calls_per_task": sum(v.get("calls", 0) for v in rows) / len(rows),
                    "min_turn1_prompt_tokens": min((v.get("turn1_prompt_tokens") or 0) for v in rows),
                    "error_types": {et: sum(1 for v in rows if v["error_type"] == et)
                                    for et in sorted({v["error_type"] for v in rows if v["error_type"]})},
                }
        allrows = list(per_task.values())
        if allrows:
            lay_sum["mean_cost_per_task"] = sum(v.get("cost", 0) for v in allrows) / len(allrows)
            lay_sum["mean_cached_fraction"] = sum(v.get("cached_fraction", 0) for v in allrows) / len(allrows)
        summary["layouts"][L] = lay_sum
    # total T2 spend across all logs incl. MWE
    total = 0.0
    for f in list(RAW_T2.glob("*.jsonl")) + [HERE / "usage_log.jsonl"]:
        if f.exists():
            for line in open(f):
                try:
                    total += float(json.loads(line).get("cost_usd") or 0)
                except Exception:
                    pass
    summary["total_t2_spend_usd_incl_mwe"] = round(total, 6)
    json.dump(summary, open(RAW_T2 / "t2_summary.json", "w"), indent=1)
    print(json.dumps(summary, indent=1))


if len(sys.argv) >= 2 and sys.argv[1] == "set-ids":
    cmd_set_ids(sys.argv[2:]); sys.exit(0)
if len(sys.argv) >= 2 and sys.argv[1] == "repair":
    cmd_repair(sys.argv[2] if len(sys.argv) > 2 else "google/gemini-3.1-flash-lite"); sys.exit(0)
if len(sys.argv) >= 2 and sys.argv[1] == "summarize":
    cmd_summarize(sys.argv[2] if len(sys.argv) > 2 else "google/gemini-3.1-flash-lite"); sys.exit(0)

from bfcl_eval.constants.model_config import MODEL_CONFIG_MAPPING, ModelConfig  # noqa: E402
from openrouter_handler import OpenRouterHandler  # noqa: E402

for model_id, (in_price, out_price) in MODELS.items():
    for lay in LAYOUT_SUFFIXES:
        MODEL_CONFIG_MAPPING[registry_key(model_id, lay)] = ModelConfig(
            model_name=model_id,
            display_name=f"{model_id} via OpenRouter {lay.upper()} (FC)",
            url="https://openrouter.ai/models/" + model_id,
            org="OpenRouter",
            license="Proprietary",
            model_handler=OpenRouterHandler,
            input_price=in_price,
            output_price=out_price,
            is_fc_model=True,
            underscore_to_dot=True,
        )

from bfcl_eval.__main__ import cli  # noqa: E402

if __name__ == "__main__":
    cli()
