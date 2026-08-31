"""
legacy_script.py — remove legacy-encoded Tamil from retrieved text.

WHY THIS EXISTS
---------------
Some PDFs in the corpus set their Tamil in Bamini, a pre-Unicode font that maps
Tamil letters onto ASCII code points. Extracting text from those PDFs yields the
ASCII bytes, not Tamil, so a verse comes out as:

    ehndDQ; nrhw;nghU shkJ ehSNk ehdw;w J}f;fj;J Ke;jPgw

That is not Tamil to anyone reading it and not meaningful to the model either.
It was appearing verbatim in answers, ahead of the English translation.

WHAT THIS DOES NOT DO
---------------------
It does not touch real Unicode Tamil. The site answers in Tamil, and Unicode
Tamil chunks are legitimate content. Every rule here is ASCII-only, so text in
any real script passes through untouched. It also does not attempt to convert
Bamini to Unicode: that mapping is lossy in places, and silently guessing at
scripture is worse than omitting a line the reader could not have read anyway.

HOW IT DECIDES
--------------
The unmistakable signature of Bamini is a semicolon inside a word
("nrhw;nghU"). It encodes the pulli, and no English word does it. Nothing is
removed from a line that has no such anchor, which is what keeps ordinary
English safe.

Once a line IS anchored, the question is how far the damage extends, and the
first version of this got that wrong. It grew the span only over tokens with
their own visible marker (a semicolon, a brace, a mid-word capital), so a real
verse line

    vz;ZU ahT kpiwAU thnkd ntz;zp topgl Ye;jPgw tPrdw; g+rid Ae;jPgw

kept "thnkd", "topgl" and "g+rid", which carry no marker at all. The test is
now the other way round: a token is suspect unless it LOOKS like English, that
is unless it is ordinary letters, capitalised only at the front, with a vowel
in it. "thnkd" has no vowel; "g+rid" is not letters; "ahT" capitalises in the
middle. All three are caught.

Anchored lines are then judged as a whole. If most of the line fails the
English test the entire line goes, which is the common case because these PDFs
put the Tamil on its own line. If most of it passes, only the run around each
anchor is removed, so an English sentence with a Tamil phrase set into it keeps
its English.
"""
from __future__ import annotations

import re

# A semicolon or brace wedged between two ASCII letters. The anchor.
_ANCHOR = re.compile(r"[A-Za-z][;}{\[\]][A-Za-z]")

# Ordinary English: letters, capitalised at the front only, or an acronym.
_ENGLISH_SHAPE = re.compile(r"^(?:[A-Za-z][a-z']*|[A-Z]{2,})$")
_VOWELS = set("aeiouyAEIOUY")

# Below this share of English-looking words, an anchored line is dropped whole.
_ENGLISH_SHARE_TO_KEEP_LINE = 0.5

_STRIP = ".,:!?()\"'`*_-–—“”‘’"


def _core(token: str) -> str:
    return token.strip(_STRIP)


def _is_anchor(token: str) -> bool:
    return bool(_ANCHOR.search(token))


def _is_neutral(token: str) -> bool:
    """Digits and bare punctuation: evidence for neither side."""
    core = _core(token)
    return not core or not any(ch.isalpha() for ch in core)


def _looks_english(token: str) -> bool:
    core = _core(token)
    if not core or not core.isascii():
        # Non-ASCII means a real script. Always treated as legitimate.
        return True
    if not _ENGLISH_SHAPE.match(core):
        return False
    return any(ch in _VOWELS for ch in core)


def _clean_line(line: str) -> str:
    tokens = line.split(" ")
    if not any(_is_anchor(t) for t in tokens):
        return line

    judged = [t for t in tokens if not _is_neutral(t)]
    if judged:
        share = sum(1 for t in judged if _looks_english(t)) / len(judged)
        if share < _ENGLISH_SHARE_TO_KEEP_LINE:
            # Mostly not English: this is a verse line, drop it entirely.
            return ""

    # Mostly English with Tamil set into it. Remove only the runs.
    drop = [False] * len(tokens)
    for i, tok in enumerate(tokens):
        if not _is_anchor(tok):
            continue
        drop[i] = True
        for step in (-1, 1):
            j = i + step
            while 0 <= j < len(tokens):
                t = tokens[j]
                if not t.strip():
                    j += step
                    continue
                if _looks_english(t) or _is_neutral(t):
                    break
                drop[j] = True
                j += step

    cleaned = " ".join(t for t, d in zip(tokens, drop) if not d)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


def strip_legacy_tamil(text: str) -> str:
    """Remove Bamini-encoded runs, leaving the surrounding English intact."""
    if not text or ";" not in text:
        # The anchor requires a semicolon. No semicolon, nothing to do, and
        # this is the overwhelmingly common case.
        return text

    out = []
    for line in text.split("\n"):
        cleaned = _clean_line(line)
        if cleaned or not line.strip():
            out.append(cleaned)

    result = "\n".join(out)
    return re.sub(r"\n{3,}", "\n\n", result).strip()
