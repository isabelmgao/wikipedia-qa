"""Eval dataset for the Wikipedia Q&A system.

Each example has:
  id              - unique slug
  category        - one of the six question categories (see DESIGN.md)
  question        - the user's question
  reference       - hand-written gold answer / key facts the judge grades against
  expected_search - did we expect the agent to call search_wikipedia?
  notes           - optional grading guidance / why this example exists

References are tolerant of phrasing and approximate figures; they capture the key
facts a correct answer must contain, not exact wording.
"""

EVAL_EXAMPLES = [
    # ---------- single-fact: basic retrieval accuracy ----------
    {
        "id": "single_fact_01",
        "category": "single_fact",
        "question": "What is the capital of Australia?",
        "reference": "Canberra is the capital of Australia.",
        "expected_search": True,
        "notes": "Common trap: Sydney or Melbourne (the larger cities) are not the capital.",
    },
    {
        "id": "single_fact_02",
        "category": "single_fact",
        "question": "What is the chemical symbol for gold?",
        "reference": "The chemical symbol for gold is Au.",
        "expected_search": True,
    },
    {
        "id": "single_fact_03",
        "category": "single_fact",
        "question": "Who wrote the novel 'Pride and Prejudice'?",
        "reference": "Jane Austen wrote Pride and Prejudice (published 1813).",
        "expected_search": True,
    },
    {
        "id": "single_fact_04",
        "category": "single_fact",
        "question": "How many bones are in the adult human body?",
        "reference": "An adult human body has 206 bones.",
        "expected_search": True,
        "notes": "Infants have more (~270); the adult count is 206.",
    },

    # ---------- multi-hop: combining facts across articles ----------
    {
        "id": "multi_hop_01",
        "category": "multi_hop",
        "question": "What is the population of the capital of Japan?",
        "reference": (
            "Tokyo is the capital of Japan. Its population is roughly 14 million in the "
            "city proper, or about 37 million in the greater Tokyo metropolitan area. "
            "Accept figures in this range."
        ),
        "expected_search": True,
        "must_discover": ["Tokyo"],   # the capital must be looked up, not assumed from memory
        "notes": "Two hops: capital of Japan -> Tokyo -> its population.",
    },
    {
        "id": "multi_hop_02",
        "category": "multi_hop",
        "question": "Which is taller, the Eiffel Tower or the Statue of Liberty?",
        "reference": (
            "The Eiffel Tower (~330 m) is much taller than the Statue of Liberty "
            "(~93 m including its pedestal)."
        ),
        "expected_search": True,
    },
    {
        "id": "multi_hop_03",
        "category": "multi_hop",
        "question": "In what country is the world's highest mountain located?",
        "reference": (
            "Mount Everest, the highest mountain above sea level, lies on the border of "
            "Nepal and China (Tibet). Either Nepal or the Nepal/China border is acceptable."
        ),
        "expected_search": True,
        "must_discover": ["Everest"],   # which mountain is highest must be looked up, not assumed
        "notes": "Watch 'highest' (Everest, above sea level) vs 'tallest base-to-peak' (Mauna Kea).",
    },
    {
        "id": "multi_hop_04",
        "category": "multi_hop",
        "question": "What is the official language of the country that hosted the 2016 Summer Olympics?",
        "reference": (
            "The 2016 Summer Olympics were held in Rio de Janeiro, Brazil. Brazil's "
            "official language is Portuguese."
        ),
        "expected_search": True,
        "must_discover": ["Brazil", "Rio"],   # the host country must be looked up, not assumed
    },

    # ---------- ambiguous: underspecified queries with multiple senses ----------
    {
        "id": "ambiguous_01",
        "category": "ambiguous",
        "question": "What is Mercury?",
        "reference": (
            "'Mercury' is ambiguous. Main senses: the planet Mercury (closest to the Sun); "
            "the chemical element mercury (Hg), a liquid metal; and Mercury, the Roman god. "
            "A good answer acknowledges the ambiguity and covers the major senses."
        ),
        "expected_search": True,
        "notes": "Grade on whether it surfaces the ambiguity rather than picking one sense silently.",
    },
    {
        "id": "ambiguous_02",
        "category": "ambiguous",
        "question": "Tell me about Java.",
        "reference": (
            "'Java' is ambiguous. Main senses: the island of Java in Indonesia; the Java "
            "programming language; and java as a slang term for coffee. A good answer "
            "acknowledges the ambiguity and covers the major senses."
        ),
        "expected_search": True,
    },
    {
        "id": "ambiguous_03",
        "category": "ambiguous",
        "question": "What is a jaguar?",
        "reference": (
            "'Jaguar' can mean the large wild cat (Panthera onca) native to the Americas, or "
            "Jaguar the British luxury car manufacturer. A good answer notes both main senses."
        ),
        "expected_search": True,
    },

    # ---------- unanswerable: gracefully decline, do not fabricate ----------
    {
        "id": "unanswerable_01",
        "category": "unanswerable",
        "question": "What will the weather be in Tokyo next Friday?",
        "reference": (
            "This is a future weather forecast, which Wikipedia cannot provide. The correct "
            "behavior is to explain that this isn't answerable from Wikipedia, not to guess."
        ),
        "expected_search": False,
        "notes": "Tests over-searching: a strict 'always search' SI may waste a search here.",
    },
    {
        "id": "unanswerable_02",
        "category": "unanswerable",
        "question": "How many people are using the internet at this exact moment?",
        "reference": (
            "This is real-time data that Wikipedia does not contain. The correct behavior is "
            "to explain it can't be answered from Wikipedia (general usage statistics are fine "
            "to mention, but no exact live count)."
        ),
        "expected_search": False,
    },
    {
        "id": "unanswerable_03",
        "category": "unanswerable",
        "question": "Who will win the 2032 U.S. presidential election?",
        "reference": (
            "This is a future event with no factual answer. The correct behavior is to decline "
            "and explain that the outcome is unknowable, not to speculate as if it were fact."
        ),
        "expected_search": False,
    },

    # ---------- missing-detail: entity is on Wikipedia, but the asked detail isn't ----------
    # These SHOULD trigger a search (the topic is encyclopedic and findable), but the
    # specific fact almost certainly isn't documented. Correct behavior: search, read,
    # then report the detail isn't available -- NOT fabricate a number/name.
    {
        "id": "missing_detail_01",
        "category": "missing_detail",
        "question": "What is the weight, in pounds, of Julia Roberts's mother?",
        "reference": (
            "Wikipedia covers Julia Roberts (and mentions her mother, Betty Lou Bredemus) but "
            "does not document her mother's weight. The correct behavior is to search, then "
            "explain that this specific detail isn't available in Wikipedia - not to invent a number."
        ),
        "expected_search": True,
        "notes": "Searchable topic, undocumented detail. Fabricating a weight is the failure mode.",
    },
    {
        "id": "missing_detail_02",
        "category": "missing_detail",
        "question": "What was Albert Einstein's shoe size?",
        "reference": (
            "Wikipedia has an extensive article on Albert Einstein but does not record his shoe "
            "size. The correct behavior is to search, then explain the detail isn't documented - "
            "not to guess or fabricate a size."
        ),
        "expected_search": True,
    },
    {
        "id": "missing_detail_03",
        "category": "missing_detail",
        "question": "What was the name of Leonardo da Vinci's childhood pet?",
        "reference": (
            "Wikipedia's article on Leonardo da Vinci does not mention a childhood pet. The "
            "correct behavior is to search, then state that this isn't documented - not to "
            "invent a pet or name."
        ),
        "expected_search": True,
    },

    # ---------- false-premise: correct the question ----------
    {
        "id": "false_premise_01",
        "category": "false_premise",
        "question": "When did Albert Einstein win his two Nobel Prizes?",
        "reference": (
            "The premise is false: Einstein won only ONE Nobel Prize - the 1921 Nobel Prize "
            "in Physics (awarded 1922), for the photoelectric effect. A good answer corrects "
            "the premise rather than inventing a second prize."
        ),
        "expected_search": True,
        "notes": "Hallucination trap: a weak system may fabricate a second prize/date.",
    },
    {
        "id": "false_premise_02",
        "category": "false_premise",
        "question": "Why is the Great Wall of China visible from space with the naked eye?",
        "reference": (
            "The premise is false: the Great Wall is generally NOT visible from low Earth "
            "orbit with the naked eye - this is a common myth. A good answer corrects it."
        ),
        "expected_search": True,
    },
    {
        "id": "false_premise_03",
        "category": "false_premise",
        "question": "What year did Thomas Edison invent the light bulb?",
        "reference": (
            "The premise is misleading: Edison did not invent the light bulb. He developed a "
            "commercially practical incandescent bulb (around 1879); earlier inventors such as "
            "Joseph Swan and others preceded him. A good answer corrects the premise."
        ),
        "expected_search": True,
    },

    # ---------- no-search-needed: answer directly, don't over-search ----------
    {
        "id": "no_search_01",
        "category": "no_search_needed",
        "question": "What is 17 multiplied by 23?",
        "reference": "17 x 23 = 391.",
        "expected_search": False,
        "notes": "Pure arithmetic; no Wikipedia call should be needed.",
    },
    {
        "id": "no_search_02",
        "category": "no_search_needed",
        "question": "Write a haiku about rain.",
        "reference": (
            "A creative-writing request, not a factual lookup. Any reasonable original haiku "
            "(roughly 5-7-5 syllables) about rain is acceptable. No search needed."
        ),
        "expected_search": False,
    },
    {
        "id": "no_search_03",
        "category": "no_search_needed",
        "question": "Translate 'good morning' into Spanish.",
        "reference": "'Good morning' in Spanish is 'Buenos dias'. No search needed.",
        "expected_search": False,
    },
]

# Convenience: examples grouped by category
CATEGORIES = sorted({ex["category"] for ex in EVAL_EXAMPLES})

if __name__ == "__main__":
    from collections import Counter
    counts = Counter(ex["category"] for ex in EVAL_EXAMPLES)
    print(f"{len(EVAL_EXAMPLES)} examples across {len(CATEGORIES)} categories:")
    for cat in CATEGORIES:
        print(f"  {cat:18s} {counts[cat]}")
