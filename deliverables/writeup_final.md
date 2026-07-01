# Wikipedia Q&A — Design Rationale

This project implements a Wikipedia-grounded question answering system using Claude and the MediaWiki API, together with an evaluation framework that measures answer quality and guides prompt iteration.

Rather than treating prompt engineering as trial and error, I wanted prompt changes to be driven by measurable improvements. As a result, I designed the evaluation suite first, then used it to iteratively refine the prompts and system behavior throughout development.

## 1. What I built

The system consists of four main components:

1. **Wikipedia retrieval.** A lightweight wrapper around the live MediaWiki API. The agent first searches for relevant article titles, then retrieves introductory extracts from the matching pages. Following the assignment requirements, I implemented the retrieval layer myself rather than using a hosted search or RAG system.

2. **Tool definition and retrieval prompts.** Claude is given a custom `search_wikipedia(query: str)` tool together with a retrieval-focused system prompt that governs when to search, how to search, what evidence may be used, and how answers should be presented.

3. **Agent loop.** Using Anthropic's native tool-use API, Claude decides whether retrieval is necessary, emits structured tool calls, performs one or more Wikipedia searches, and synthesizes a final grounded answer.

4. **Evaluation harness.** A separate Claude model evaluates the generated answers using rubric-based scoring. The evaluation harness also records behavioral metrics and execution traces so prompt changes can be measured objectively rather than qualitatively.

### Models used

- **Question-answering agent:** Claude Sonnet 4.6
- **LLM judge:** Claude Opus 4.8

I intentionally used a stronger, separate model as the judge. Evaluation is a more demanding reasoning task than answer generation, and using a different model also reduces self-evaluation bias.

## 2. Prompt engineering approach

The core challenge in this assignment was balancing two competing goals:

- Produce helpful, natural answers.
- Ensure every factual claim is grounded in retrieved Wikipedia evidence rather than the model's own knowledge.

To achieve this, I separated the prompting into two components: the **tool definition** and the **retrieval system prompt**.

### Tool definition

The tool definition tells Claude how to interact with the Wikipedia retrieval system.

The **tool description** explains *when* and *why* the tool should be used—for example, that Wikipedia should be searched before answering factual questions, that multiple searches are allowed, and that the highest-ranked search result is not necessarily the correct one.

The **input schema** specifies the structure of the arguments Claude should emit when making a tool call. In this case, the schema consists of a single search query. Claude never executes the tool itself; instead, it emits a structured tool call, which my Python agent executes against the MediaWiki API before returning the results back to Claude.

### Retrieval system prompt

I intentionally organized the retrieval system prompt into four independent sections because they mirror the flow of the agent itself. Rather than one large collection of instructions, each section controls a distinct aspect of the agent's behavior, making prompt iteration much easier.

#### Role

The Role establishes Claude's objective: answer user questions using Wikipedia as the authoritative source for factual information.

#### Search Policy

The Search Policy governs **when** and **how** retrieval should occur.

It instructs Claude to:

- search before answering factual questions,
- use concise keyword-based searches,
- read all returned articles rather than assuming the first result is correct,
- perform additional searches when the retrieved evidence is insufficient,
- and use multiple searches for comparison or multi-hop questions when necessary.

#### Grounding Policy

The Grounding Policy became the most important prompt iteration during development.

Early evaluation runs showed that when retrieved evidence was incomplete, Claude would sometimes supplement the answer using its own parametric knowledge. While these facts were often correct, they were unsupported by the retrieved evidence and therefore violated the goal of a retrieval-grounded system.

To address this, I added an explicit grounding policy stating that retrieved Wikipedia content is the only authoritative source for factual claims. If a fact is not supported by the retrieved evidence, Claude should leave it out—even if it already knows the answer. The same rule applies when correcting false-premise questions.

This single change substantially improved groundedness across the evaluation suite.

#### Answer Policy

Finally, the Answer Policy controls how responses are presented.

Rather than focusing on factual correctness, it specifies the desired interaction style: answer the user's question directly, include citations to the Wikipedia articles used, distinguish retrieved facts from inference, and explicitly acknowledge when Wikipedia does not contain sufficient evidence rather than guessing.

---

Organizing the prompt into these four policies made prompt engineering much more systematic. Evaluation failures could typically be traced back to a single policy—for example retrieval, grounding, or answer formatting—allowing individual behaviors to be refined without unintentionally affecting the rest of the system.

## 3. Evaluation methodology

I designed the evaluation suite before iterating on the prompts because I wanted prompt engineering to be driven by measurable improvements rather than qualitative inspection.

### Evaluation dataset

