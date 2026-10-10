# T2 external arm: BFCL multi-turn through OpenRouter with a custom layout hook

Date: 2026-10-10 (MWE), updated 2026-10-10 18:15 after the full 50 x 3 run. Verdict: **BFCL works.** The official `bfcl-eval` harness runs end to end
against OpenRouter (`google/gemini-3.1-flash-lite`, temperature 0) with a per-call message
re-serialisation hook, produces the official score file, and returns per-call `usage.cost` and
`prompt_tokens_details.cached_tokens`. Two-task MWE spend: **$0.0302** (59 calls). tau2-bench
was not needed and was not checked.

## 1. Environment

- venv: `experiments/bfcl_env` (python 3.13.12), `pip install bfcl-eval` -> **bfcl-eval 2026.3.23**
  (openai SDK 3.28.0). One undeclared dependency had to be added: `pip install soundfile`
  (`qwen_agent`, imported unconditionally by `constants/model_config.py`, needs it).
- Package root: `experiments/bfcl_env/lib/python3.13/site-packages/bfcl_eval/` (called `PKG` below).
- The package has renamed the datasets to **`BFCL_v4_*`**; the multi-turn categories are the
  same `multi_turn_base` / `multi_turn_long_context` tasks as v3 (ids `multi_turn_base_0..199`).
- Our files (nothing under `experiments/` was modified except these two new directories):
  - `experiments/t2_bfcl/openrouter_handler.py`: handler subclass (OpenRouter client, layout hook, usage log)
  - `experiments/t2_bfcl/layouts_bfcl.py`: layout hook registry (`L1` identity implemented)
  - `experiments/t2_bfcl/run_bfcl.py`: wrapper around the official CLI (registers the model, pins project root)
  - `experiments/t2_bfcl/bfcl_root/`: `result/`, `score/`, `test_case_ids_to_generate.json` (BFCL_PROJECT_ROOT)
  - `experiments/t2_bfcl/usage_log.jsonl`: per-call OpenRouter usage from the MWE

## 2. Datasets and environments

| File (under `PKG/data/`) | Tasks | Mean user turns (min/max) | Mean ground-truth calls / task |
|---|---|---|---|
| `BFCL_v4_multi_turn_base.json` + `possible_answer/BFCL_v4_multi_turn_base.json` | 200 | 3.67 (1/7) | 5.71 |
| `BFCL_v4_multi_turn_long_context.json` + `possible_answer/...long_context.json` | 200 | 3.67 (1/7) | 5.71 |

The two categories share the same 200 conversations and ground truths; `long_context` differs
only in environment state: `_load_scenario(..., long_context=True)` pads the instances (extra
files/directories in `GorillaFileSystem._populate_directory`, extra bookings/credit cards in
`TravelAPI`, longer lists in `VehicleControlAPI`, from `func_source_code/long_context.py`), so
tool results are much longer. Involved classes in `multi_turn_base` (a task uses 1-2):
GorillaFileSystem 50, TradingBot 50, TravelAPI 50, VehicleControlAPI 50, MessageAPI 40,
TwitterAPI 39, TicketAPI 31, MathAPI 25. Class source: `PKG/eval_checker/multi_turn_eval/func_source_code/*.py`;
tool schemas: `PKG/data/multi_turn_func_doc/*.json` (18 GFS, 20 TradingBot, 18 Travel, 22 Vehicle,
10 Message, 14 Posting(Twitter), 9 Ticket, 17 Math functions). The task entry has keys
`id, question (list of turns, each a list of messages), initial_config, path, involved_classes,
excluded_function`; `utils.populate_test_cases_with_predefined_functions` attaches `function`
(all tools of all involved classes; 32 tools for base_0). There is **no system prompt** in FC
mode: turn 0 is a bare user message, so the cacheable prefix is the tool block only.

Ground truth (`possible_answer`): `ground_truth` is a list over user turns, each a list of Python
call strings, e.g. turn 0 of base_0: `["cd(folder='document')", "mkdir(dir_name='temp')",
"mv(source='final_report.pdf', destination='temp')"]`. An empty list for a turn means "the model
should not call anything" (used by miss_func/miss_param, not by base/long_context).

