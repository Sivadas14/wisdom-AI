"""
legacy_script.py — keep the English, drop the gibberish, in retrieved text.

WHY THIS EXISTS
---------------
Corpus PDFs carry two kinds of text that mean nothing to a reader of the
answer:

  1. Non-Latin script. Tamil, Devanagari and the rest. The corpus books are in
     English and the answer is written in English (or translated by the model
     into the seeker's language), so the original script contributes nothing to
     the passage and only crowds the context.

  2. Gibberish that looks like ASCII. Several PDFs set their Tamil in Bamini, a
     pre-Unicode font that maps Tamil letters onto ASCII code points, so
     extraction returns things like

         ehndDQ; nrhw;nghU shkJ ehSNk ehdw;w J}f;fj;J Ke;jPgw

     which is not Tamil, not English, and not readable by anyone. It was being
     served at the top of the verse 21 answer.

The rule is simply: if it is not English, drop it.

WHAT MUST SURVIVE
-----------------
The hard part is not spotting gibberish, it is not mistaking the vocabulary of
these texts FOR gibberish. "vichara", "jnani", "Bhagavan", "Arunachala",
"Muruganar", "I-I", "self-enquiry" and "Upadeśa Sāram" all have to come
through untouched. Losing a word of the teaching is a far worse failure than
leaving a stray token of Bamini, so every rule here errs towards keeping.

That is why diacritics count as English: "Sāram" and "Ātman" are scholarly
transliteration, not another script. And why a token is judged on its shape
rather than against a word list: no list would contain "Ramanasramam".
"""
from __future__ import annotations

import re

# Letters allowed in "English": ASCII, Latin-1, Latin Extended-A/B (through
# U+024F) and Latin Extended Additional (U+1E00–U+1EFF, the IAST diacritics
# used to transliterate Sanskrit). Anything alphabetic outside these is
# another script.
_LATIN_MAX = 0x024F
_LATIN_ADDITIONAL = range(0x1E00, 0x1F00)

# Shape of an ordinary English word part: capitalised at the front, or an
# acronym. "ahT" and "shkJ" fail this; "Bhagavan" and "UPADESA" pass.
_WORD_SHAPE = re.compile(r"^(?:[A-Za-z][a-z]*|[A-Z]+)$", re.UNICODE)
_VOWELS = set("aeiouyAEIOUY")

_PUNCT = ".,:!?()[]{}\"'`*_;–—“”‘’…"
# Words are split on these before shape-testing, so "I-I", "self-enquiry",
# "Bhagavan's" and "e.g." are judged by their parts. The full stop has to be
# in here: without it "e.g." was read as one malformed word and deleted from
# the middle of English sentences.
_SPLIT_INSIDE = re.compile(r"[-'’/.]")

# An all-capitals run is an acronym, and acronyms are allowed to have no
# vowel. Without this exemption "LLM", "PDF" and "USA" were treated as
# gibberish and dropped.
_ACRONYM = re.compile(r"^[A-Z]+$")

# An acronym given a plural or possessive: "URLs", "CTAs", "PDFs".
_ACRONYM_PLURAL = re.compile(r"^[A-Z]{2,}s$")

# CamelCase names: "OpenAI", "ChatGPT", "FastAPI", "WisdomAI". The leading
# capital followed by lower case is what makes this safe to allow — Bamini
# tokens with mid-word capitals ("ahT", "shkJ", "kpiwAU") start in lower
# case, so none of them match.
_CAMEL_CASE = re.compile(r"^[A-Z][a-z]+(?:[A-Z][a-z]*)+$")

# The lower-camel form: "eBooks", "iPhone". Safe for the same reason — the
# capital falls on the SECOND character, and no Bamini token does that.
_LOWER_CAMEL = re.compile(r"^[a-z][A-Z][a-z]+$")

# A web address. Splitting one on its dots and slashes left fragments that
# failed the shape test and took the whole address with them.
_URL = re.compile(r"^(?:[a-z]+://|www\.)", re.I)

# Anything mixing letters and digits: "MP3", "21st", "v2". Bamini is pure
# letters and punctuation, so digits are a reliable sign of real text.
_HAS_DIGIT = re.compile(r"\d")

