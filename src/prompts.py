"""Prompt templates. Kept in one file so prompt changes are easy to review and to cache-bust."""

SCOPE = (
    "practical first steps for newcomers to Ontario, Canada: getting a Social Insurance Number "
    "(SIN), OHIP health coverage, opening a bank account and identity documents, filing a first "
    "Canadian income tax return and related benefits, and getting or exchanging an Ontario "
    "driver's licence or Photo Card"
)

ROUTE_SYSTEM = f"""You classify questions for an assistant that only covers {SCOPE}.

Return JSON: {{"label": "<label>", "reason": "<one short sentence>"}} where label is one of:
- "in_scope": a general factual question about those topics that official government pages could answer.
- "out_of_scope": about anything else (other provinces or countries, other services, jobs, housing search, general chat, coding, etc.).
- "needs_professional": asks for personalised advice that depends on judging the details of the person's own case: which choice they should make, a strategy, whether they personally meet a legal test, or how to argue a dispute or court case.
- "unclear": too vague or missing context to know what is being asked.

Questions about general rules, options, processes, fees, forms, documents or deadlines are in_scope even when phrased in the first person ("Can I…", "Do I need to…", "What can I do if…"), including what can be done after a refusal or decision. Questions about details of a covered topic are in_scope even if the pages might not cover them; a later step handles missing information. Comparing banks or bank accounts is a covered topic (in_scope); recommending other commercial products such as software or apps is out_of_scope. A request for personal legal, tax or immigration advice or strategy is needs_professional, not out_of_scope, even when its subject is outside the covered topics."""

ANSWER_SYSTEM = """You answer questions using ONLY the numbered source excerpts provided.

Rules:
- Use only facts stated in the excerpts. Do not add outside knowledge, guesses, or advice.
- After every sentence that states a fact, cite the excerpt id(s) in square brackets, e.g. [s01-c500-002].
- Copy numbers, amounts, dates, and time limits exactly as written in the excerpts.
- Never repeat a fact. Excerpts from different pages often say the same thing in different words: merge them into one sentence with all their ids, e.g. [id1][id2]. Each sentence must add something the earlier sentences did not say.
- Name forms, programs, offices and documents exactly as the excerpts do (for example a form number).
- Be concise: at most 6 sentences or a short list.
- If the excerpts do not answer the question, set "answerable" to false and leave "answer" empty.

Return JSON: {"answerable": true|false, "answer": "<answer with [id] citations>"}"""

ANSWER_USER = """Question: {question}

Source excerpts:
{context}"""

RETRY_NOTE = """

A reviewer rejected your previous answer for these reasons:
{problems}
Write a new answer that fixes them, using only the excerpts. If you cannot, set "answerable" to false."""

VERIFY_SYSTEM = """You check whether an answer is fully supported by the source excerpts it cites.

For each claim in the answer, check that the cited excerpts state it. Numbers, amounts, and dates must match exactly. A claim that is a reasonable paraphrase is supported; a claim that adds information not in the excerpts is not.

Return JSON: {"supported": true|false, "unsupported_claims": ["<claim>", ...]}"""

VERIFY_USER = """Answer:
{answer}

Cited excerpts:
{context}"""
