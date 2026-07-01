# Improvements Made

A log of changes already shipped, with the evidence/rationale behind each — the "what we did and
why" for the writeup/presentation. (Things still **to do** live in `IMPROVEMENTS.md`.)

---

## Eval harness & infrastructure

1. **Incremental, resumable runner.** Each example is written to `results_v{version}.jsonl` the
   moment it finishes (flushed); re-running skips completed examples and re-runs only failures.
   *Why:* a crash at example 22 used to lose the first 21 — wasteful given API cost.

2. **Multithreaded execution** (`max_workers`). Runs examples concurrently. *Why:* the serial run
   took ~4 min; latency is dominated by LLM calls, so concurrency is the real speedup lever.

3. **Wikipedia reliability: persistent cache + rate-limiter + proper User-Agent.** Multithreading
   tripped HTTP **429 (Too Many Requests)** — and backoff alone couldn't fix it because retrying a
   429 just adds load. Fixes, in order of leverage: (a) a **disk cache** of successful queries, so
   repeats — within a run, across retries, and across re-runs — never re-hit Wikipedia; (b) a
   global ~1 req/s **throttle** on request *starts* (LLM calls stay concurrent — only Wikipedia is
   throttled); (c) a **descriptive User-Agent** (Wikipedia throttles generic ones); (d) exponential
   backoff + `Retry-After`. *Why:* turn a persistently-flaky live API into a reliable one without a
   production search stack.

4. **Robust `search_wikipedia`.** Retries with exponential backoff; returns graceful sentinel
   strings (never raises). *Why:* a single flaky Wikipedia response used to crash the whole run.

5. **Structured logging.** Per-example traces (JSONL + pretty JSON), per-search status
   (ok/empty/failed), a latency breakdown (agent vs Wikipedia vs judge), and turn structure.
   *Why:* debug failures and see exactly what the agent dispatched and whether searches were
   parallel or sequential.

6. **Timestamp-only output naming.** Every file from a run shares one Unix timestamp
   (`results_/baseline_/trace_/scorecard_{ts}`), and `scorecard_history.csv` is keyed by `ts`.
   The timestamp is the sole run identifier, so runs accumulate instead of overwriting.
   (Replaced an earlier content-hash SI-versioning scheme — it added bookkeeping without helping.)

## Metrics & rubric design

7. **Four quality metrics (0/1/2)** — correctness, completeness, conciseness, groundedness —
   graded by a *separate, stronger* judge model (**Opus 4.8** judging **Sonnet 4.6**) to reduce
   self-grading bias.

8. **Conciseness metric** (relevance, not length) — the mirror of completeness: completeness
   penalizes *under*-answering, conciseness penalizes *over*-answering. *Why:* baseline answers
   padded unrequested factoids (e.g. Canberra's population/history for "what is the capital?").

9. **Grounding as an overriding principle.** Facts must come from the retrieved content. A
   `SOURCING REQUIRED` (yes/no) flag — derived from the eval's `expected_search`, fed only to the
   *judge* — lets the model use its own knowledge for no-lookup questions (arithmetic, translation,
   creative) but **never** for factual lookups; any fact asserted when searches failed scores
   correctness 0 / groundedness 0. *Why:* the system must not answer from Claude's memory when it
   should be grounding in Wikipedia.

10. **Metric honesty (conditioned metrics).** Non-applicable examples no longer distort metrics:
    - `citation*` — cited rate only among examples expected to give a sourced answer (excludes
      no-search categories and absence-reporting `missing_detail`). Corrected a misleading
      0.83 → ~1.0.
    - `groundedness` is **N/A for `no_search_needed`** — a haiku / "17×23" has no factual claims to
      ground, so an auto-2 would inflate the metric.

11. **Behavioral metrics** (separate from quality): `tool_use_accuracy` (searched exactly when
    expected), avg searches, avg turns (reveals parallel vs sequential multi-hop), search-failure
    count.

12. **Hallucination flag (binary, scored separately from groundedness).** The judge returns
    `hallucinated` true/false; the scorecard reports a per-category **count** (target 0). *Why:*
    groundedness conflates two very different failures — a *true* fact recalled from memory
    (ungrounded but harmless) and a *fabricated* claim/quote/source (dangerous). Both scored **G1**
    on `false_premise_02`, so groundedness couldn't distinguish them; the flag isolates the
    fabrication. *Evidence:* re-judging the pre-SI-fix answer (invented an "According to Wikipedia"
    quote + astronauts Yang Liwei/Ed Lu) → `hallucinated=True`; the post-fix answer (true width/length
    facts, no fake source) → `hallucinated=False`. Initially deemed redundant with groundedness —
    added once we observed real, repeated fabrications.

13. **`grounded_chain` metric (knowledge-injection detector for multi-hop).** Dependent multi-hop
    examples carry a `must_discover` list (the intermediate entity that must be *looked up*); the
    check passes only if the agent's **first** query doesn't already contain it. Reported as a
    conditioned rate `grounded_chain*` (applicable examples only). *Why:* a model can shortcut a
    chained lookup by injecting its own knowledge into query #1, and `num_turns >= 2` can't catch
    this — it may take several turns yet still bake the answer into the first query. *Evidence:*
    `multi_hop_01` searched `'Tokyo capital Japan population'` (assumed Tokyo from memory) → flagged
    `False`; `multi_hop_03/04` discovered the intermediate fact first → pass; `multi_hop_02` (both
    entities named) → N/A. Supersedes the backlogged `requires_chained_lookup` num_turns proxy.

14. **Consolidated scorecard.** Quality + System-behavior sections, by category + ALL, written per
    version (`scorecard_v{N}.md`) and appended to `scorecard_history.csv` — the hill-climbing
    surface for comparing iterations.

## Dataset & scoping decisions

15. **Dataset:** 23 examples across 7 categories — single-fact, multi-hop, ambiguous, unanswerable,
    missing-detail, false-premise, no-search-needed. Each category is a deliberate probe; the
    unanswerable / missing-detail / false-premise sets specifically target hallucination resistance.

16. **Decided NOT to pursue:** ambiguity sense-enumeration — "what is a jaguar?" focusing on the
    animal is defensible, and 2/3 ambiguous examples already enumerate senses. Not an SI target.