# Real English abbreviations with no vowel. Exempting these by NAME rather
# than by length is deliberate: a blanket "short words are fine" rule let
# "vz", "Mk" and "vd" through, and that was enough to push a Bamini verse
# line back over the English majority threshold and keep the whole line.
_VOWELLESS_BUT_REAL = {
    "px", "js", "ts", "vs", "th", "st", "nd", "rd", "km", "cm", "mm",
    "kg", "ml", "hr", "mr", "mrs", "dr", "ft", "tv", "pc", "ok", "bc",
    "ad", "pm", "am", "www",
    # File types and technology names, which show up in notes and appendices.
    "pdf", "txt", "csv", "xml", "css", "sql", "jpg", "png", "gif", "ppt",
    "gpt", "url", "aws", "https", "com", "org", "net", "mp",
}

# An anchored line is dropped whole below this share of English words.
_ENGLISH_SHARE_TO_KEEP_LINE = 0.5
_MIN_WORDS_TO_JUDGE_A_LINE = 2


def _is_non_latin_letter(ch: str) -> bool:
    if not ch.isalpha():
        return False
    code = ord(ch)
    return code > _LATIN_MAX and code not in _LATIN_ADDITIONAL


def strip_non_latin(text: str) -> str:
    """Remove runs of non-Latin script, along with their combining marks."""
    out = []
    for ch in text:
        if _is_non_latin_letter(ch):
            continue
        # Combining marks belong to the letter they follow; if that letter
        # went, so do they.
        if ch.isspace() or ch.isascii() or ch.isalnum() or ch in _PUNCT:
            out.append(ch)
        elif not ch.isalpha():
            # Script-specific punctuation such as danda. Only kept if Latin.
            if ord(ch) <= _LATIN_MAX:
                out.append(ch)
        else:
            out.append(ch)
    return "".join(out)


def _looks_english(token: str) -> bool:
    core = token.strip(_PUNCT)
    if not core:
        return True  # bare punctuation is not evidence either way
    if not core.isascii():
        # Latin with diacritics. Transliteration, so English for our purposes.
        return True
    if _URL.match(core):
        return True
    parts = [p for p in _SPLIT_INSIDE.split(core) if p]
    if not parts:
        return True
    return all(_part_looks_english(p) for p in parts)


def _part_looks_english(part: str) -> bool:
    """Judge one piece of a token.

    Applied per PART rather than to the whole token, because "ChatGPT-like"
    splits into "ChatGPT" and "like", and testing only the joined form threw
    away the ordinary English word "like" along with the brand name.
    """
    if not any(ch.isalpha() for ch in part):
        return True  # a number or symbol inside a hyphenated token
    if _HAS_DIGIT.search(part):
        return True
    if (_CAMEL_CASE.match(part) or _ACRONYM_PLURAL.match(part)
            or _LOWER_CAMEL.match(part)):
        return True
    if not _WORD_SHAPE.match(part):
        return False
    if _ACRONYM.match(part):
        return True
    if part.lower() in _VOWELLESS_BUT_REAL:
        return True
    if len(part) > 1 and not any(ch in _VOWELS for ch in part):
        # "thnkd", "vz", "ntz". No English word of length 2+ lacks a vowel.
        return False
    return True


def _is_neutral(token: str) -> bool:
    """Digits and bare punctuation: evidence for neither side."""
    core = token.strip(_PUNCT)
    return not core or not any(ch.isalpha() for ch in core)


def _clean_line(line: str) -> str:
    tokens = line.split(" ")
    judged = [t for t in tokens if not _is_neutral(t)]
    if len(judged) < _MIN_WORDS_TO_JUDGE_A_LINE:
        return line

    english = sum(1 for t in judged if _looks_english(t))
    if english / len(judged) < _ENGLISH_SHARE_TO_KEEP_LINE:
        # Mostly not English. This is a verse line or a word-by-word gloss;
        # drop it whole. This is the case that actually occurs, because these
        # PDFs put the original script on its own line.
        return ""

    # Mostly English, so only remove the words that are clearly not. If
    # nothing needs removing, hand the line back exactly as it came: there is
    # no reason for this function to be reflowing whitespace in passages it
    # has no quarrel with.
    kept = [t for t in tokens if _is_neutral(t) or _looks_english(t)]
    if len(kept) == len(tokens):
        return line
    return re.sub(r"\s{2,}", " ", " ".join(kept)).strip()


def strip_legacy_tamil(text: str) -> str:
    """Keep the English in a passage and drop the rest.

    Named for the case that prompted it. Handles non-Latin script and
    ASCII-encoded gibberish alike.
    """
    if not text:
        return text

    out = []
    for line in strip_non_latin(text).split("\n"):
        cleaned = _clean_line(line)
        if cleaned or not line.strip():
            out.append(cleaned)

    return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()


# The name says what it does; the old one says where it came from.
keep_english_only = strip_legacy_tamil
