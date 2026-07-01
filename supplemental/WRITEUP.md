# Wikipedia Q&A — Design Rationale

*The written half of the design-rationale deliverable; it also serves as the outline for the
~5-minute video. Companion docs: `DESIGN.md` (the living plan), `CHANGELOG.md` (every shipped
change + why), `IMPROVEMENTS.md` (backlog).*

---

## 1. What I built

A system that answers questions with **Claude Sonnet 4.6** grounded in **live Wikipedia**, plus an
**evaluation harness** that grades it so quality changes can be measured rather than guessed.

- **Agent:** a manual tool-use loop. The model decides whether to search, issues `search_wikipedia`
  queries (in parallel or in sequence), reads intro extracts, and writes a grounded, cited answer.
- **Retrieval:** the live MediaWiki API — a full-text search for titles, then plain-text intro
  extracts. No API key, no hosted RAG/web-search tool. Per the assignment, **I built the search
  myself** and focused on prompt quality and eval design, not production retrieval.
- **Judge:** a *separate, stronger* model — **Opus 4.8 grades Sonnet 4.6** — returning a structured
  (JSON-schema) verdict. I used a stronger model for evaluation than generation: since the
  evaluation suite is relatively small, a more capable judge improves scoring reliability at
  negligible additional cost, while reducing the likelihood that the judge shares the same
  weaknesses as the evaluated system (self-grading bias).

Everything runs in `notebook.ipynb` (ask a question, or run the eval suite); `eval_data.py` holds
the dataset.

---

## 2. Prompt-engineering approach (and why)

The core design tension is **"ground everything in Wikipedia" vs. "stay genuinely helpful."** The
system prompt resolves it with four explicit policies:

- **Self-determined sourcing.** The model itself decides whether a request needs retrieval —
  factual lookups must search; arithmetic, translation, and creative tasks must not. I deliberately
  did **not** drive this from the eval's labels: the prompt reasons from the *nature of the
  question*, and the labels are used only by the judge to *measure*. (A system that only looked
  right because it was told the answer key would not generalize.)
- **Grounding as the overriding rule.** Factual claims must trace to retrieved content. The prompt
  explicitly forbids importing facts from prior knowledge "even if you believe they are correct,"
  and forbids inventing names, dates, quotations, or statistics.
- **Honest limitation over guessing.** If the evidence is insufficient, say what's missing rather
  than fabricate — the anti-hallucination behavior the dataset is built to stress.
- **Answer shape.** Lead with the direct answer, add only necessary detail, cite the article(s) by
  name, and self-verify that each claim is supported before finalizing.

The final iteration reorganizes these into labeled sections (`<Role>`, `<SearchStrategy>`,
`<GroundingPolicy>`, `<AnswerPolicy>`). XML tags aren't strictly required, but they're idiomatic for
Claude and make the policy boundaries unambiguous. **Honest caveat:** this reorganization is the one
change I could not re-measure — I ran out of API credits before the validation run — so it ships as
a structural cleanup of already-validated content, not a separately-proven improvement.

---

## 3. Eval-suite design: what I measured, and why

### Dataset — 23 examples across 7 categories
Each category is a deliberate probe, chosen to stress a *different* behavior (not just to sample
trivia):

| Category | What it stresses |
|---|---|
| **single_fact** (4) | Basic retrieval accuracy |
| **multi_hop** (4) | Chaining facts across articles (and *not* shortcutting via memory) |
| **ambiguous** (3) | Handling underspecified queries / multiple senses |
| **unanswerable** (3) | Declining cleanly when the topic isn't encyclopedic (weather, future, real-time) |
| **missing_detail** (3) | Topic *is* on Wikipedia but the asked detail isn't → search, then report absence |
| **false_premise** (3) | Correcting a wrong premise *using the sources* |
| **no_search_needed** (3) | Not over-searching (arithmetic, translation, creative) |

The **unanswerable vs. missing_detail** split is intentional: one should *not* search, the other
*should* search and then admit the detail is absent — two different failure modes for hallucination.

### Metrics — three families, kept separate
**Quality (0/1/2 rubric, LLM judge):**
- **Correctness** — facts match the reference (for lookups, only *grounded* facts count).
- **Completeness** — addresses every part asked (penalizes *under*-answering).
- **Conciseness** — no superfluous content; scored on **relevance, not length** (penalizes
  *over*-answering). Completeness and conciseness are mirror images that together pin the answer to
  "exactly what was needed."
- **Groundedness** — *how much* of the answer traces to retrieved content (provenance).

**Safety (binary):**
- **Hallucination** — did the answer *fabricate* content (a false claim, an invented quotation, or a
  fake "according to Wikipedia")? Scored **separately** from groundedness on purpose — see §5.

