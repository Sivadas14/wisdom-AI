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


WORKS: tuple[Work, ...] = (
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
    """Regroup page chunks into verse chunks for a known numbered work.

    Returns None when the work is not recognised or its structure does not
    parse as expected, so the caller keeps the ordinary page chunks. Failing
    back to page chunks is always safe; emitting wrongly numbered verses is not.

    Pages before the first verse (title, dedication, contents, introduction) are
    preserved unchanged, so nothing is dropped.
    """
    work = identify_work(source_name)
    if not work or not chunks:
        return None

    ordered = sorted(chunks, key=lambda c: (_page_no(getattr(c, "loc", "")) or 0))

    # Locate the first heading on each page, in order, keeping verse numbers
    # strictly increasing. An appendix that repeats "Verse 1" must not restart
    # the sequence.
    starts: list[tuple[int, int]] = []   # (index into ordered, verse number)
    highest = 0
    for idx, c in enumerate(ordered):
        nums = [int(n) for n in work.heading.findall(getattr(c, "content", "") or "")]
        nums = [n for n in nums if n > highest]
        if nums:
            n = min(nums)
            starts.append((idx, n))
            highest = n

    verses_found = [n for _, n in starts]
    if len(verses_found) < max(3, work.expected_verses // 2):
        # Too few to trust; the edition is probably laid out differently.
        return None
    if verses_found != sorted(verses_found):
        return None

    out: list = []
    ChunkCls = type(chunks[0])
    next_id = 0

    def emit(content: str, loc: str) -> None:
        nonlocal next_id
        out.append(ChunkCls(id=next_id, content=content, loc=loc))
        next_id += 1

    # Front matter, untouched.
    for c in ordered[: starts[0][0]]:
        emit(c.content, c.loc)

    for i, (start_idx, verse_no) in enumerate(starts):
        end_idx = starts[i + 1][0] if i + 1 < len(starts) else len(ordered)
        group = ordered[start_idx:end_idx]
        first_page = _page_no(group[0].loc)
        last_page = _page_no(group[-1].loc)
        span = (
            f"p. {first_page}" if first_page == last_page
            else f"pp. {first_page}-{last_page}"
        )

        body = "\n\n".join((getattr(c, "content", "") or "").strip() for c in group)

        # The verse number goes into the embedded TEXT as well as the label, so
        # semantic search gets a handle on it too, not just the exact lookup.
        header = f"{work.title}, Verse {verse_no}"

        if _count_tokens(body) <= _MAX_TOKENS_PER_CHUNK:
            emit(f"{header}\n\n{body}", f"{work.title} · Verse {verse_no} ({span})")
            continue

        # Long commentary: split across several chunks, each still addressable
        # as this verse.
        parts: list[str] = []
        current: list[str] = []
        for c in group:
            piece = (getattr(c, "content", "") or "").strip()
            candidate = "\n\n".join(current + [piece])
            if current and _count_tokens(candidate) > _MAX_TOKENS_PER_CHUNK:
                parts.append("\n\n".join(current))
                current = [piece]
            else:
                current.append(piece)
        if current:
            parts.append("\n\n".join(current))

        for pi, part in enumerate(parts, start=1):
            emit(
                f"{header} (part {pi} of {len(parts)})\n\n{part}",
                f"{work.title} · Verse {verse_no} ({span}, part {pi}/{len(parts)})",
            )

    return out


# ── Query side ───────────────────────────────────────────────────────────────

_VERSE_IN_QUERY = re.compile(
    r"\b(?:verse|sloka|shloka|sutra|v\.)\s*(?:no\.?\s*)?(\d{1,3})\b", re.I
)
# "21st verse", "verse 21", "chapter 2 verse 21"
_ORDINAL_IN_QUERY = re.compile(r"\b(\d{1,3})(?:st|nd|rd|th)\s+verse\b", re.I)


def parse_verse_query(text: str) -> Optional[Tuple[str, int]]:
    """Detect "verse N of <known work>" in a user question.

    Returns (work_key, verse_number), or None. Requires BOTH a verse number and
    a recognised work, so "verse 21" alone stays an ordinary semantic search
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

    m = _VERSE_IN_QUERY.search(text) or _ORDINAL_IN_QUERY.search(text)
    if not m:
        return None

    verse_no = int(m.group(1))
    work = next((w for w in WORKS if w.key == work_key), None)
    if not work or not (1 <= verse_no <= work.expected_verses):
        return None

    return work_key, verse_no


def title_for(work_key: str) -> str:
    for w in WORKS:
        if w.key == work_key:
            return w.title
    return work_key
