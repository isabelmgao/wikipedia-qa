# Wikipedia Q&A — Design & Roadmap

A system that answers questions using Claude + Wikipedia, plus an eval suite that measures
how well it works. This doc is the living plan and the skeleton of the written rationale.

## Goal

Given a user question, produce a high-quality answer grounded in Wikipedia, and be able to
**measure** answer quality and system behavior across a representative range of question types.

## Architecture

```
question ──> agent (Claude Sonnet 4.6) ──> search_wikipedia(query) ──> MediaWiki API
                     │  (manual tool-use loop; may search multiple times)
                     └──> grounded answer + trace (used_search, queries, …)
```

- **Agent model:** `claude-sonnet-4-6` — the model that reasons and dispatches searches.
- **Judge model:** `claude-opus-4-8` — a *different, stronger* model grades the agent's
  answers. Using a separate model reduces self-grading bias and gives a more reliable rubric
  scorer. (Judging is one call per example, so the higher cost is negligible.)
- **Retrieval:** live MediaWiki API (no key, no setup). Two calls per search: full-text
  search for titles → plain-text intro extracts. Returns several results so the agent can
  pick the relevant one or re-search.

## Eval design

### Question categories

Each category is a deliberate design statement about what we care about (esp. hallucination
resistance). ~3–4 examples each, ~20 total.

| Category | What it probes | Example | Expect search? |
|---|---|---|---|
| **Single-fact** | Basic retrieval accuracy | "What is the capital of Australia?" | Yes |
| **Multi-hop / synthesis** | Combining facts across articles | "Who was U.S. president when the Eiffel Tower opened?" | Yes |
| **Ambiguous** | Handling underspecified queries | "What is Mercury?" (planet / element / god) | Yes |
| **Unanswerable** | Declining when the topic isn't encyclopedic at all | "What will the weather in Paris be next Tuesday?" | No (just decline) |
| **Missing-detail** | Topic *is* on Wikipedia, but the asked detail isn't | "What is the weight of Julia Roberts's mother?" | Yes (then report absence) |
| **False-premise** | Correcting the question | "When did Einstein win his two Nobel Prizes?" (he won one) | Yes |
| **No-search-needed** | Not over-searching | "What is 17 × 23?" / "Write a haiku about rain." | No |

> **Unanswerable vs. Missing-detail** is a deliberate split. *Unanswerable* = not encyclopedic
> (weather, future, real-time) → the model shouldn't search at all. *Missing-detail* = the entity
> has a page but the trivial fact isn't recorded → the model **should** search, then admit the
> detail is absent rather than fabricate. The two stress different behaviors (search-decision vs.
> refuse-when-absent-after-searching).

### Dataset format

Each example carries a reference so it's gradeable:

```python
{
    "id": "single_fact_01",
    "category": "single_fact",
    "question": "What is the capital of Australia?",
    "reference": "Canberra is the capital of Australia.",   # gold answer / key facts
    "expected_search": True,                                  # did we expect a Wikipedia call?
    "notes": "Common trap: Sydney/Melbourne.",              # optional grading guidance
}
```

### Metrics

Two families, kept separate.

**Answer quality** (LLM judge vs. `reference`, each on a **0/1/2** scale):

| Metric | Probes |
|---|---|
| **Correctness** | Do the answer's facts match the reference (no material errors)? |
| **Completeness** | Does it address every part of what was asked? (penalizes *under*-answering) |
| **Conciseness** | Does it avoid superfluous, unrequested content? (penalizes *over*-answering) |
| **Groundedness** | Are the claims supported by retrieved content (no fabrication)? |

> **Completeness ↔ Conciseness** are mirror images: completeness penalizes leaving out what was
> asked, conciseness penalizes adding what wasn't. Together they pin the answer to "exactly what's
> needed." Conciseness is scored on **relevance, not length** — a long answer to a genuinely complex
> question still scores 2 — so it doesn't bias the system toward terse, robotic replies.

#### Judge rubrics (0/1/2)