## 3. How scoring works (`PKG/eval_checker/multi_turn_eval/multi_turn_checker.py`)

`multi_turn_checker(model_result_decoded, ground_truth, test_entry, category, model_name)`,
called per task from `eval_runner._evaluate_single_multi_turn_entry`:

1. Pre-checks: if the model result is not a list -> `multi_turn:inference_error`; if the number
   of model turns != number of ground-truth turns (the harness broke out early at the 20-step cap)
   -> `multi_turn:force_terminated` (whole task fails).
2. For each turn, the model's decoded call strings (all steps of that turn, in order) are executed
   with `multi_turn_utils.execute_multi_turn_func_call` on a **model** set of class instances, and
   the ground-truth strings on a **ground-truth** set. Instances persist across turns inside
   `multi_turn_utils` module globals keyed `f"{model_name}_eval_{test_id}_{class}_instance"`;
   `_load_scenario(initial_config[class], long_context)` seeds them at turn 0. Calls are run via
   `eval()` after `_process_method_calls` prefixes each function name with its instance.
3. If ground truth for the turn is non-empty and the model produced no executable call ->
   `multi_turn:empty_turn_model_response`.
4. **State-based check** `state_checker(model_instances, gt_instances)` -> `_compare_instances`:
   for every non-underscore attribute in `vars(gt_instance)`, `getattr(model) == getattr(gt)`
   (Python equality of the whole attribute, e.g. the file-system tree, order book, booking dicts).
   Any difference -> `multi_turn:instance_state_mismatch` with a `differences` dict.
5. **Response-based check** `response_checker(all_model_execution_results_so_far, gt_turn_results)`
   -> `_is_subsequence_unordered`: every ground-truth call's **return string** for this turn must
   appear (multiset containment, order ignored) among the return strings of all model calls made
   in this and earlier turns. Missing -> `multi_turn:execution_response_mismatch`. This is what
   catches read-only queries (e.g. `grep`, `get_balance`) that leave no state behind.
6. `method_invoke_order_checker` exists but is commented out. A task is correct only if every
   turn passes both checks; accuracy = correct tasks / tasks.

Score file: `score/<model_dir>/multi_turn/BFCL_v4_<category>_score.json` (first line
`{"accuracy", "correct_count", "total_count"}`, then one record per failed task with `error`,
`prompt`, `model_result_decoded`, `possible_answer`, `inference_log`), plus `score/data_multi_turn.csv`
and `data_overall.csv`.

## 4. How inference runs for an OpenAI-compatible model

- `PKG/model_handler/base_handler.py::BaseHandler.inference_multi_turn_FC` (lines 95-392) is the
  loop, marked `@final`; `PKG/model_handler/api_inference/openai_completion.py::OpenAICompletionsHandler`
  is the chat-completions implementation (OpenAI itself now uses `openai_response.py`).
- Per task: `_pre_query_processing_FC(inference_data, test_entry)` creates `inference_data["message"] = []`;
  `_compile_tools` converts `test_entry["function"]` with `convert_to_tool(..., GORILLA_TO_OPENAPI,
  OPENAI_COMPLETIONS)` into `inference_data["tools"]`. Then for each user turn:
  `add_first_turn_message_FC` / `_add_next_turn_user_message_FC` extend the list with the user
  message(s); the inner step loop (max `MAXIMUM_STEP_LIMIT = 20`, `constants/default_prompts.py`)
  calls `_query_FC(inference_data)` -> `self.client.chat.completions.create(messages=inference_data["message"],
  model, temperature, tools, store=False)`, `_parse_query_response_FC` extracts
  `[{name: arguments_json}, ...]` + `tool_call_ids` + `usage.prompt_tokens/completion_tokens`,
  `_add_assistant_message_FC` appends the raw `choices[0].message` object, `decode_execute`
  turns the tool calls into call strings, `execute_multi_turn_func_call` runs them on the live
  instances (same global-keyed instances as the checker, suffix `_instance` without `_eval`), and
  `_add_execution_results_FC` appends one `{"role": "tool", "content": result_str, "tool_call_id"}`
  per call. A text-only reply (no tool_calls) makes `decode_execute` raise -> "Failed to decode the
  model response. Proceed to next turn." -> that is the normal end-of-turn path.
