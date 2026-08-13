"""
humanize.py — Strip AI-writing tells from assistant answers before display.

Applied to every chat reply (guest and authenticated) so seekers read prose
that sounds like a person rather than a language model.

Based on Wikipedia's "Signs of AI writing" (WikiProject AI Cleanup).

THE ONE HARD RULE
-----------------
Verbatim quotations are never touched. This product answers from the
authenticated Ramana Maharshi library, and silently rewording Bhagavan's
recorded words would be a far worse failure than any amount of AI phrasing.
Blockquotes and anything inside quotation marks are masked out before any
transformation runs and restored byte-for-byte afterwards.

Two layers work together:
  1. The system prompt (services/chat.py) prevents most patterns at generation
     time — free, and it produces genuinely better prose than any rewrite.
  2. This module deterministically cleans up what still slips through. No LLM
     call, so it adds no cost and no latency.
"""
from __future__ import annotations

import re

# ─────────────────────────────────────────────────────────────────────────────
# Quote protection
# ─────────────────────────────────────────────────────────────────────────────

# Sentinel that cannot occur in model output.
_MARK = "\x00H{}\x00"

_PROTECT_PATTERNS = [
    re.compile(r"^[ \t]*>[^\n]*$", re.MULTILINE),   # markdown blockquotes
    re.compile(r"\"[^\"\n]{0,800}\""),               # "straight quoted"
    re.compile(r"[“][^”\n]{0,800}[”]"),  # "curly quoted"
    re.compile(r"[‘][^’\n]{0,400}[’]"),  # 'curly single'
    re.compile(r"`[^`\n]{0,200}`"),                  # inline code / terms
]


def _mask(text: str) -> tuple[str, list[str]]:
    """Replace protected spans with sentinels. Returns (masked, originals)."""
    store: list[str] = []

    def _sub(m: re.Match) -> str:
        store.append(m.group(0))
        return _MARK.format(len(store) - 1)

    for pat in _PROTECT_PATTERNS:
        text = pat.sub(_sub, text)
    return text, store


def _unmask(text: str, store: list[str]) -> str:
    for i, original in enumerate(store):
        text = text.replace(_MARK.format(i), original)
    return text


# ─────────────────────────────────────────────────────────────────────────────
# Transformations (only ever applied to unprotected prose)
# ─────────────────────────────────────────────────────────────────────────────

# Emoji blocks only. Deliberately excludes U+0900–U+0DFF so Devanagari, Tamil,
# Telugu, Bengali and Malayalam text is never touched.
_EMOJI = re.compile(
    "[\U0001F300-\U0001FAFF\U0001F000-\U0001F2FF☀-➿️⬀-⯿]+"
)

# Formulaic praise of the question — classic chatbot sycophancy.
_SYCOPHANCY = [
    re.compile(r"(?i)\b(what a |such a )?(beautiful|wonderful|excellent|great|profound|thoughtful|lovely)\s+question[^.!?]*[.!?]\s*"),
    re.compile(r"(?i)^\s*(great|excellent|good|wonderful)\s+question[!.]?\s*", re.MULTILINE),
    re.compile(r"(?i)\bthank you for (this|your) (beautiful|wonderful|thoughtful|profound)?\s*question[^.!?]*[.!?]\s*"),
    re.compile(r"(?i)\byou('re| are) absolutely right[^.!?]*[.!?]\s*"),
    re.compile(r"(?i)\bwhat a (beautiful|wonderful|rich) (inquiry|enquiry)[^.!?]*[.!?]\s*"),
]

# Chatbot correspondence artifacts that should never reach a reader.
_ARTIFACTS = [
    re.compile(r"(?i)\s*i hope this helps[^.!?]*[.!?]"),
    re.compile(r"(?i)\s*let me know if[^.!?]*[.!?]"),
    re.compile(r"(?i)\s*would you like me to[^.!?]*[?]"),
    re.compile(r"(?i)^\s*(certainly|of course)[!,.]\s*", re.MULTILINE),
    re.compile(r"(?i)\s*feel free to ask[^.!?]*[.!?]"),
]

# Signposting — announcing instead of doing.
_SIGNPOSTS = [
    re.compile(r"(?i)\blet(?:'s| us) (dive in|dive into|explore|break this down|look at)\b[^.!?,]*[.,]?\s*"),
    re.compile(r"(?i)\bhere(?:'s| is) what you need to know[^.!?]*[.!?]\s*"),
    re.compile(r"(?i)\bwithout further ado[,]?\s*"),
    re.compile(r"(?i)\blet me share what[^.!?]*[.!?]\s*"),
]