These rubrics are the judge prompt. Mean score per metric is reported per category and overall.

**Correctness**
- **2** — All key facts match the reference; no material errors.
- **1** — Core answer right but with a material error, or only partly right.
- **0** — Core answer wrong or contradicts the reference.

**Completeness**
- **2** — Fully addresses every part of the question.
- **1** — Answers the core but omits a sub-part or an important qualifier.
- **0** — Misses the main thing asked, or most of a multi-part question.

**Conciseness** (relevance, *not* length)
- **2** — No superfluous content; every sentence serves the question. A long answer to a genuinely complex question still scores 2.
- **1** — Mostly focused, but includes some unrequested detail.
- **0** — Answer is padded or buried in tangential, unrequested information.

**Groundedness**
- **2** — Every factual claim is supported by retrieved content (or appropriately hedged); no fabrication. A correct refusal when sources lack the answer scores 2.
- **1** — Core claims supported, but some unsupported or embellished detail.
- **0** — Contains fabricated or unsupported claims presented as fact.

> **Note:** to grade *groundedness* the judge must see what the agent actually retrieved, so the
> eval trace captures the retrieved text and passes it to the judge alongside the answer and
> reference. Correctness and completeness are graded against the hand-written `reference`.

**Behavior** (deterministic, from the agent trace):

| Metric | Definition |
|---|---|
| **Search-decision match** | `used_search == expected_search` (did it search exactly when we wanted?) |
| **Cited source** | answer contains a citation marker (e.g. `Source:`) |
| **# searches** | descriptive — efficiency / over-searching signal |

Aggregate = mean per metric, broken down by category (so we see *where* it fails, not just an
average).

### Grading methodology

- **LLM-as-judge** for the open-ended quality metrics — the judge gets the question, the
  reference, and the agent's answer, and returns a structured rubric verdict.
- **Deterministic checks** for behavior (string/trace inspection) — cheap and exact.
- Reference answers are written by hand from Wikipedia so grading has ground truth.

## Roadmap

| Phase | Status | Output |
|---|---|---|
| 0. Env setup | ✓ (needs key) | venv, deps, `.env`, kernel |
| 1. Eval categories + metrics | ← this doc | categories, metric defs, grading method |
| 2. Eval dataset | todo | ~20 questions + references in `eval_data.py` |
| 3. Eval harness | todo | `run_evals()` → per-example + aggregate scores |
| 4. Baseline | todo | run current SI, record numbers, inspect failures |
| 5. SI iteration | todo | improve prompt against evals; log each change + why |
| 6. Package | todo | move SI + dataset to modules; README + rationale |

## Key design choices (for the writeup)

- **Always-search default** vs. letting the model skip — currently strict; the
  no-search-needed category tests that we don't over-correct.
- **Read-all-results / re-search** instruction — targets the observed failure that
  Wikipedia's top hit is often not the best match (e.g. "Mona Lisa", "tallest mountain").
- **Refuse-when-absent** — explicit anti-hallucination instruction, tested by the
  unanswerable + false-premise categories.
- **Separate judge model** — reduces self-grading bias.

## Open questions / future work

- **Conciseness vs. helpfulness tension:** the rubric scores "no superfluous content" as 2, but
  the *ideal* answer carries a little helpful context (not a one-word reply). Risk: conciseness
  creates pressure toward terseness, and nothing currently rewards helpful richness — a
  terse-but-correct-and-complete answer scores 2/2/2/2. Likely fix: scope conciseness to penalize
  only *irrelevant/distracting* content (count brief helpful context as "serving the question") and
  let the SI set the lead-with-answer-plus-light-context tone, rather than add a competing "richness"
  metric that would make scores noisy. Revisit after seeing baseline conciseness scores.
- Recency: the live MediaWiki API is quite current, so a pure "out-of-date" category is weak;
  folded "recent events" into Unanswerable for now.
- Retrieval depth: currently intro extracts only — full-article or section retrieval could
  help multi-hop questions.
- Judge reliability: spot-check judge verdicts against human judgment on a few examples.