- `inference_data["message"]` is therefore the running, append-only OpenAI message list for the
  whole episode; it is never rewritten by the harness and is only read inside `_query_FC`.
- Result file: `result/<registry_name with / -> _>/multi_turn/BFCL_v4_<category>_result.json`, one
  JSON line per task with `result` (per turn, per step: list of `{name: args}` or the text),
  `input_token_count`, `output_token_count`, `latency` (per turn, per step), `inference_log`
  (with `state_info` snapshots after every turn; `inference_input` entries when `--include-input-log`).

### The hook (what we did)
`OpenRouterHandler._query_FC` (in `openrouter_handler.py`) replaces the parent's `_query_FC`:
`sent = self.layout_hook(copy.deepcopy(inference_data["message"]), inference_data)` right
before `chat.completions.create(messages=sent, ...)`. The harness's own history, the environment
execution, the result file and the checker never see the re-serialised list; only the API does.
`inference_data` also carries `_test_id`, `_call_idx`, `_session_id` (set in our
`_pre_query_processing_FC`) so a hook can key per-episode state (e.g. which tool results are
superseded). The hook is selected by the `T2_LAYOUT` env var from `layouts_bfcl.LAYOUTS`.
We also store the assistant message in the history as a plain dict (`role/content/tool_calls`),
not the SDK object, so OpenRouter/Gemini extras (`reasoning`, `annotations`, `refusal`) are not
echoed back, and so hooks operate on plain JSON.

### Pointing at OpenRouter
The stock handler reads `OPENAI_API_KEY`, `OPENAI_BASE_URL`, `OPENAI_DEFAULT_HEADERS` from the
environment (`_build_client_kwargs`), so `OPENAI_BASE_URL=https://openrouter.ai/api/v1
OPENAI_API_KEY=<openrouter key>` would work for the transport, BUT (a) the model must be a key of
`MODEL_CONFIG_MAPPING` (`constants/model_config.py`), which has no OpenRouter ids, (b) the stock
`_query_FC` sends no `extra_body`, so OpenRouter returns no `usage.cost`, and (c) the stock
handler passes `store=False`. So we subclassed: our `__init__` builds
`OpenAI(base_url="https://openrouter.ai/api/v1", api_key=<OPENROUTER_API_KEY from project .env>)`
and every request carries `extra_body={"usage": {"include": True}, "reasoning": {"effort":
"minimal"}, "session_id": <per-task id>}` (same options as `experiments/runner.py`), `max_tokens=1200`.
The wrapper `run_bfcl.py` inserts `ModelConfig(... model_handler=OpenRouterHandler, is_fc_model=True,
input_price=0.25, output_price=1.5)` into `MODEL_CONFIG_MAPPING` under the key
`openrouter/google/gemini-3.1-flash-lite` before invoking the official `cli()`. The key must not
contain underscores: `eval_runner.runner` recovers the model name from the result directory with
`.replace("_", "/")`. `BFCL_PROJECT_ROOT` (read at import in `constants/eval_config.py`) is set to
`experiments/t2_bfcl/bfcl_root` so `result/`, `score/`, `.file_locks/`, `test_case_ids_to_generate.json`
and the (unused) `.env` all live there.

### Capturing usage
`_log_usage` reads `resp.usage.prompt_tokens`, `resp.usage.prompt_tokens_details.cached_tokens`,
`resp.usage.completion_tokens`, `resp.usage.completion_tokens_details.reasoning_tokens`,
`resp.usage.cost` (extra field; the openai SDK models allow extras, `getattr` works),
`resp.provider`, `resp.cache_discount`, `finish_reason`, latency, and appends one JSON line per
call to `usage_log.jsonl`; the billed cost is also pushed into the project tracker
(`experiments/cost_tracker.py`, tag `T2-bfcl`, visible in `results/spend.json`).

## 5. Commands that worked (from `experiments/t2_bfcl/`, venv python)