# Filler and hedging. Order matters — longest first.
_PHRASES: list[tuple[re.Pattern, str]] = [
    (re.compile(r"(?i)\bit is important to note that\b\s*"), ""),
    (re.compile(r"(?i)\bit(?:'s| is) worth noting that\b\s*"), ""),
    (re.compile(r"(?i)\bdue to the fact that\b"), "because"),
    (re.compile(r"(?i)\bin order to\b"), "to"),
    (re.compile(r"(?i)\bat this point in time\b"), "now"),
    (re.compile(r"(?i)\bin the event that\b"), "if"),
    (re.compile(r"(?i)\bhas the ability to\b"), "can"),
    (re.compile(r"(?i)\bcould potentially possibly\b"), "may"),
    (re.compile(r"(?i)\bcould potentially\b"), "may"),
    # Copula avoidance
    (re.compile(r"(?i)\bserves as\b"), "is"),
    (re.compile(r"(?i)\bstands as\b"), "is"),
    (re.compile(r"(?i)\bfunctions as\b"), "is"),
    # Significance inflation
    (re.compile(r"(?i)\bplays a (crucial|vital|pivotal|key) role in\b"), "matters in"),
    (re.compile(r"(?i)\bis a testament to\b"), "shows"),
    (re.compile(r"(?i)\bstands as a testament to\b"), "shows"),
    # AI vocabulary. Kept deliberately short: words like "profound", "stillness"
    # and "enduring" are legitimate in Ramana's context and are NOT stripped.
    (re.compile(r"(?i)\bdelve into\b"), "look at"),
    (re.compile(r"(?i)\bdelving into\b"), "looking at"),
    # NOTE: negative parallelism ("it's not just X, it's Y") is deliberately
    # NOT rewritten here. Every regex form of it inverts the meaning — an
    # earlier version turned "not just about technique" into "about
    # technique", the opposite of what Bhagavan taught. The system prompt
    # discourages the construction at generation time instead, which is the
    # only safe place to handle it.
    # Persuasive authority tropes
    (re.compile(r"(?i)\bthe real question is\b"), "the question is"),
    (re.compile(r"(?i)\bat its core,\s*"), ""),
    (re.compile(r"(?i)\bat the heart of the matter,\s*"), ""),
]


def _strip_em_dashes(text: str) -> str:
    """Replace em/en dashes used as sentence punctuation.

    Kept out of quotations by the masking layer, so Bhagavan's recorded
    punctuation survives intact.

    A comma is the usual replacement, but a *single* dash in a clause that
    already carries commas produces a splice ("without the ego, in sleep, the
    ego does not exist"). In that case a full stop reads better, so the
    sentence is split and the next word capitalised.
    """
    def _fix_sentence(sentence: str) -> str:
        dashes = len(re.findall(r"[—―]", sentence))
        if dashes == 0:
            return sentence
        # Paired dashes are parenthetical: commas keep the aside intact.
        if dashes % 2 == 0:
            return re.sub(r"\s*[—―]\s*", ", ", sentence)
        # Single dash. If what FOLLOWS already carries commas, another comma
        # produces a splice, so prefer a full stop — but only when the tail can
        # stand as its own sentence. A tail opening with a participle ("turning
        # inward, silently") is a phrase, not a clause, and splitting it would
        # leave a fragment.
        head, _, tail = sentence.partition(re.search(r"[—―]", sentence).group(0))
        tail = tail.lstrip()
        first = re.match(r"[A-Za-z']+", tail)
        starts_with_participle = bool(first) and first.group(0).lower().endswith("ing")

        if "," in tail and tail and not starts_with_participle and head.strip():
            tail = tail[:1].upper() + tail[1:]
            return head.rstrip().rstrip(",") + ". " + tail
        return re.sub(r"\s*[—―]\s*", ", ", sentence)

    # Process sentence by sentence so the comma count is judged locally.
    parts = re.split(r"(?<=[.!?])\s+", text)
    text = " ".join(_fix_sentence(p) for p in parts)

    # En dash used as an em dash (spaced). Numeric ranges (5–10) stay.
    text = re.sub(r"(?<=[A-Za-z,])\s+[–]\s+(?=[A-Za-z])", ", ", text)
    return text


def _tidy_punctuation(text: str) -> str:
    """Clean artifacts created by the substitutions above."""
    text = re.sub(r",\s*,+", ",", text)          # ",," -> ","
    text = re.sub(r",\s*([.!?;:])", r"\1", text)  # ", ." -> "."
    text = re.sub(r"\s+([.,!?;:])", r"\1", text)  # " ," -> ","
    text = re.sub(r"([.!?])\s*,", r"\1", text)    # ". ," -> "."
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Capitalise after a sentence end if a substitution lowercased the start.
    text = re.sub(
        r"(^|[.!?]\s+)([a-z])",
        lambda m: m.group(1) + m.group(2).upper(),
        text,
    )
    return text.strip()


def humanize_response(text: str) -> str:
    """Remove AI-writing tells while preserving every verbatim quotation."""
    if not text or not text.strip():
        return text

    original = text
    try:
        text, store = _mask(text)

        text = _EMOJI.sub("", text)

        # Curly to straight quotes. Safe everywhere: changes punctuation glyphs,
        # never words. (Quoted spans are masked, so this only affects stray marks.)
        text = text.replace("’", "'").replace("‘", "'")
        text = text.replace("“", '"').replace("”", '"')

        for pat in _SYCOPHANCY:
            text = pat.sub("", text)
        for pat in _ARTIFACTS:
            text = pat.sub("", text)
        for pat in _SIGNPOSTS:
            text = pat.sub("", text)
        for pat, repl in _PHRASES:
            text = pat.sub(repl, text)

        text = _strip_em_dashes(text)

        # Mechanical boldface. A conversational reply is not a document; when
        # the model bolds three or more fragments it is decorating, not
        # emphasising, so the markers are dropped.
        if len(re.findall(r"\*\*[^*\n]+\*\*", text)) >= 3:
            text = re.sub(r"\*\*([^*\n]+)\*\*", r"\1", text)

        text = _tidy_punctuation(text)

        text = _unmask(text, store)

        # Never return an empty or gutted answer: if the filters removed most
        # of the reply, something matched too greedily, so keep the original.
        if len(text.strip()) < max(20, int(len(original.strip()) * 0.5)):
            return original
        return text
    except Exception:
        # Presentation polish must never cost a seeker their answer.
        return original
