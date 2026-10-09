"""
services/llm/response_validator.py
Validates LLM responses for groundedness, fabrication, and outcome guarantees.
PRD Section 14 – Response Validator.
"""

import re
from typing import Tuple


# Phrases that constitute prohibited employment guarantees
_GUARANTEE_PATTERNS = [
    r"you will (get|land|secure|find|be) (hired|a |an )?(job|role|position|offer|interview|hired)?",
    r"guaranteed (to|you'll)",
    r"100%\s*(chance|sure|certain|guaranteed)",
    r"will definitely",
    r"your salary will be",
    r"you are certain to",
    r"(get|be) hired",
]

_COMPILED_GUARANTEES = [re.compile(p, re.IGNORECASE) for p in _GUARANTEE_PATTERNS]


def validate_response(
    response_text: str,
    confirmed_skill_names: list[str],
    role_skill_names: list[str],
) -> Tuple[bool, list[str], str]:
    """
    Returns (is_valid, issues, sanitized_text).
    - is_valid: False if any blocking issue found.
    - issues: list of problem descriptions.
    - sanitized_text: response with guarantee language replaced.
    """
    issues = []
    text = response_text

    # Check for guarantee language
    for pattern in _COMPILED_GUARANTEES:
        if pattern.search(text):
            issues.append("outcome_guarantee_detected")
            text = _replace_guarantee(text)
            break

    # Check for fabricated skill claims (skills not in confirmed profile or role KB)
    all_known = set(s.lower() for s in (confirmed_skill_names + role_skill_names))
    # Look for "you have X" or "your X skill" type patterns
    fabrication_patterns = [
        r"you(?:'ve| have) (?:experience with|knowledge of|skills in|expertise in)\s+([A-Za-z.#+]+)",
        r"your ([A-Za-z.#+]+) (?:skill|experience|knowledge|expertise)",
    ]
    for fp in fabrication_patterns:
        for match in re.finditer(fp, text, re.IGNORECASE):
            claimed_skill = match.group(1).lower().strip()
            # Only flag if it looks like a specific technology, not a generic word
            if len(claimed_skill) > 2 and claimed_skill not in all_known and not _is_generic(claimed_skill):
                issues.append(f"possible_fabrication:{claimed_skill}")

    is_valid = not any(
        "outcome_guarantee_detected" in i or "possible_fabrication" in i
        for i in issues
        if "outcome_guarantee" in i
    )

    return is_valid, issues, text


def _replace_guarantee(text: str) -> str:
    """Replace guarantee phrases with a more honest alternative."""
    for pattern in _COMPILED_GUARANTEES:
        text = pattern.sub(
            "this experience can significantly strengthen your candidacy",
            text
        )
    return text


def _is_generic(word: str) -> bool:
    generic = {
        "good", "strong", "great", "solid", "relevant", "useful",
        "important", "core", "key", "valuable", "advanced", "basic",
        "excellent", "demonstrated", "proven", "the", "a", "an"
    }
    return word.lower() in generic