The evaluation dataset contains **23 examples** spanning seven categories, each chosen to stress a different behavior of the retrieval system rather than simply testing factual knowledge.

| Category | Purpose |
|-----------|---------|
| **Single fact** | Basic retrieval accuracy |
| **Multi-hop** | Sequential reasoning across multiple Wikipedia searches |
| **Ambiguous** | Handling underspecified queries with multiple possible meanings |
| **False premise** | Correcting incorrect assumptions using retrieved evidence |
| **Missing detail** | Searching appropriately, then admitting when Wikipedia lacks the requested information |
| **Unanswerable** | Recognizing questions that Wikipedia cannot answer (e.g. future events) |
| **No search needed** | Avoiding unnecessary retrieval for arithmetic, translation, or creative writing |

Designing the dataset around behaviors rather than question topics made it much easier to diagnose *why* the system failed and identify targeted prompt improvements.

---

### LLM-as-a-judge

I evaluated the system using **Claude Opus 4.8** as an independent judge while using **Claude Sonnet 4.6** as the question-answering agent.

The judge prompt is organized into two parts:

- an **evaluation policy**, which establishes the grading context, and
- a set of explicit **0–2 scoring rubrics**.

One important design decision was introducing an `expected_search` label in the evaluation data. This label is **never shown to the agent**—it is used only by the judge to determine whether a question should be evaluated as a Wikipedia-grounded retrieval task or as a task where retrieval is unnecessary, such as arithmetic or creative writing.

This prevents the evaluator from unfairly penalizing questions that were never intended to use Wikipedia while still enforcing strict grounding for factual questions.

---

### Metrics

I measured three complementary aspects of the system.

#### Answer quality (LLM judge)

The judge scores each answer using explicit 0–2 rubrics for:

- **Correctness** — Does the answer agree with the reference answer?
- **Completeness** — Does it answer every part of the question?
- **Conciseness** — Does it stay focused on what was asked?
- **Groundedness** — Are factual claims supported by the retrieved Wikipedia evidence?

I also included a separate **hallucination** metric.

I intentionally treated hallucination and groundedness as different failure modes. An answer can be factually correct but still be **ungrounded** if it relies on the model's own knowledge rather than retrieved evidence. Hallucinations, on the other hand, are fabricated facts or fabricated citations. Separating these metrics made it easier to distinguish retrieval failures from genuine fabrication.

#### Agent behavior

In addition to answer quality, I measured how the agent used retrieval.

Behavioral metrics include:

- **Tool-use accuracy** — Did the agent search when retrieval was expected?
- **Citation rate** — Did grounded answers cite their Wikipedia sources?
- **Average number of searches** — Was retrieval efficient or excessive?
- **Average number of turns** — How many Claude–tool interactions were required?
- **Grounded chain** — For dependent multi-hop questions, did the model retrieve intermediate facts before using them?

The final metric, **grounded_chain**, was introduced after observing that Claude would sometimes inject intermediate facts from memory rather than discovering them through retrieval.

#### Infrastructure

Finally, I tracked infrastructure metrics such as **Wikipedia search failures** and latency.

These metrics were useful not only for separating prompt failures from operational issues, but also for guiding improvements to the retrieval system itself. Early evaluation runs revealed frequent Wikipedia API failures caused by concurrent requests and rate limiting. In response, I added a global rate limiter, exponential backoff with retry handling, persistent Wikipedia page caching, and concurrent execution of LLM calls while throttling only the Wikipedia requests.

These engineering improvements reduced search failures to zero and ensured that subsequent prompt iterations were measured against a stable retrieval system rather than fluctuating infrastructure performance.


## 4. Where the system succeeds and where it fails

Because I iterated against the eval suite, I can point to concrete numbers rather than impressions. On the last clean full run (23 examples):

- **Correctness 2.00**, **completeness 1.96**, **groundedness 1.90**, **conciseness 1.74** (all on the 0–2 scale)
- **Tool-use accuracy 0.96**, **citation rate 1.0**, **Wikipedia search failures 0**

**Where it succeeds.** Factual accuracy and citation are essentially saturated. The system searches when it should, chains most multi-hop questions correctly, declines genuinely unanswerable questions without guessing, and reports missing details rather than fabricating them.

**Where it fails.**

- **Conciseness is the weakest dimension (1.74).** The failures split into two distinct causes: unnecessary narration on no-search questions ("this doesn't require a Wikipedia source"), and over-answering on simple factual questions—adding history or related context the user never asked for.
- **Groundedness on false-premise questions (1.33)** is limited by my deliberate choice of intro-only retrieval: the debunking evidence often lives later in the article, so the model falls back on a *true but ungrounded* recalled fact. This is a retrieval-design limitation, not a prompt failure—and the evaluation is what let me tell those two apart.
- **Knowledge injection on multi-hop questions**, caught by the grounded_chain metric (see §5).

