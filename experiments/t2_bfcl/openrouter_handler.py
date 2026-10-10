"""BFCL handler for the T2 arm: OpenRouter transport + per-call layout hook + usage logging.

Subclasses the official OpenAICompletionsHandler (bfcl_eval/model_handler/api_inference/
openai_completion.py). Differences from the parent:
  * client -> https://openrouter.ai/api/v1, OPENROUTER_API_KEY read from the project .env;
  * a fixed system message (system_prompt_t2.SYSTEM_PROMPT) is inserted before the first user
    message (add_first_turn_message_FC) so the stable prefix clears the implicit-cache minimum;
  * every request carries extra_body={"usage": {"include": True}, "reasoning": {"effort":
    "minimal"}, "session_id": <per-task id>}; temperature from the CLI; max_tokens=1200;
  * the message list is passed through layouts_bfcl.LAYOUTS[layout] on a deepcopy right before
    each call; the harness's own history is untouched;
  * assistant messages are stored in the history as plain dicts (role/content/tool_calls);
  * per-call usage -> results/raw/t2/<layout>_<model-slug>.jsonl and cost_tracker ($24 hard
    stop); a T2-specific stop at T2_SPEND_CAP_USD (default 5.50) exits the process;
  * retries on 429/5xx/connection errors with exponential backoff (the key is shared).
"""

import copy
import json
import os
import random
import re
import uuid
import sys
import time
from pathlib import Path

import openai
from openai import OpenAI

from bfcl_eval.constants.enums import ModelStyle
from bfcl_eval.model_handler.api_inference.openai_completion import OpenAICompletionsHandler
from bfcl_eval.model_handler.base_handler import BaseHandler

HERE = Path(__file__).resolve().parent
EXPERIMENTS = HERE.parent
PROJECT = EXPERIMENTS.parent
RAW_T2 = PROJECT / "results" / "raw" / "t2"
REASONING_EFFORT = os.environ.get("T2_REASONING", "minimal")  # same as experiments/runner.py
MAX_TOKENS = int(os.environ.get("T2_MAX_TOKENS", "1200"))
T2_SPEND_CAP_USD = float(os.environ.get("T2_SPEND_CAP_USD", "5.50"))
T2_DUMP = os.environ.get("T2_DUMP", "0") == "1"
MAX_ATTEMPTS = 8

sys.path.insert(0, str(HERE))
sys.path.insert(0, str(EXPERIMENTS))
from layouts_bfcl import LAYOUTS  # noqa: E402
from system_prompt_t2 import SYSTEM_PROMPT  # noqa: E402

try:
    import cost_tracker  # experiments/cost_tracker.py -> results/spend.json, $24 hard stop
except Exception:  # pragma: no cover
    cost_tracker = None


def load_openrouter_key() -> str:
    env_path = PROJECT / ".env"
    for line in env_path.read_text().splitlines():
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError(f"OPENROUTER_API_KEY not found in {env_path}")


def t2_spend_so_far() -> float:
    """Sum of usage.cost over every T2 log (full runs, validation and the MWE)."""
    total = 0.0
    files = list(RAW_T2.glob("*.jsonl")) + [HERE / "usage_log.jsonl"]
    for f in files:
        if not f.exists():
            continue
        with open(f) as fh:
            for line in fh:
                try:
                    total += float(json.loads(line).get("cost_usd") or 0.0)
                except Exception:
                    pass
    return total