**Behavioral (deterministic, from the trace):**
- **tool_use_accuracy** (searched exactly when expected), **citation\***, **avg_searches /
  avg_turns** (reveals parallel vs. sequential hops), **search_fails**, and **grounded_chain\***
  (did dependent multi-hops look up the intermediate fact rather than assume it?).

### Two design decisions that make the metrics honest
- **A `SOURCING REQUIRED` flag** (derived from each example's `expected_search`, fed *only* to the
  judge) lets the system use its own knowledge on no-lookup questions but **never** on factual
  lookups — and makes "answered a factual question from memory" score correctness 0 / groundedness 0.
- **Conditioned metrics** so non-applicable examples don't distort averages: `citation*` counts only
  examples expected to give a sourced answer; `groundedness` excludes `no_search_needed` (a haiku has
  nothing to ground); `grounded_chain*` covers only dependent multi-hops.

---

## 4. Where it succeeds, where it fails, what the evals taught me

**Headline (last clean full run, 23 examples):** correctness **2.00**, completeness **1.96**,
conciseness **1.74**, groundedness **1.90**, tool_use_accuracy **0.96**, citation\* **1.0**,
search_fails **0**, hallucinations **0** (post-fix).

**Succeeds:** factual accuracy and citation are essentially saturated; it searches when it should,
chains most multi-hops correctly, declines unanswerable questions cleanly, and reports absent details
without fabricating.

