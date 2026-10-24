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
- "needs_professional": asks for advice on the person's own legal, tax, or immigration situation, a strategy, a judgment about their status, or help with a dispute, appeal, or court matter.
- "unclear": too vague or missing context to know what is being asked.

Questions asking for a general rule or fact (fees, documents, eligibility rules, deadlines) are in_scope even when phrased in the first person."""

ANSWER_SYSTEM = """You answer questions using ONLY the numbered source excerpts provided.

Rules:
- Use only facts stated in the excerpts. Do not add outside knowledge, guesses, or advice.
- After every sentence that states a fact, cite the excerpt id(s) in square brackets, e.g. [s01-c500-002].
- Copy numbers, amounts, dates, and time limits exactly as written in the excerpts.
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
