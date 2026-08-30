"""Tests for src/verse_index.py.

The page layout in the fixtures is not invented: verse start pages are the ones
actually observed in the indexed Rajiv Kapur edition of Upadesa Saram (165
pages, verse 1 on page 26 through verse 30 on page 162).

Priority under test:
  1. Never mislabel a verse (a wrong number is worse than no number).
  2. Never lose content.
  3. Group and label correctly.
"""
import os
import re
import sys
from dataclasses import dataclass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.verse_index import (  # noqa: E402
    identify_work, parse_verse_query, regroup_by_verse,
)


@dataclass
class Chunk:
    id: int
    content: str
    loc: str


# Verse start pages verified against the live corpus.
STARTS = [26, 31, 35, 43, 51, 57, 61, 66, 69, 72, 95, 100, 104, 106, 109,
          114, 117, 120, 123, 126, 128, 130, 136, 141, 146, 148, 151, 154,
          157, 162]


def _pages(total=165):
    verse_at = {p: i + 1 for i, p in enumerate(STARTS)}
    out = []
    for p in range(1, total + 1):
        body = f"Page No: {p}\nPage Text:\n```\n"
        if p in verse_at:
            body += f"## Verse {verse_at[p]}\n\nSanskrit\n\nTranslation\n"
        body += ("commentary " * 90) + "\n```"
        out.append(Chunk(id=p - 1, content=body, loc=f"Page: {p}"))
    # Contents page: verses listed in italics, not as headings.
    out[6] = Chunk(6, "Page No: 7\nPage Text:\n```\n_Verse 11_ 95\n_Verse 21_ 128\n```", "Page: 7")
    return out


# ── 1. Correct labelling ─────────────────────────────────────────────────────

def test_all_thirty_verses_captured_in_order():
    out = regroup_by_verse(_pages(), "sri_ramanas_upadesa_saram__ebook_.pdf")
    nums = [int(re.search(r"Verse (\d+)", c.loc).group(1))
            for c in out if "Verse" in c.loc]
    assert sorted(set(nums)) == list(range(1, 31)), nums


def test_contents_page_is_not_treated_as_a_verse():
    """The contents page lists '_Verse 21_ 128' and must not become verse 21."""
    out = regroup_by_verse(_pages(), "sri_ramanas_upadesa_saram__ebook_.pdf")
    v21 = [c for c in out if "Verse 21 (" in c.loc]
    assert v21, "verse 21 missing"
    assert all("Page No: 7" not in c.content for c in v21)


def test_verse_21_spans_the_right_pages():
    out = regroup_by_verse(_pages(), "sri_ramanas_upadesa_saram__ebook_.pdf")
    v21 = [c for c in out if "Verse 21 (" in c.loc][0]
    assert "pp. 128-129" in v21.loc, v21.loc
    assert v21.content.startswith("Upadesa Saram, Verse 21")


def test_verse_number_is_in_the_embedded_text_too():
    """So semantic search gets a handle on it, not only the exact lookup."""
    out = regroup_by_verse(_pages(), "sri_ramanas_upadesa_saram__ebook_.pdf")
    for c in out:
        if "Verse 7 (" in c.loc:
            assert "Upadesa Saram, Verse 7" in c.content
            return
    raise AssertionError("verse 7 not found")


# ── 2. Nothing lost ──────────────────────────────────────────────────────────

def test_front_matter_is_preserved():
    out = regroup_by_verse(_pages(), "sri_ramanas_upadesa_saram__ebook_.pdf")
    front = [c for c in out if "Verse" not in c.loc]
    assert len(front) == 25, f"expected pages 1-25, got {len(front)}"


def test_long_verse_is_split_but_stays_addressable():
    """A verse whose commentary exceeds the embedding budget must split.

    Upadesa Saram verse 10 carries the whole Ashtanga Yoga section across pages
    72-94, which sits near the cap. This fixture uses deliberately heavy pages
    so the split path is exercised regardless of which tokeniser is available,
    rather than depending on where the real text happens to land.
    """
    verse_at = {p: i + 1 for i, p in enumerate(STARTS)}
    pages = []
    for p in range(1, 166):
        body = f"Page No: {p}\nPage Text:\n```\n"
        if p in verse_at:
            body += f"## Verse {verse_at[p]}\n\nSanskrit\n\nTranslation\n"
        body += ("commentary " * 600) + "\n```"
        pages.append(Chunk(p - 1, body, f"Page: {p}"))

    out = regroup_by_verse(pages, "sri_ramanas_upadesa_saram__ebook_.pdf")
    v10 = [c for c in out if re.search(r"Verse 10 \(", c.loc)]
    assert len(v10) > 1, "expected the long verse to be split"
    assert all("Verse 10" in c.loc for c in v10)
    assert all("part" in c.loc for c in v10), [c.loc for c in v10]
    # Splitting must not drop pages.
    joined = " ".join(c.content for c in v10)
    for page in (72, 85, 94):
        assert f"Page No: {page}\n" in joined, f"page {page} lost in the split"


# ── 3. Safety: unknown or malformed input falls back to page chunks ──────────

def test_unknown_work_returns_none():
    assert regroup_by_verse(_pages(), "conscious-immortality.pdf") is None


def test_document_without_verse_headings_returns_none():
    plain = [Chunk(i, f"Page No: {i+1}\nPage Text:\n```\nprose\n```", f"Page: {i+1}")
             for i in range(40)]
    assert regroup_by_verse(plain, "sri_ramanas_upadesa_saram__ebook_.pdf") is None


def test_identify_work():
    assert identify_work("sri_ramanas_upadesa_saram__ebook_.pdf").key == "upadesa-saram"
    assert identify_work("40 Verses on Reality.pdf").key == "ulladu-narpadu"
    assert identify_work("glory-of-arunachala.pdf") is None


# ── 4. Query parsing ─────────────────────────────────────────────────────────

def test_verse_queries_parse():
    cases = {
        "Explain verse 21 of Upadesa Saram": ("upadesa-saram", 21),
        "What does the 21st verse of Upadesa Saram mean?": ("upadesa-saram", 21),
        "Upadesa Undiyar sloka 30": ("upadesa-saram", 30),
        "verse 12 of Ulladu Narpadu": ("ulladu-narpadu", 12),
    }
    for q, exp in cases.items():
        assert parse_verse_query(q) == exp, q


def test_verse_lookup_stays_conservative():
    """Must not fire without BOTH a work and an in-range verse number."""
    for q in ["What is self-enquiry?",          # neither
              "verse 21",                        # no work named
              "Tell me about Upadesa Saram",     # no verse number
              "verse 99 of Upadesa Saram",       # beyond 30
              "verse 41 of Ulladu Narpadu"]:     # beyond 40
        assert parse_verse_query(q) is None, q


if __name__ == "__main__":
    passed = failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS  {name}")
                passed += 1
            except AssertionError as e:
                print(f"FAIL  {name}: {e}")
                failed += 1
            except Exception as e:
                print(f"ERROR {name}: {type(e).__name__}: {e}")
                failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