**Fails / the interesting parts — what the evals localized:**
- **Conciseness is the weakest metric (1.74),** and decomposes into *two distinct causes*: (a)
  **tool-narration** on `no_search_needed`/`unanswerable` ("this doesn't require a Wikipedia
  source"; unsolicited "you could try…"), and (b) **over-answering** on `single_fact` (1.25) and
  `ambiguous` (extra unrequested facts). Two different fixes, not one.
- **`false_premise` groundedness (1.33) reflects a deliberate retrieval choice, not a prompt
  failure.** I intentionally use **intro-only retrieval**: it keeps the prototype simple, minimizes
  context size, and still performs well for many encyclopedic questions. The evaluation uncovered its
  limitation — some evidence needed for false-premise (and multi-hop) questions appears *later in the
  article*, so the model recalls a *true* fact it wasn't given a source for (hence G1, not G0). The
  eval cleanly **separated a prompt problem (fixed) from a retrieval-design limitation (accepted by
  choice).**
- **Knowledge injection in multi-hop queries.** `multi_hop_01` ("population of the capital of Japan")
  searched `Tokyo capital Japan population` — assuming "Tokyo" from memory instead of looking up the
  capital. `grounded_chain` flags it; a turn-count metric would have missed it (see §5).

**Transferable lessons:**
- *"Cite your sources" without guaranteeing the content is present is a hallucination amplifier* — it
  pressures the model to **fabricate citations** to satisfy the instruction. The fix is to pair "cite"
  with an explicit escape hatch ("if it's not retrieved, say so — never invent a source").
- *Groundedness and hallucination are different axes.* A true-from-memory fact and a fabricated quote
  both scored **G1** on the same answer; only the separate hallucination flag distinguished the
  dangerous one.

---

## 5. Key iterations driven by eval results (the hill-climb)

1. **Wikipedia reliability.** Concurrency caused HTTP 429s that crashed runs; backoff alone made it
   worse (retrying adds load). Fixed with a disk **cache**, a global **~1 req/s throttle**, a
   **descriptive User-Agent**, and `Retry-After`/backoff → `search_fails` went to **0**.
2. **Grounding-aware judge + `SOURCING REQUIRED`.** Made the judge penalize answering-from-memory and
   reward clean refusals when sources are absent — so the metric rewards *grounding*, not just
   correctness.
3. **Metric honesty.** Conditioned `citation*` (corrected a misleading 0.83 → ~1.0), made
   groundedness N/A for `no_search_needed`, and stopped citation penalizing absence-reporting answers.
4. **Anti-fabrication system-prompt fix.** Added explicit "never invent a quotation / attribute a
   statement to Wikipedia" rules. `false_premise` groundedness **0.67 → 1.33**; this *converted*
   outright fabrication (a fake Great-Wall quote + invented astronauts) into honest, true-but-ungrounded
   recall. Diagnosed root cause = citation pressure colliding with a retrieval miss.
5. **Hallucination flag added.** I had judged a dedicated hallucination metric "overkill" — until the
   evals surfaced *real, repeated* fabrications. Validated it on the actual before/after answers: the
   pre-fix fabricated quote → `hallucinated=True`, the post-fix recall → `False`, while groundedness
   couldn't tell them apart.
6. **`grounded_chain` metric.** A *content-based* knowledge-injection detector: dependent multi-hops
   carry a `must_discover` entity, and the check fails if the **first** query already contains it.
   This catches `multi_hop_01` where a `num_turns ≥ 2` proxy could not (the model can take several
   turns yet still bake the answer into query #1).
7. **System-prompt reorganization** into labeled policy sections (validated content; not separately
   re-measured — credits ran out).

---

## 6. How I'd extend this with more time

- **Hierarchical retrieval** — the single highest-leverage change: first retrieve the introduction,
  then fetch additional sections only if the evidence is insufficient. This keeps context small in
  the common case while letting `false_premise` debunks and multi-hop questions ground on the deeper
  facts (G1 → G2).
- **Close the conciseness gap** with a targeted prompt pass for both causes (kill tool-narration;
  lead-with-answer), then *measure* it — and validate the reorganized prompt I couldn't run.
- **Fix multi-hop knowledge injection** with an explicit "look up intermediate facts, don't assume
  them" instruction, and watch `grounded_chain` move.
- **Harden the harness:** exclude API/retrieval-errored rows from quality aggregates and surface an
  error count on the scorecard (a partial run currently shifts a rate and can read as a regression).
- **Strengthen the eval itself:** a larger, more adversarial dataset; multiple judge samples (or a
  human spot-check) to measure judge reliability; and factoring the prompt + dataset into modules
  behind a small CLI binary.

---

## 7. Engineering & operational considerations

The assignment is about prompts and evals, but a flaky harness produces untrustworthy numbers, so a
fair amount of the work went into making runs **reliable, cheap to repeat, and fully observable**.

- **Rate limiting & retries.** Running examples concurrently tripped Wikipedia's HTTP **429 (Too
  Many Requests)**, and naive backoff made it *worse* (a retry just adds load). The fix layers, in
  order of leverage: a global **~1 req/s throttle** on request *starts* (a lock + min-interval, so
  it holds regardless of worker count — only Wikipedia is throttled, LLM calls stay concurrent); a
  **descriptive User-Agent** (Wikipedia throttles generic ones); and **exponential backoff +
  `Retry-After`** with a 60s timeout. `search_wikipedia` **never raises** — on failure it returns a
  graceful sentinel string, so one bad response can't crash a 23-example run.
- **Caching.** A persistent disk cache (`eval_results/wiki_cache.json`) stores *successful* queries,
  so repeats — within a run, across retries, and across re-runs — never re-hit Wikipedia. Failures
  are deliberately **not** cached, so a 429'd query retries fresh. Beyond cutting load, the cache
  makes a prompt-only re-run a **clean experiment**: identical retrieved content, so any scorecard
  delta is attributable to the prompt change alone.
- **Concurrency & resumability.** A `ThreadPoolExecutor` (`max_workers`) parallelizes examples
  (latency is dominated by LLM calls). Each example is written to a JSONL log **the moment it
  finishes**; re-running with `resume=True` skips completed examples and retries only failures —
  which is exactly how I recovered the 5 examples that died on a mid-run credit-exhaustion error.
- **Structured, timestamped logging.** Every run is keyed by one Unix timestamp so runs accumulate
  instead of overwriting, emitting the set of output files described below.
- **Structured judge output.** The judge is forced to return a valid rubric via a JSON schema
  (`output_config` / `json_schema`), so verdicts are parsed without regex and the model retries on a
  malformed response.

### Eval output files (all keyed by run timestamp `{ts}`)

| File | What it holds | Why it's useful |
|---|---|---|
| `trace_{ts}.json` | The full per-example trace, pretty-printed as one array — queries + per-search status, retrieved text, answer, **judge verdict + rationale**, latency, turn structure. | Human-readable inspection — see what Claude searched, what it read, and *why* the judge scored it. |
| `eval_results_{ts}.csv` | Per-example metrics plus the actual queries searched. | Quick spreadsheet sort to find failing examples and inspect their queries at a glance. |
| `scorecard_{ts}.md` | Quality + behavior metrics by category, for one run. | The human-readable summary you read after a run. |
| `scorecard_history.csv` | One `ALL` row appended per run. | The hill-climbing record — diff runs to confirm a change actually helped. |

*Each Wikipedia result is capped at ~600 chars in the trace; the untruncated text lives in
`wiki_cache.json`, keyed by query. (An append-only JSONL log is also written during the run — the
internal write-ahead log that makes `resume` possible — but the artifacts above are what you read.)*

These choices are why headline metrics like `search_fails = 0` are believable, and why each
iteration in §5 could be attributed to a single change rather than to run-to-run noise.

---

## 8. Constraints honored & time spent

- **Constraints:** Anthropic API only (Sonnet 4.6 agent, Opus 4.8 judge); **no hosted search/RAG
  tool** — the Wikipedia layer is hand-built; emphasis on prompt quality and eval design.
- **Time spent:** approximately **__ hours** *(fill in)*, spread across system design, dataset
  construction, harness engineering (the 429 reliability work was a meaningful chunk), and the
  measured hill-climb above.
