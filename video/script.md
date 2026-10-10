# Film narration (plain teaching register; numbers from results/analysis.json, main grid gemini-3.1-flash-lite)

p1. Every production agent is now built around one rule: never change the start of the prompt. Keep the system prompt and the tools first. Append every new observation at the end. Never reorder, never delete. The reason is money. Providers charge about one tenth of the price for input tokens they have already seen, and the discount only applies when the prompt starts with exactly the same bytes as last time.

p2. The rule has a side effect. Nothing is ever removed. When a value changes, the old value stays in the context next to the new one. So we asked a simple question. Does the layout that caching rewards cost accuracy, when the information in the context is held fixed?

p3. To answer it we built a small tool environment with three domains: a warehouse, a meeting calendar, and a support ticket queue. An agent runs scripted sessions of six to thirty tool calls. Some steps are questions it must answer from what it has already seen, with tools switched off. In a trap step, a superseded value is sitting in the context when the question arrives. In a neutral step, nothing competes.

p4. Traps come in two kinds. In an own update, the agent changed the value itself and the tool reply stated the new value. In an external update, someone else changed the record, and the agent only saw the new value as one row inside a listing it was asked to fetch.

p5. Every episode is replayed under four layouts that carry the same information. L1 is the cache-optimal layout: append only. L2 reorders the earlier blocks by relevance on every turn. L3 keeps the order but redacts, in place, every value that a later result replaced. L4 is L1 plus a short note on each turn that says which earlier observations are current, without stating any value.

p6. First result, on Gemini 3.1 Flash-Lite over one hundred and forty-four episodes. Own updates never fail: all four layouts score one hundred percent. Neutral steps never fail either. The whole effect lives in external updates. There, the cache-optimal layout answers correctly sixty-five percent of the time. The pruned layout answers correctly ninety-six percent of the time. Reordering barely helps: seventy percent. The note recovers about a quarter of the gap: seventy-three percent.

p7. We read forty of the wrong answers one by one. Thirty-four are the same mistake. The agent answers with its own earlier write, and ignores the listing row that overtook it.

p8. Second result, the bill. Per episode the append-only layout is the cheapest, at one point zero five cents, and the pruned layout costs ten percent more. But per correct episode the pruned layout is the cheapest: one point two two cents against one point five two. We then repriced every cached token, from free to full price. At every price, pruning stays the cheapest per correct answer. The accuracy it buys is worth more than the cache it breaks.

p9. We repeated the comparison on an older and a newer Gemini model. On Gemini 2.5 Flash, the append-only layout gets forty percent of external updates right, and pruning gets eighty-four. On Gemini 3.6 Flash, the numbers are eighty and one hundred. Newer models are confused less often. None of them is cured. And on every model, pruning is the cheapest layout per correct answer.

p10. So, for anyone who followed the caching guidance: the discipline is free when the world only changes through your own agent. It is not free when the world changes behind it. Then a stale copy of a value in the prompt costs a third of the answers, and the cheapest fix is to overwrite it, even if that breaks the cache.

p11. Cheap but confused. Keep the cache. Do not keep the stale value.
