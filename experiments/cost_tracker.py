"""Spend tracker with hard stop. Every OpenRouter call logs the exact `usage.cost` it returned.
State: results/spend.json. Raises CostCapExceeded once the total crosses HARD_STOP_USD ($24:
the key is shared with a sibling project; see INSTRUCTIONS.md section 4).
Safe for several processes at once: an fcntl lock on results/spend.lock guards read-modify-write,
and the JSON is written to a temp file and renamed into place (atomic on POSIX)."""

import fcntl
import json
import os
import threading
import time

HARD_STOP_USD = 24.00
_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
STATE = os.path.join(_DIR, "spend.json")
LOCK = os.path.join(_DIR, "spend.lock")
_lock = threading.Lock()


class CostCapExceeded(RuntimeError):
    pass


def _load():
    for attempt in range(5):
        try:
            if os.path.exists(STATE):
                return json.load(open(STATE))
            return {"total_usd": 0.0, "by_model": {}, "n_calls": 0, "updated": None}
        except json.JSONDecodeError:
            time.sleep(0.2 * (attempt + 1))
    raise RuntimeError("spend.json unreadable after retries")


def _save(s):
    tmp = STATE + f".tmp.{os.getpid()}"
    with open(tmp, "w") as fh:
        json.dump(s, fh, indent=1)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, STATE)


def log_call(model, cost_usd, tag=None):
    os.makedirs(_DIR, exist_ok=True)
    with _lock, open(LOCK, "a") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        try:
            s = _load()
            s["total_usd"] = round(s["total_usd"] + float(cost_usd), 8)
            key = model if tag is None else f"{model}|{tag}"
            s["by_model"][key] = round(s["by_model"].get(key, 0.0) + float(cost_usd), 8)
            s["n_calls"] += 1
            s["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            _save(s)
        finally:
            fcntl.flock(lk, fcntl.LOCK_UN)
    if s["total_usd"] >= HARD_STOP_USD:
        raise CostCapExceeded(f"spend {s['total_usd']:.2f} >= {HARD_STOP_USD}")
    return s["total_usd"]


def total():
    return _load()["total_usd"]
