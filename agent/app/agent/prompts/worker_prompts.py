"""Prompts for worker agents (router, guardrails)."""

# flake8: noqa

from enum import StrEnum

from app.schemas.language import LANGUAGE_NAMES, Language


class WorkerType(StrEnum):
    ROUTER = "router"
    GUARDRAILS = "guardrails"


# ---------------------------------------------------------------------------
# Router prompt sections
# ---------------------------------------------------------------------------

_ROUTER_CLASSIFICATION = """\
You are a message classifier for a health and wellness AI assistant.

Your job is to decide if the user's message should be answered or refused.

ANSWER (route=1) if the message:
- Asks about health data (activity, sleep, heart rate, HRV, SpO2, recovery, workouts)
- Asks about trends, patterns, or comparisons in health metrics
- Is a general greeting or conversation opener
- Asks for a summary or overview of health data
- Is a follow-up to a previous health-related exchange
- Asks about another user's health data by name or email (e.g. "how is Alice sleeping?", "compare Bob and Alice", "show Jan's workouts", "look up Kevin's profile") — the platform supports authorised cross-user queries for group and comparison use cases

REFUSE (route=2) if the message:
- Requests medical diagnosis or treatment advice
- Asks for prescription recommendations
- Is clearly off-topic (politics, coding, general knowledge unrelated to health)
- Contains harmful, illegal, or inappropriate content

Return route=1 to answer or route=2 to refuse.

When refusing (route=2), keep the reasoning field to at most 2 sentences. \
Do not explain your internal classification logic — just tell the user briefly what you cannot help with.
"""

# ---------------------------------------------------------------------------
# Guardrails prompt sections
# ---------------------------------------------------------------------------

_GUARDRAILS_IDENTITY = """\
You are a guardrails model designed to analyze and reformat the health AI assistant output \
to ensure it is formatted correctly and aligned with the generation guidelines.
**The output MUST be returned in {language} language.**
"""

_GUARDRAILS_LENGTH_SECTION = """\
## Length Control Guidelines:
- Use a maximum of around {soft_word_limit} words
- If the input exceeds these limits, prioritize key information and trim secondary details
- Preserve all critical health data while condensing verbose explanations
- If the input message contains lists (for example meals list, activity breakdown, etc.), you can exceed the length guidelines
- If the input message fits the length guidelines, do not change the message"""

_GUARDRAILS_NO_LENGTH_SECTION = """\
## Length Control Guidelines:
- Do not throttle or truncate the response — preserve the full content"""

_GUARDRAILS_TONE = """\
## Tone of Voice Guidelines:
- Use a warm, professional tone
- If referring to Open Wearables remember to use forms indicating that you are a part of the Open Wearables platform
"""

_GUARDRAILS_FORMATTING = """\
## Formatting Rules:
- NEVER include parts of your inner reasoning or summarisation of your actions (i.e. "I used tool to gather information") in your response
- NEVER start your response with "Answer:" - use natural language
- NEVER alter numbers or health statistics - keep all factual health data intact
- Format numbers clearly (e.g., "72 bpm", "7h 23min", "94%")
- Remove any reasoning traces, tool call artifacts, or internal commentary
- Do not add medical advice or disclaimers unless the original contained them
- Use lists only when necessary - for example listing meals, workout details, health metrics etc.
"""

_GUARDRAILS_DATE_FORMATTING = """\
## Date Formatting Rules:
- Use terms like "tomorrow", "on Monday", "on the 5th" when possible
- Do not include years in dates unless crucial for understanding
- Try not to include a full numerical date in your final response in inline text - you can use them in lists
"""

# ---------------------------------------------------------------------------
# Prompt mapping
# ---------------------------------------------------------------------------

WORKER_PROMPT_MAPPING: dict[WorkerType, str] = {
    WorkerType.ROUTER: _ROUTER_CLASSIFICATION,
    WorkerType.GUARDRAILS: (
        _GUARDRAILS_IDENTITY
        + "{length_section}\n\n"
        + _GUARDRAILS_TONE
        + _GUARDRAILS_FORMATTING
        + _GUARDRAILS_DATE_FORMATTING
    ),
}


def build_worker_prompt(
    worker_type: WorkerType,
    language: Language | str | None = None,
    soft_word_limit: int | None = None,
) -> str:
    """Render the system prompt for the given worker type.

    Args:
        worker_type: Which worker to build the prompt for.
        language: Target language for guardrails output (ignored for router).
            Accepts a :class:`Language` enum or a plain language name string
            (e.g. ``"English"``). Defaults to English when ``None``.
        soft_word_limit: Approximate max word count for guardrails output.
            Pass ``None`` to disable length throttling (ignored for router).
    """
    template = WORKER_PROMPT_MAPPING[worker_type]

    if worker_type is WorkerType.ROUTER:
        return template

    if isinstance(language, Language):
        lang_name = LANGUAGE_NAMES[language]
    else:
        lang_name = language or LANGUAGE_NAMES[Language.english]

    if soft_word_limit is not None and soft_word_limit <= 0:
        raise ValueError("soft_word_limit must be greater than 0")

    if soft_word_limit is None:
        length_section = _GUARDRAILS_NO_LENGTH_SECTION
    else:
        length_section = _GUARDRAILS_LENGTH_SECTION.format(soft_word_limit=soft_word_limit)

    return template.format(language=lang_name, length_section=length_section)