class OpenRouterHandler(OpenAICompletionsHandler):
    def __init__(self, model_name, temperature, registry_name, is_fc_model, **kwargs) -> None:
        BaseHandler.__init__(self, model_name, temperature, registry_name, is_fc_model, **kwargs)
        self.model_style = ModelStyle.OPENAI_COMPLETIONS
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=load_openrouter_key(),
            default_headers={
                "HTTP-Referer": "https://github.com/Abraar237/cache-layout-cost",
                "X-Title": "cache-layout-cost-T2",
            },
            max_retries=0,  # we do our own backoff
            timeout=180,
        )
        # layout from the registry key suffix (…-l1 / -l3 / -l4), else T2_LAYOUT, else L1
        m = re.search(r"-(l\d)$", registry_name)
        self.layout_name = m.group(1).upper() if m else os.environ.get("T2_LAYOUT", "L1")
        self.layout_hook = LAYOUTS[self.layout_name]
        self.model_slug = model_name.replace("/", "_")
        self._pending_cost = {}
        import threading
        self._pending_lock = threading.Lock()
        self.log_path = RAW_T2 / f"{self.layout_name}_{self.model_slug}.jsonl"
        RAW_T2.mkdir(parents=True, exist_ok=True)

    # ---- per-episode bookkeeping -------------------------------------------------
    def inference(self, test_entry: dict, include_input_log: bool, exclude_state_log: bool):
        """Wrap the harness entry point so the episode's billed cost reaches cost_tracker in one
        write per task (instead of one per call) even if the episode raises."""
        test_id = test_entry["id"]
        try:
            return super().inference(test_entry, include_input_log, exclude_state_log)
        finally:
            with self._pending_lock:
                cost = self._pending_cost.pop(test_id, 0.0)
            if cost:
                self._track_cost(cost)

    def _pre_query_processing_FC(self, inference_data: dict, test_entry: dict) -> dict:
        inference_data["message"] = []
        inference_data["_test_id"] = test_entry["id"]
        inference_data["_category"] = test_entry["id"].rsplit("_", 1)[0]
        inference_data["_call_idx"] = 0
        inference_data["_turn_idx"] = 0
        inference_data["_episode_uid"] = uuid.uuid4().hex[:12]  # one per inference attempt
        inference_data["_session_id"] = re.sub(
            r"[^A-Za-z0-9_-]", "_", f"{self.registry_dir_name}_{test_entry['id']}"
        )
        return inference_data

    def add_first_turn_message_FC(self, inference_data: dict, first_turn_message: list) -> dict:
        inference_data["message"].append({"role": "system", "content": SYSTEM_PROMPT})
        inference_data["message"].extend(first_turn_message)
        inference_data["_turn_idx"] = 0
        return inference_data

    def _add_next_turn_user_message_FC(self, inference_data: dict, user_message: list) -> dict:
        inference_data["message"].extend(user_message)
        inference_data["_turn_idx"] = inference_data.get("_turn_idx", 0) + 1
        return inference_data

    # ---- the API call ------------------------------------------------------------
    def generate_with_backoff(self, **kwargs):
        delay = 4.0
        for attempt in range(1, MAX_ATTEMPTS + 1):
            start = time.time()
            try:
                resp = self.client.chat.completions.create(**kwargs)
                return resp, time.time() - start
            except (openai.RateLimitError, openai.APIConnectionError, openai.APITimeoutError,
                    openai.InternalServerError) as e:
                err = e
            except openai.APIStatusError as e:
                if e.status_code in (408, 409, 425, 429, 500, 502, 503, 504, 529):
                    err = e
                else:
                    raise
            if attempt == MAX_ATTEMPTS:
                raise err
            sleep = min(90.0, delay * (2 ** (attempt - 1))) * (0.7 + 0.6 * random.random())
            print(f"[T2] attempt {attempt} failed ({type(err).__name__}); sleeping {sleep:.1f}s")
            time.sleep(sleep)

    def _query_FC(self, inference_data: dict):
        spent = t2_spend_so_far()
        if spent >= T2_SPEND_CAP_USD:
            print(f"[T2] SPEND CAP: T2 spend ${spent:.4f} >= ${T2_SPEND_CAP_USD}; exiting process.")
            sys.stdout.flush()
            time.sleep(3)  # let the writer thread flush completed tasks
            os._exit(3)

        history: list = inference_data["message"]
        tools = inference_data["tools"]
        inference_data.pop("_layout_stat", None)

        # THE HOOK: re-serialise the whole history per experimental condition, on a copy.
        sent = self.layout_hook(copy.deepcopy(history), inference_data)
        inference_data["inference_input_log"] = {"message": repr(sent), "tools": tools}

        kwargs = {
            "model": self.model_name,
            "messages": sent,
            "temperature": self.temperature,
            "max_tokens": MAX_TOKENS,
            "extra_body": {
                "usage": {"include": True},
                "reasoning": {"effort": REASONING_EFFORT},
                "session_id": inference_data.get("_session_id"),
            },
        }
        if len(tools) > 0:
            kwargs["tools"] = tools

        resp, latency = self.generate_with_backoff(**kwargs)
        self._log_usage(resp, latency, inference_data, sent)
        inference_data["_call_idx"] = inference_data.get("_call_idx", 0) + 1
        return resp, latency

    def _log_usage(self, resp, latency, inference_data, sent):
        u = resp.usage
        ptd = getattr(u, "prompt_tokens_details", None) if u is not None else None
        ctd = getattr(u, "completion_tokens_details", None) if u is not None else None
        cost = getattr(u, "cost", None) if u is not None else None
        choice = resp.choices[0] if resp.choices else None
        rec = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "task_id": inference_data.get("_test_id"),
            "category": inference_data.get("_category"),
            "layout": self.layout_name,
            "model": self.model_name,
            "episode_uid": inference_data.get("_episode_uid"),
            "turn_idx": inference_data.get("_turn_idx", 0),
            "call_idx": inference_data.get("_call_idx", 0),
            "n_messages_sent": len(sent),
            "prompt_tokens": getattr(u, "prompt_tokens", None) if u is not None else None,
            "cached_tokens": getattr(ptd, "cached_tokens", None) if ptd is not None else None,
            "cache_write_tokens": getattr(ptd, "cache_write_tokens", None) if ptd is not None else None,
            "completion_tokens": getattr(u, "completion_tokens", None) if u is not None else None,
            "reasoning_tokens": getattr(ctd, "reasoning_tokens", None) if ctd is not None else None,
            "cost_usd": cost,
            "cache_discount": getattr(resp, "cache_discount", None),
            "provider": getattr(resp, "provider", None),
            "resp_model": getattr(resp, "model", None),
            "finish_reason": getattr(choice, "finish_reason", None),
            "native_finish_reason": getattr(choice, "native_finish_reason", None),
            "latency_s": round(latency, 3),
            "layout_stat": inference_data.get("_layout_stat"),
        }
        with open(self.log_path, "a") as f:
            f.write(json.dumps(rec) + "\n")
        if cost is not None:
            # batched: flushed to cost_tracker once per episode (see inference) to minimise
            # concurrent rewrites of results/spend.json by this and the T1 process
            with self._pending_lock:
                self._pending_cost[inference_data.get("_test_id")] = (
                    self._pending_cost.get(inference_data.get("_test_id"), 0.0) + float(cost))
        if T2_DUMP:
            d = RAW_T2 / "debug"
            d.mkdir(exist_ok=True)
            with open(d / f"{self.layout_name}_{inference_data.get('_test_id')}_last_context.json", "w") as f:
                json.dump({"call_idx": rec["call_idx"], "turn_idx": rec["turn_idx"], "messages": sent}, f, indent=1)

    def _track_cost(self, cost):
        """cost_tracker.log_call reads/writes results/spend.json without cross-process locking;
        the concurrent T1 run rewrites it, so json.load can hit a half-written file. Retry, then
        spill to results/raw/t2/spend_unlogged.jsonl so no billed cost goes unaccounted. A
        CostCapExceeded from the tracker is re-raised (the $24 project hard stop)."""
        if cost_tracker is None:
            return
        last = None
        for _ in range(6):
            try:
                cost_tracker.log_call(self.model_name, cost, tag=f"T2-{self.layout_name}")
                return
            except cost_tracker.CostCapExceeded:
                raise
            except Exception as e:  # JSONDecodeError / transient IO race
                last = e
                time.sleep(0.05 + random.random() * 0.2)
        with open(RAW_T2 / "spend_unlogged.jsonl", "a") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "model": self.model_name,
                                "tag": f"T2-{self.layout_name}", "cost_usd": cost, "error": str(last)}) + "\n")

    # ---- keep the chat history provider-neutral ----------------------------------
    def _parse_query_response_FC(self, api_response):
        data = super()._parse_query_response_FC(api_response)
        msg = api_response.choices[0].message
        clean = {"role": "assistant", "content": msg.content}
        if getattr(msg, "tool_calls", None):
            clean["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
        data["model_responses_message_for_chat_history"] = clean
        reasoning = getattr(msg, "reasoning", None) or getattr(msg, "reasoning_content", None)
        if reasoning:
            data["reasoning_content"] = reasoning
        return data