```
../bfcl_env/bin/pip install bfcl-eval soundfile
../bfcl_env/bin/python run_bfcl.py set-ids multi_turn_base=0,1
../bfcl_env/bin/python run_bfcl.py generate --model openrouter/google/gemini-3.1-flash-lite --run-ids --temperature 0 --include-input-log
../bfcl_env/bin/python run_bfcl.py evaluate --model openrouter/google/gemini-3.1-flash-lite --test-category multi_turn_base --partial-eval
```
`--run-ids` reads `bfcl_root/test_case_ids_to_generate.json` (the package's
`test_case_ids_to_generate.json.example` format: `{"multi_turn_base": ["multi_turn_base_0", ...]}`)
and ignores `--test-category`; existing ids in the result file are skipped unless
`--allow-overwrite` (with `--run-ids` it updates those entries in place). `evaluate --partial-eval`
scores only the ids present in the result file. `--num-threads N` parallelises across tasks
(instances are keyed per task id, so this is safe); default 1 for API models.

## 6. MWE output

Evaluator: `Accuracy: 50.00%`; `bfcl_root/score/openrouter_google_gemini-3.1-flash-lite/multi_turn/BFCL_v4_multi_turn_base_score.json`:
```
{"accuracy": 0.5, "correct_count": 1, "total_count": 2}
multi_turn_base_1  multi_turn:force_terminated  (model turns 2 != ground-truth turns 4)
```
`data_multi_turn.csv`: `google/gemini-3.1-flash-lite via OpenRouter (FC), Multi Turn Overall 12.50%, Base 50.00%`
(the overall figure averages the three unrun sub-categories as 0; ignore it).

- base_0 (GorillaFileSystem + TwitterAPI, 32 tools, 4 user turns): passed. 29 API calls
  (steps per turn 17/4/2/6), 108,676 prompt tokens total, $0.01379.
- base_1 (GorillaFileSystem, 18 tools, 4 user turns): 30 API calls; the model looped on `ls(a=true)`
  in turn 1 until the 20-step cap, so the harness stopped after 2 turns -> `force_terminated`. $0.01644.

Per-call usage (`usage_log.jsonl`, provider `Google`, finish_reason tool_calls/stop, reasoning 0):
```
base_0 call 0  msgs 1  prompt 3386 cached    0  out  8  cost $0.0008585
base_0 call 1  msgs 3  prompt 3403 cached    0  out 14  cost $0.0008718
base_0 call 2  msgs 5  prompt 3421 cached    0  out  8  cost $0.0008673
base_0 call 3  msgs 7  prompt 3446 cached 3098  out 16  cost $0.0001885   <- first hit, 90% of prompt
base_0 call 4  msgs 9  prompt 3462 cached 3090  out 30  cost $0.0002153
...   calls 5-27: cached 3007-3084 every call (prefix = tool block), cost $0.00021-0.00042
base_0 call 28 msgs 57 prompt 4246 cached    0  out 120 cost $0.0012415   <- a miss on the last call
base_1 calls 0-29: prompt 2175 -> 2798, cached 0 on every call, cost $0.00056-0.00072
```
Billed cost reconciles with the price list: uncached 3386 x $0.25/M + 8 x $1.5/M = $0.000859
(billed $0.0008585); cached call 3: 348 x $0.25/M + 3098 x $0.025/M + 16 x $1.5/M = $0.000189
(billed $0.00018845). Cache reads are billed at 0.1x input on this route. Total MWE spend
**$0.03023** (59 calls), logged in `results/spend.json` under `google/gemini-3.1-flash-lite|T2-bfcl`.

Two facts that matter for the design: (1) Gemini implicit caching only hit when the prompt was
>= ~3.4k tokens (base_0), never at 2.2-2.8k tokens (base_1), and took two calls to warm; the
cached span is the ~3.0k-token tool block, which is the entire stable prefix because FC mode has
no system prompt. (2) Hits were 3,007-3,098 tokens even though the message list grew from 7 to 55
messages: everything after the tool block is re-read at full price under L1 too, so on BFCL the
cache saving of L1 vs L2 is bounded by the tool-block fraction of the prompt (~75-90% here).

