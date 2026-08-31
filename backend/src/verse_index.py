"""
verse_index.py — verse-aware chunking and lookup for numbered works.

WHY THIS EXISTS
---------------
Retrieval is semantic. "Explain verse 21 of Upadesa Saram" embeds essentially
as "Upadesa Saram" plus "explain": the number 21 carries almost no semantic
weight, so the nearest neighbours are the book's contents page and opening
verses. Asking for a verse by number is a lookup, not a similarity problem, and
dense vectors are the wrong instrument for it.

For works that are actually numbered, we can do better. At ingestion we regroup
the page chunks into VERSE chunks, label each one, and put the verse number into
the embedded text as well. At query time a "verse N" question is answered by a
direct lookup on that label, with the usual vector search still running
alongside for context.

This deliberately covers only works whose verse structure has been VERIFIED
against the indexed text. A generic "find a number in a heading" rule would
mislabel tables of contents, footnotes and page numbers.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple


# ── Registry of numbered works ───────────────────────────────────────────────
# `filename` matches the uploaded source. `heading` must match the real heading
# form in the extracted text, NOT a table-of-contents entry. In the Rajiv Kapur
# edition of Upadesa Saram the verses appear as markdown headings ("## Verse 21")
# while the contents page lists them in italics ("_Verse 21_ 128"), so anchoring
# to a heading at the start of a line excludes the contents page cleanly.

@dataclass(frozen=True)
class Work:
    key: str
    title: str
    filename: re.Pattern
    heading: re.Pattern
    expected_verses: int
    # Some editions print prefatory verses with their OWN numbering before the
    # main text starts. Counting from the top would then attach the wrong
    # numbers to everything. When set, verse counting only begins on the page
    # where this matches.
    start_after: Optional[re.Pattern] = None


WORKS: tuple[Work, ...] = (
    # Michael James / Sri Muruganar lineage edition. Verses are numbered "1."
    # under a markdown heading, NOT "## Verse 1". Crucially the Payiram
    # (prefatory verses) are numbered 1-6 before the main text, so counting
    # starts only at the "Nul - Text" marker; a benedictory appendix restarts at
    # 1 after verse 30 and is rejected by the strictly-increasing rule.
    Work(
        key="upadesa-saram",
        title="Upadesa Saram",
        filename=re.compile(r"upadesa[_\s-]*undiyar", re.I),
        heading=re.compile(r"^#{1,6}\s*\**\s*(\d{1,2})\.\s", re.M),
        expected_verses=30,
        start_after=re.compile(r"Nul\s*[\u2013-]\s*Text|E\}y;", re.I),
    ),
    Work(
        key="upadesa-saram",
        title="Upadesa Saram",
        filename=re.compile(r"upadesa[_\s-]*saram|upadesa[_\s-]*undiyar", re.I),
        heading=re.compile(r"^#{1,6}\s*Verse\s+(\d{1,3})\b", re.I | re.M),
        expected_verses=30,
    ),
    Work(
        key="ulladu-narpadu",
        title="Forty Verses on Reality",
        filename=re.compile(r"40\s*verses|forty\s*verses|ulladu[_\s-]*narpadu", re.I),
        heading=re.compile(r"^#{1,6}\s*(?:Verse|Vs\.?)\s+(\d{1,3})\b", re.I | re.M),
        expected_verses=40,
    ),
)

# Aliases people actually type, mapped to a work key.
_QUERY_ALIASES: tuple[tuple[re.Pattern, str], ...] = (
    (re.compile(r"upadesa\s*(saram|saara|undiyar)", re.I), "upadesa-saram"),
    (re.compile(r"(ulladu\s*narpadu|forty\s*verses|40\s*verses)", re.I), "ulladu-narpadu"),
)

# Roughly the embedding model's ceiling, with headroom. A verse plus its
# commentary can run to twenty pages (Upadesa Saram verse 10 carries the whole
# Ashtanga Yoga section), which would exceed the limit as a single chunk.
_MAX_TOKENS_PER_CHUNK = 6000


def identify_work(source_name: str) -> Optional[Work]:
    """Return the Work this filename belongs to, or None."""
    if not source_name:
        return None
    for w in WORKS:
        if w.filename.search(source_name):
            return w
    return None


def _page_no(loc: str) -> Optional[int]:
    m = re.search(r"(\d+)", loc or "")
    return int(m.group(1)) if m else None


def _count_tokens(text: str) -> int:
    try:
        import tiktoken
        return len(tiktoken.get_encoding("cl100k_base").encode(text))
    except Exception:
        # Cheap fallback: about four characters per token.
        return len(text) // 4


def regroup_by_verse(chunks: list, source_name: str) -> Optional[list]:
    """Label each page of a numbered work with the verse it belongs to.

    Pages are NOT merged into one chunk per verse. An early version did that,
    and it traded one problem for another: Upadesa Saram verse 10 carries the
    whole Ashtanga Yoga section over twenty-three pages, and folding that into a
    single chunk gives it one averaged embedding, so a question about a specific
    point in the commentary matches it less well than the individual page used
    to. Retrieval granularity is the thing that makes commentary findable.

    Instead each page keeps its own chunk and gains a verse label:

        Upadesa Saram · Verse 21 · p. 129

    That gives both behaviours at once. A "verse 21" question matches every page
    of verse 21 on the label prefix, verse first and commentary after, while an
    ordinary semantic question still searches at page resolution.

    Returns None when the work is not recognised or its structure does not parse
    as expected, so the caller keeps ordinary page chunks. Falling back to pages
    is always safe; emitting wrongly numbered verses is not.
    """
    work = identify_work(source_name)
    if not work or not chunks:
        return None

    ordered = sorted(chunks, key=lambda c: (_page_no(getattr(c, "loc", "")) or 0))

    # Skip anything before the main text when the edition has prefatory verses
    # under their own numbering.
    begin = 0
    if work.start_after is not None:
        for idx, c in enumerate(ordered):
            if work.start_after.search(getattr(c, "content", "") or ""):
                begin = idx
                break
        else:
            # Anchor never found: the edition is not laid out as expected.
            return None

    # Locate every verse heading, with the page it sits on and its offset in
    # that page. Numbers must increase strictly, so a benedictory appendix that
    # restarts at 1 after the last verse is ignored.
    marks: list[tuple[int, int, int]] = []   # (page index, offset in page, verse)
    highest = 0
    for idx, c in enumerate(ordered):
        if idx < begin:
            continue
        for m in work.heading.finditer(getattr(c, "content", "") or ""):
            n = int(m.group(1))
            if n > highest and n <= work.expected_verses:
                marks.append((idx, m.start(), n))
                highest = n

    verses_found = [n for _, _, n in marks]
    if len(verses_found) < max(3, work.expected_verses // 2):
        return None
    if verses_found != sorted(verses_found):
        return None

    out: list = []
    ChunkCls = type(chunks[0])

    def emit(content: str, loc: str) -> None:
        out.append(ChunkCls(id=len(out), content=content.strip(), loc=loc))

    # Anything before the first verse (title, contents, introduction, and any
    # prefatory verses under their own numbering) is kept untouched.
    first_page = marks[0][0]
    for c in ordered[:first_page]:
        emit(getattr(c, "content", "") or "", c.loc)

    by_page: dict[int, list[tuple[int, int]]] = {}
    for page_idx, offset, n in marks:
        by_page.setdefault(page_idx, []).append((offset, n))

    current_verse: Optional[int] = None
    for idx in range(first_page, len(ordered)):
        c = ordered[idx]
        page = _page_no(getattr(c, "loc", ""))
        text = (getattr(c, "content", "") or "")
        here = by_page.get(idx, [])

        if not here:
            # Continuation page: commentary belonging to the verse still open.
            if current_verse is None:
                emit(text, c.loc)
            else:
                emit(
                    f"{work.title}, Verse {current_verse} (commentary, p. {page})\n\n{text}",
                    f"{work.title} · Verse {current_verse} · p. {page}",
                )
            continue

        # One or more verses start on this page. Split at each heading so a page
        # carrying two verses does not leave one of them unlabelled: this
        # edition regularly prints two verses per page.
        lead = text[: here[0][0]] if here[0][0] > 0 else ""
        carry = ""
        if lead.strip():
            # Every page opens with "Page No: N / Page Text: / ```" scaffolding.
            # On its own that is not commentary, and emitting it as its own
            # chunk would add one noise chunk per verse. Judge the lead by what
            # remains once the scaffold is removed.
            bare = re.sub(r"Page No:\s*\d+|Page Text:|`+", "", lead).strip()
            if len(bare) < 40:
                # Scaffolding only: carry it into the first verse on this page
                # so the page marker is preserved without a junk chunk.
                carry = lead
            elif current_verse is None:
                # Real text before the first verse, such as the marker that
                # opens the main text. Not part of any verse, but not droppable.
                emit(lead, c.loc)
            else:
                emit(
                    f"{work.title}, Verse {current_verse} (commentary, p. {page})\n\n{lead}",
                    f"{work.title} · Verse {current_verse} · p. {page}",
                )

        for i, (offset, n) in enumerate(here):
            end = here[i + 1][0] if i + 1 < len(here) else len(text)
            body = text[offset:end]
            if i == 0 and carry:
                body = carry + body
            if not body.strip():
                continue
            emit(
                f"{work.title}, Verse {n} (verse and commentary, p. {page})\n\n{body}",
                f"{work.title} · Verse {n} · p. {page}",
            )
            current_verse = n

    return out


# ── Query side ───────────────────────────────────────────────────────────────

# The keyword, then everything that could be a list or range of numbers after
# it. Two things this has to get right that the first version did not:
#
#   1. The PLURAL. "verses 21, 22 and 23" did not match at all, because the
#      pattern demanded "verse" followed immediately by digits, and the "s"
#      broke it. A seeker asking about more than one verse naturally writes
#      "verses", so the commonest multi-verse phrasing was the one form
#      guaranteed to fail.
#
#   2. The WHOLE list. The old pattern captured one number with .search(), so
#      "verses 21, 22 and 23" retrieved verse 21 and nothing else, and the
#      answer then honestly reported that it did not have 22 and 23. It was
#      not missing from the corpus; it was never asked for.
_VERSE_IN_QUERY = re.compile(
    r"\b(?:verses?|slokas?|shlokas?|sutras?|vv?\.)\s*(?:nos?\.?\s*)?"
    r"(\d{1,3}(?:\s*(?:,|&|and|to|through|thru|-|\u2013|\u2014)\s*\d{1,3})*)",
    re.I,
)
# "21st verse", "the 3rd verse"
_ORDINAL_IN_QUERY = re.compile(r"\b(\d{1,3})(?:st|nd|rd|th)\s+verses?\b", re.I)

# Separators that mean "everything between these two", rather than "these two".
_RANGE_SEP = re.compile(r"^(?:to|through|thru|-|\u2013|\u2014)$", re.I)

# A cap on how many verses one question can pull in. Six verses of text and
# commentary is already a long answer, and the retrieval budget is shared
# between them: ask for forty and each would get too little context to be
# explained properly. Better to answer six well.
MAX_VERSES_PER_QUERY = 6


def _expand_verse_list(raw: str, limit: int) -> list[int]:
    """Turn "21, 22 and 23" or "21-23" into [21, 22, 23]."""
    pieces = re.split(r"\s*(,|&|and|to|through|thru|-|\u2013|\u2014)\s*", raw, flags=re.I)
    numbers: list[int] = []
    pending_range = False
    for piece in pieces:
        token = piece.strip()
        if not token:
            continue
        if token.isdigit():
            n = int(token)
            if pending_range and numbers:
                # "21 to 23" — fill in everything between.
                step = 1 if n >= numbers[-1] else -1
                numbers.extend(range(numbers[-1] + step, n + step, step))
            else:
                numbers.append(n)
            pending_range = False
        else:
            pending_range = bool(_RANGE_SEP.match(token))

    # Keep the seeker's order, drop repeats, drop anything out of range.
    seen: set[int] = set()
    out: list[int] = []
    for n in numbers:
        if n in seen or not (1 <= n <= limit):
            continue
        seen.add(n)
        out.append(n)
    return out


def parse_verse_query(text: str) -> Optional[Tuple[str, List[int]]]:
    """Detect "verse(s) N of <known work>" in a question.

    Returns (work_key, [verse numbers]) or None. Requires BOTH a number and a
    recognised work, so "verse 21" alone stays an ordinary semantic search
    rather than guessing which text the seeker meant.
    """
    if not text:
        return None

    work_key = None
    for pat, key in _QUERY_ALIASES:
        if pat.search(text):
            work_key = key
            break
    if not work_key:
        return None

    work = next((w for w in WORKS if w.key == work_key), None)
    if not work:
        return None

    verses: list[int] = []
    for m in _VERSE_IN_QUERY.finditer(text):
        for n in _expand_verse_list(m.group(1), work.expected_verses):
            if n not in verses:
                verses.append(n)
    for m in _ORDINAL_IN_QUERY.finditer(text):
        n = int(m.group(1))
        if 1 <= n <= work.expected_verses and n not in verses:
            verses.append(n)

    if not verses:
        return None
    return work_key, verses[:MAX_VERSES_PER_QUERY]


def title_for(work_key: str) -> str:
    for w in WORKS:
        if w.key == work_key:
            return w.title
    return work_key
