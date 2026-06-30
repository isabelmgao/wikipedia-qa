# Wikipedia Q&A

Answer questions with Claude (Sonnet 4.6) grounded in **live Wikipedia**. The model decides when
to search, calls a `search_wikipedia` tool as many times as it needs, and grounds its answer in
what it retrieves — citing the articles it used. A companion **eval harness** grades the system
across a labeled dataset so quality changes can be measured, not guessed.

Everything runs in `notebook.ipynb`. There are two ways to use it:
**(A) ask a question**, or **(B) evaluate the system**.

## Setup

1. **Python 3.10+.** Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   source .venv/bin/activate        # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

2. **Add your Anthropic API key:**

   ```bash
   cp .env.example .env
   # then edit .env and set ANTHROPIC_API_KEY=sk-ant-...
   ```

   Get a key at <https://console.anthropic.com/settings/keys>. A few dollars of credit is plenty;
   the full eval run below costs roughly **$1**, a single question a fraction of a cent.

3. Open `notebook.ipynb` (in VS Code, or run `jupyter lab`) and select the **`.venv`** kernel.

---

## (A) Ask a question

Run the cells from the top **through section 4 (Demo)**. The demo answers a sample question and
**shows whether search was used**, the queries it issued, and the grounded answer:

```python
result = answer_question("Who painted the Mona Lisa, and where is it displayed today?", verbose=True)
print("Used search:", result["used_search"], "| searches:", result["num_searches"])
print("Queries:", result["queries"])
print(result["answer"])
```

To ask your own question, change the text and re-run that one cell:

```python
print(answer_question("What is the tallest mountain in Africa?")["answer"])
```

`answer_question(...)` returns the answer plus a full trace (`used_search`, `num_searches`,
`queries`, retrieved text, timing). You do **not** need the eval harness to ask questions.

---

## (B) Evaluate the system

The eval harness (section 5) runs the agent over a labeled dataset (`eval_data.py`), grades each
answer with a **separate, stronger judge model (Opus 4.8)**, and reports a scorecard.

- **Quick smoke test** — run the **`run-sample`** cell (3 examples) to confirm everything is wired
  up. Cheap.
- **Full run** — run the **`run-full`** cell (all 23 examples). It prints a scorecard and writes
  timestamped outputs to `eval_results/`:
  - `scorecard_{ts}.md` — quality + behavior metrics by category
  - `eval_results_{ts}.csv` — per-example scores and the queries the agent searched
  - `trace_{ts}.json` — full per-example traces
  - one row appended to `scorecard_history.csv` — the hill-climbing record across runs

**Metrics:** four quality scores on a 0/1/2 rubric (correctness, completeness, conciseness,
groundedness), a binary **hallucination** flag, and behavioral checks (searched when expected,
cited a source, and `grounded_chain` — did multi-hop questions look up the intermediate fact
rather than assume it). See `DESIGN.md` for the rationale and `CHANGELOG.md` for what was tuned
and why.

---

## What's in here

| File | Purpose |
|---|---|
| `notebook.ipynb` | The system (retrieval → system prompt → agent loop) + the eval harness. |
| `eval_data.py` | The evaluation dataset (questions, reference answers, labels). |
| `DESIGN.md` | Design rationale: question categories, metrics, grading method. |
| `CHANGELOG.md` | What was improved and why — the hill-climbing log. |
| `IMPROVEMENTS.md` | Backlog of changes not yet shipped. |
| `eval_results/` | Saved scorecards, per-example metrics, and traces from prior runs. |
