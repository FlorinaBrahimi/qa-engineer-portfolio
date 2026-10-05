"""Deterministic similarity scoring used by the Submission Service.

The score is the percentage of 5-word shingles in the submitted text that also appear in
the known corpus. It is intentionally simple so tests can predict exact outcomes.
"""
from __future__ import annotations

import re

SHINGLE_SIZE = 5

KNOWN_CORPUS = [
    "The mitochondria is the powerhouse of the cell and produces energy through respiration",
    "To be or not to be that is the question whether tis nobler in the mind to suffer",
    "Academic integrity is the commitment to honesty trust fairness respect and responsibility",
]


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def _shingles(tokens: list[str], size: int = SHINGLE_SIZE) -> set[tuple[str, ...]]:
    if len(tokens) < size:
        return {tuple(tokens)} if tokens else set()
    return {tuple(tokens[i : i + size]) for i in range(len(tokens) - size + 1)}


_CORPUS_SHINGLES: set[tuple[str, ...]] = set()
for _doc in KNOWN_CORPUS:
    _CORPUS_SHINGLES |= _shingles(_tokens(_doc))


def word_count(text: str) -> int:
    return len(_tokens(text))


def similarity_score(text: str) -> float:
    """Return 0.0 to 100.0: share of the text's shingles found in the corpus."""
    shingles = _shingles(_tokens(text))
    if not shingles:
        return 0.0
    matched = len(shingles & _CORPUS_SHINGLES)
    return round(100.0 * matched / len(shingles), 1)


def similarity_band(score: float) -> str:
    """Colour band used by similarity reports: blue (no match), green, yellow, orange, red."""
    if score <= 0.0:
        return "blue"
    if score < 25.0:
        return "green"
    if score < 50.0:
        return "yellow"
    if score < 75.0:
        return "orange"
    return "red"