## 7. Pre-build recommendation (superseded by section 8, kept for the record)

Scope: `multi_turn_base` and `multi_turn_long_context`, a fixed 50-100-task subset (same ids for
every layout and model), one process per (model, layout), `--run-ids`, `--num-threads 2-4`.

1. **Stable prefix >= 4,500 tokens for every task.** Override `add_first_turn_message_FC` to insert
   a fixed system message (BFCL-neutral operating instructions + the involved classes' descriptions,
   padded to ~2k tokens, identical across layouts) before the first user message. This clears the
   implicit-cache minimum for every task (base_1's 18-tool prompt was 2.2k tokens and never cached)
   and mirrors T1. Keep the tool list untouched (BFCL's checker is indifferent to tool ordering;
   `excluded_function` is already applied by the loader).
2. **Separate registry keys per layout** so result/score directories never collide:
   `openrouter/google/gemini-3.1-flash-lite/L1` ... `/L4` (no underscores). `run_bfcl.py` derives
   `T2_LAYOUT` from the key suffix. The environment instances live in `multi_turn_utils` globals keyed by
   `model_name` (the OpenRouter id, same for all layouts) + task id, so **never run two layouts of the
   same model in one process**; one process per layout is also what keeps `session_id` routing clean.
3. **Hooks operate only on the sent copy** (`layouts_bfcl.py`), using the plain-dict history:
   - **L1 (cache-optimal)**: identity. Already implemented and measured.
   - **L2 (relevance-reordered)**: keep system + first user message in place; group every
     (assistant tool_call, tool result) pair into blocks; re-sort the blocks of *previous* turns by a
     deterministic relevance score to the current user turn (BM25 over the current user message vs.
     tool name + arguments + result text; `rank_bm25` is already installed by bfcl-eval), most relevant
     last, directly before the current turn's messages; keep the current turn's steps in arrival order.
     Tool-call ids stay paired, so the OpenAI/Gemini "tool result must follow its call" constraint holds.
     Content identical to L1 (same blocks, different order); prefix breaks every call (expected: cached_tokens
     collapses to the tool block only when the order happens to be unchanged, otherwise 0 after the prefix).
   - **L3 (pruned)**: replace the `content` of superseded tool results with
     `"[result superseded by call N]"` and drop stale ones. Supersession is defined per class from the
     tool schemas in `multi_turn_func_doc` (read-type tools whose later call with the same arguments,
     or a write-type tool on the same object, returned a newer value: `ls`/`cat`/`pwd` after `cd`/`mv`/`rm`;
     `get_account_info`/`get_stock_info` after `place_order`/`cancel_order`; `get_flight_cost`/`get_budget_fiscal_year`
     after `book_flight`; `displayCarStatus` after `startEngine`/`lockDoors`, etc.). Keep a per-episode map in
     `inference_data` (hook receives it) so the rule is computed once per call and logged.
   - **L4 (hybrid)**: identity plus one appended user-role block ~150 tokens after the newest message:
     restated goal (current user turn), current environment facts derived from the tool results so far
     (cwd, last balances, bookings), and the list of call indices that are superseded (same rule as L3,
     but stated instead of applied). Appending keeps the prefix stable; expected cached_tokens tracks L1.
4. **Measurement**: `usage_log.jsonl` already has everything per call (prompt, cached, completion,
   reasoning, `usage.cost`, provider, latency, finish_reason, n_messages_sent, layout, test_id,
   call_idx). Derive per task: cache-read fraction, USD per task, calls per task; join with the
   score file by `id` for USD per correct task. Set `T2_USAGE_LOG` per (model, layout) run.
5. **Budget**: flash-lite cost $0.014-0.016 per task per layout at 29-30 calls (the 20-step cap bounds
   the worst case at ~$0.05/task). 100 tasks x 4 layouts ~ $6 on flash-lite; long_context tool results
   are several times longer, so budget ~$10-12 for 2 x 100 tasks x 4 layouts on one model, or cut to 50
   tasks per category. A second model family is blocked by the workspace guardrail (only `google/*`
   passes; see MILESTONES.md).
6. **Checker caveats to report**: a task fails as a whole on the first bad turn; `force_terminated`
   (20-step loop) is a frequent failure mode for flash-lite and should be reported separately from
   state/response mismatches; `max_tokens=1200` is ours (the stock handler sets none).

## 8. FINAL DESIGN AS BUILT (coordinator decision, 2026-10-10)

Files: `layouts_bfcl.py` (hooks), `system_prompt_t2.py` (fixed system message), `openrouter_handler.py`
(transport, hook application, logging, spend stop), `run_bfcl.py` (CLI wrapper, per-layout registry
keys, `set-ids`, `summarize`), `run_full.sh` (the full run driver), `run_full.log` (its output).
The MWE result/score directories of section 6 were moved to `mwe_archive/` (their unsuffixed
registry key is no longer registered and broke the evaluator's leaderboard aggregation).

**Layouts** (applied to a deepcopy of the running message list right before every API call; the
harness's history, the environment and the checker never see the re-serialised list). A block is
(user message, assistant tool-call message(s), tool-result message(s)) up to the next user message;
the fixed system message is always first.
- L1: identity (append-only).
- L3 (practitioner pruner, observation masking by age): the `content` of every tool-result message
  older than the most recent 2 user turns is replaced by `"[tool result from an earlier turn omitted]"`;
  assistant tool_call messages stay intact so ids pair. Nothing is masked in turns 1-2; from turn 3 on,
  the masked set changes only at turn boundaries, so the cached prefix breaks once per turn and
  re-warms on the intra-turn steps (observed cached fraction 0.82-0.84 on the validation tasks).
- L4: L1 unchanged + a pointer-only session note prepended to EVERY user message text (v2, persistent;
  v1 decorated only the newest user message and is archived, see section 9):
  `[Session note before turn N] Goal so far: <first user message, 300 chars>. Current request: <newest
  user message>. Earlier tool calls in this session: step k: <name>(<60 chars of args>) ... (last 25,
  computed from the messages BEFORE that user message, which never change later, so every note is
  byte-stable for the rest of the episode and the layout is append-only; unit test in the build log).
  Rule: results of the most recent calls about the same object are current; earlier ones may be stale.
  [End of note]`. Observed 830-940 chars (~230 tokens).
- L2 not run on T2 (budget).

**Fixed system message**: `system_prompt_t2.SYSTEM_PROMPT`, 12,673 chars, 2,525 cl100k tokens,
~2,570 Gemini tokens, neutral operating guidance for a tool-using assistant (functions, errors,
concise answers, no invented results, latest state wins); identical bytes for all layouts. Sized above
the requested ~2,000 tokens because the smallest selected tool block (18 GorillaFileSystem tools, 10
tasks per category) is 2,175 Gemini tokens, and 2,000 would have left those tasks under 4,500.
Turn-1 prompt on the validation tasks: 5,952 tokens (L1/L3) and 6,059 (L4) for base_0 / long_context_0
(32 tools). The minimum turn-1 prompt over all 50 tasks is reported in `t2_summary.json`
(`min_turn1_prompt_tokens`).

**Tasks** (deterministic, 50): even ids 0..48 of each category:
`multi_turn_base_{0,2,4,6,8,10,12,14,16,18,20,22,24,26,28,30,32,34,36,38,40,42,44,46,48}` and `multi_turn_long_context_{0,2,4,6,8,10,12,14,16,18,20,22,24,26,28,30,32,34,36,38,40,42,44,46,48}`
(25 + 25). Written to `bfcl_root/test_case_ids_to_generate.json` by `run_bfcl.py set-ids`.

**Registry keys / process layout**: `openrouter/google/gemini-3.1-flash-lite-l1`, `-l3`, `-l4`
(underscore-free; layout parsed from the suffix). One layout per process, layouts sequential,
`--num-threads 3` across tasks within a layout (environment instances are keyed per task id).
Temperature 0, `reasoning.effort=minimal`, `max_tokens=1200`, `session_id` per task, 20-step cap as
the harness defines (`MAXIMUM_STEP_LIMIT`), retries with exponential backoff on 429/5xx/connection
errors (the key is shared with the concurrent T1 run).

**Logging**: per call one JSON line in `results/raw/t2/<LAYOUT>_google_gemini-3.1-flash-lite.jsonl`
(task_id, category, layout, turn_idx, call_idx, n_messages_sent, prompt_tokens, cached_tokens,
cache_write_tokens, completion_tokens, reasoning_tokens, cost_usd, cache_discount, provider,
finish_reason, native_finish_reason, latency_s, layout_stat). Every billed `usage.cost` also goes to
`experiments/cost_tracker.py` (tag `T2-<layout>`, $24 hard stop). A T2-specific stop at $5.50
(`T2_SPEND_CAP_USD`, summed over all T2 logs incl. the MWE) exits the process. After evaluation,
`run_bfcl.py summarize` writes `results/raw/t2/scores_<LAYOUT>_google_gemini-3.1-flash-lite.json`
(per task: category, pass, error_type, cost, prompt/cached/completion tokens, calls, cached_fraction,
turn1_prompt_tokens) and `results/raw/t2/t2_summary.json` (per layout: accuracy per category, mean cost
per task, mean cached fraction, mean calls, error-type counts, total cost; plus total T2 spend).

**Commands** (from `experiments/t2_bfcl/`):
```
../bfcl_env/bin/python run_bfcl.py set-ids multi_turn_base=0,2,4,6,8,10,12,14,16,18,20,22,24,26,28,30,32,34,36,38,40,42,44,46,48 multi_turn_long_context=0,2,4,6,8,10,12,14,16,18,20,22,24,26,28,30,32,34,36,38,40,42,44,46,48
for L in l1 l3 l4; do ../bfcl_env/bin/python run_bfcl.py generate --model openrouter/google/gemini-3.1-flash-lite-$L --run-ids --temperature 0 --num-threads 3; done
for L in l1 l3 l4; do ../bfcl_env/bin/python run_bfcl.py evaluate --model openrouter/google/gemini-3.1-flash-lite-$L --test-category multi_turn --partial-eval; done
../bfcl_env/bin/python run_bfcl.py summarize google/gemini-3.1-flash-lite      # == ./run_full.sh
```
Validation (2 tasks per layout, `T2_DUMP=1`, serialised final contexts in `results/raw/t2/debug/`):
base_0 and long_context_0 passed under all three layouts; L1 $0.0099/$0.0101 per task, cached
fraction 0.78/0.83; L3 $0.0098/$0.0117, 0.82/0.84 (10 and 9 results masked at the final call);
L4 $0.0101/$0.0097, 0.77/0.81. Validation spend $0.061. These two tasks are part of the 50 and were
not regenerated.

## 9. RESULTS (google/gemini-3.1-flash-lite via OpenRouter, 50 tasks x L1/L3/L4, 2026-10-10)

Source of every number: `results/raw/t2/t2_summary.json` and `results/raw/t2/scores_<L>_google_gemini-3.1-flash-lite.json`
(per task), built by `run_bfcl.py summarize` from the official score files and the per-call logs. The
minimum turn-1 prompt over all 50 tasks is 4,730 tokens (L1/L3; 18-tool tasks) and 4,821 (L4), so the
stable prefix cleared 4,500 for every task.

| Layout | base acc (n=25) | long_context acc (n=25) | mean USD/task | mean cached fraction | mean calls/task | USD per correct task | total USD (final attempts) |
|---|---|---|---|---|---|---|---|
| L1 append-only | 0.44 | 0.44 | $0.00926 | 0.785 | 19.4 | $0.0210 | $0.463 |
| L3 mask-by-age | 0.44 | 0.48 | $0.00836 | 0.780 | 17.3 | $0.0182 | $0.418 |
| L4 v2 persistent note | 0.44 | 0.40 | $0.00920 | 0.796 | 18.4 | $0.0219 | $0.460 |
| (L4 v1, newest-only note, archived) | 0.48 | 0.44 | $0.01038 | 0.745 | 18.9 | $0.0226 | $0.519 |

Paired per-task contrasts (same 50 tasks): L1 vs L3: both pass 22, only L1 0, only L3 1, neither 27.
L1 vs L4 v2: both 20, only L1 2, only L4 1, neither 27. L3 vs L4 v2: both 20, only L3 3, only L4 1, neither 26. (L1 vs L4 v1: both 20, only L1 2, only L4 3, neither 25.)
20 tasks pass under all three layouts (L1/L3/L4 v2) and 26 fail under all three; the layout moves at most 3 of 50 tasks in either direction, which is inside the repeat-call noise seen in T1. Error types (L1 base /
long_context): force_terminated 5/4 (20-step loop), instance_state_mismatch 7/8, execution_response_mismatch 2/2;
L3: 6/3, 6/7, 2/3. Failures are dominated by state mismatches and step-cap loops, not by stale reads.

Cache structure (per-call logs): L1 94% of calls had a cache hit; at the first call of each turn >= 2 the hit
rate was 0.98 with a mean cached fraction 0.83. L3 is almost identical (95%; 1.00 / 0.80): the mask set only
changes at turn boundaries, and Gemini's implicit cache re-warms on the next intra-turn step, so masking by age
costs almost no cache reads on this provider; its saving comes from shorter prompts (107k vs 123k prompt tokens
per task) and fewer calls. L4 v1 (newest-only note) broke the prefix at every turn boundary (first-call hit rate
0.67, cached fraction 0.51) because removing the previous turn's note rewrote earlier bytes; this is the reason
for the v2 rerun. L4 v2 (persistent notes) restores the append-only profile: 95% of calls hit, first call of each turn >= 2 hit rate 0.99, cached fraction 0.82, mean cached fraction per task 0.796 (L1 0.785), with the same mean prompt tokens per task as L1 (122.7k vs 122.7k) because the ~230-token notes replace nothing and the model made slightly fewer calls. L4 v2 error types (base / long_context): force_terminated 6/3, instance_state_mismatch 7/9, execution_response_mismatch 1/3.

Spend: full-run final attempts L1 $0.463 + L3 $0.418 + L4 v1 $0.519 + L4 v2 $0.460; aborted attempts (first
driver attempt, see below) $0.067; validation + MWE $0.091. **Total T2 spend: $1.957** (sum of every logged
`usage.cost`: `t2_summary.json` reports $1.438 excluding the archived v1 log, plus v1 $0.519; `results/spend.json`
tags `T2-*` sum to $1.930, $0.026 lower because increments were lost while the tracker file was corrupted). Project total after T2: see `results/spend.json`.

### Incidents
1. **spend.json race (fixed by the coordinator).** `experiments/cost_tracker.py` rewrote `results/spend.json`
   with an unlocked `open(..., "w")`; my per-call tracker writes and the concurrent T1 runner interleaved,
   leaving a 739-byte valid JSON plus one trailing byte. `json.load` then raised inside my `_log_usage`,
   which the harness recorded as an inference error for 29 L1 and 8 L3 tasks (attempt 1, log
   `run_full_attempt1.log`), and it also broke the T1 runner's tracker calls. I repaired the file once
   (valid prefix, atomic replace) before the coordinator replaced the tracker with an fcntl-locked,
   atomic version; my handler now batches tracker writes to one per episode (`inference` wrapper) and
   retries/spills to `results/raw/t2/spend_unlogged.jsonl` (never needed). `run_bfcl.py repair` dropped the
   error entries and the resumed run (`run_full.log`) regenerated exactly those tasks; the aborted attempts
   are excluded from per-task numbers via `episode_uid` and reported as `aborted_attempts_cost_usd`.
2. **L4 v1 was not append-only.** See above; archived under `results/raw/t2/L4v1-nonpersistent/`
   (log, per-task scores, final-context dumps, summary) and `mwe_archive/L4v1-nonpersistent/` (result and
   score dirs). L4 v2 (`layouts_bfcl.l4_session_note`, persistent notes) was rerun on the same 50 tasks
   (`run_l4v2.sh`, `run_l4v2.log`).
3. No 429s or 5xx retries were triggered in any attempt; no spend-cap stop; no task hit a provider error.
