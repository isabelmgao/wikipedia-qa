# Improvements — To Make

Backlog of changes not yet shipped. Already-shipped changes live in `CHANGELOG.md`.
Priority: **P1** (do soon) → **P3** (nice to have).

---

## A. System-instruction (prompt) changes  — the Phase-5 iteration targets

The SI is intentionally **unchanged** so each of these is measured against the v1 baseline.
Bumping the prompt auto-increments `SI_VERSION`; each run appends a row to `scorecard_history.csv`.

1. **(P1, factuality) Self-determined sourcing — never driven by our eval tags.** The SI must have
   Claude *itself* judge whether a question calls for an encyclopedic/factual lookup. For those:
   ground the answer in search, and **if search fails, refuse cleanly — say retrieval failed
   without restating any entity or fact** (no "the population of Tokyo, the capital of Japan").
   For non-lookups (arithmetic, translation, creative, subjective), answer directly. Claude never
   sees our `expected_search` label — phrase the rule by the *nature of the question*.
   - *Evidence:* `false_premise_02` answered from memory (Yang Liwei, NASA) when searches failed;
     the Tokyo failure-refusal leaked "the capital of Japan."

2. **(P1, groundedness) State only what the retrieved sources support; do not embellish from
   prior knowledge.**
   - *Evidence:* `false_premise_03` (Edison "1879"), `missing_detail_03` (da Vinci freeing caged
     birds), `unanswerable_02` (internet-user count) all added unsourced facts → groundedness 1.

3. **(P2, grounding rigor) Look up intermediate facts rather than assuming them.** For multi-hop
   questions, derive the intermediate fact from Wikipedia (sequential lookups) instead of recalling
   it. Ties to the `requires_chained_lookup` metric (B2).
   - *Evidence:* `multi_hop_01`'s first query was already "Tokyo capital Japan population" — it
     assumed Tokyo from memory instead of looking up the capital.

4. **(P2, conciseness) Lead with the direct answer; add only context that serves the question.**
   Specify target verbosity.
   - *Evidence:* conciseness is the weakest quality metric (single_fact ~1.25); the judge
     repeatedly flags "extra facts not requested."
   - *Watch:* don't over-correct to terse/robotic — see the conciseness↔helpfulness note in DESIGN.md.

---

## B. Eval / harness / metric changes

1. **(P1) Exclude retrieval-failed examples from the quality aggregates.** When *all* of an
   example's searches return `failed`, the scores measure infrastructure, not model quality —
   exclude them from the quality means (like error rows). Do NOT assign negative scores.
   - *Note:* the rate-limiter should make this rare, but it's defense-in-depth so a stray outage
     can't pollute a baseline.

2. ~~**(P2, behavioral metric) Add `requires_chained_lookup`**~~ — **SHIPPED** as `grounded_chain`
   (CHANGELOG 13). We dropped the `num_turns >= 2` proxy entirely: it can't catch a model that takes
   several turns yet still injects the intermediate answer into query #1 (exactly what `multi_hop_01`
   did). The shipped check is content-based — the first query must not contain the `must_discover`
   entity. Labels became `must_discover`: `multi_hop_01=[Tokyo]`, `_03=[Everest]`, `_04=[Brazil,Rio]`,
   `_02=`none (both entities named → parallel is legitimate).

3. **(P3, cosmetic) Consolidate the grounding rubric wording.** The judge prompt has accreted
   several clauses (SOURCING REQUIRED, searches-failed handling, refusal rules) — fold them into one
   clear statement without changing behavior.

4. **(Watch) Multithreading load.** The global rate-limiter mitigates the 429s; keep watching the
   `search_fails` count. If it climbs, lower `max_workers` or tighten `_WIKI_MIN_INTERVAL`.

---

## Process notes
- **Re-baseline** with the current (throttle + grounding-aware judge) before comparing versions —
  older v1 numbers used a lenient judge and a contaminated run, so they aren't comparable.
- Hill-climb loop: edit SI → `SI_VERSION` auto-bumps → `run-full` → diff `scorecard_history.csv`.