**What I learned.** Two lessons generalized beyond this project:

- **Instructing the model to cite sources—without guaranteeing the evidence is actually present—is a hallucination amplifier.** In an early run, when asked whether the Great Wall is visible from space, Claude fabricated a direct "according to Wikipedia" quotation and invented supporting astronaut names, manufacturing a citation to satisfy the instruction. The fix was to pair "cite your sources" with an explicit escape hatch: if it isn't in the retrieved text, say so—never invent a source. The hallucination flag confirmed the fix, flagging the pre-fix answer and clearing the post-fix one.
- **Groundedness and hallucination are different axes.** A true-but-unsourced fact and a fabricated quotation scored *identically* on groundedness; only the separate hallucination flag distinguished the dangerous one. That is exactly why I kept them as two metrics rather than folding hallucination into groundedness.

## 5. Key iterations driven by the evaluation

The evaluation suite became the primary development tool throughout this project. Rather than manually inspecting a handful of examples, I iterated by modifying the prompts, rerunning the benchmark, and using the resulting metrics, traces, and judge reasoning to identify the next improvement.

### Strengthening the grounding policy

The most important observation was that some groundedness failures were not because Claude lacked knowledge, but because it knew too much. When the retrieved Wikipedia evidence was incomplete, the model would occasionally supplement the answer with facts from its own parametric knowledge.

To address this, I introduced an explicit **Grounding Policy** stating that retrieved Wikipedia content is the only authoritative source for factual claims. If a fact is not supported by the retrieved evidence, Claude should omit it—even if it knows the answer from memory.

This significantly reduced unsupported factual claims: on the false-premise questions, groundedness rose from **0.67 to 1.33**, converting cases where the model fabricated or embellished from memory into answers that either cite the retrieved evidence or explicitly note what is missing.

---

### Detecting shortcut reasoning in multi-hop questions

Another interesting failure mode appeared on dependent multi-hop questions.

For example, when asked:

> *"What is the population of the capital of Japan?"*

Claude would often search directly for **"Tokyo population"**, implying it had already supplied the intermediate fact ("Tokyo is the capital of Japan") from its own knowledge rather than discovering it through retrieval.

To expose this behavior, I added an experimental behavioral metric called **grounded_chain**, which checks whether intermediate entities are retrieved before being used in subsequent searches.

This is admittedly a brittle heuristic—it relies on expected intermediate entities—but it highlighted a failure mode that answer-quality metrics alone could not detect.

---

### Improving answer conciseness

The evaluation suite also revealed that answers were often more verbose than necessary, adding historical context or related facts that were not requested by the user.

Rather than relying on subjective preferences, I introduced **conciseness** as an explicit evaluation rubric and refined the Answer Policy to encourage direct answers before additional context.

This was aimed at making the system more responsive while still preserving factual completeness. In the interest of full transparency: the final prompt reorganization into four labeled policies was validated in content but not separately re-measured as a whole, because I ran out of API credits before a final confirmation run. The grounding improvement above, by contrast, was measured directly.


## 6. Future work

Given more time, I would continue improving both the prompts and the retrieval system.

### Prompt engineering

The next prompt iteration would focus on strengthening the retrieval policy for dependent multi-hop questions. Rather than allowing Claude to formulate later searches using its own knowledge, I would encourage it to explicitly derive intermediate entities from retrieved evidence before issuing subsequent searches.

I would also revisit the system prompt itself. During development, several instructions were added in response to specific failure cases uncovered by the evaluation suite. With more iterations, I would look for higher-level principles that capture those behaviors with fewer, clearer instructions, making the prompt easier to maintain while preserving the same behavior.

### Retrieval

The current prototype retrieves only the introductory extract of each Wikipedia article. While this keeps retrieval lightweight, it also means that evidence appearing later in an article is never available to the model.

Retrieving relevant sections—or selectively retrieving full articles when necessary—would likely improve groundedness on more complex questions while reducing unnecessary follow-up searches.

### Evaluation

Finally, I would expand the evaluation suite with additional examples, particularly for multi-hop reasoning and ambiguous retrieval, and perform more human spot-checking of the LLM judge to further validate the reliability of the evaluation framework.

## 7. Time spent

I spent approximately **5 hours** on this project in total, spanning system design, dataset construction, eval-harness engineering (the Wikipedia rate-limiting and reliability work was a meaningful chunk), and the measured prompt iteration described above.
