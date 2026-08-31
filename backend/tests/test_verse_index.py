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
    MAX_VERSES_PER_QUERY, identify_work, parse_verse_query, regroup_by_verse,
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
            for c in out if "\u00b7 Verse " in c.loc]
    assert sorted(set(nums)) == list(range(1, 31)), sorted(set(nums))


def test_contents_page_is_not_treated_as_a_verse():
    """The contents page lists '_Verse 21_ 128' and must not become verse 21."""
    out = regroup_by_verse(_pages(), "sri_ramanas_upadesa_saram__ebook_.pdf")
    v21 = [c for c in out if "\u00b7 Verse 21 \u00b7" in c.loc]
    assert v21, "verse 21 missing"
    assert all("Page No: 7" not in c.content for c in v21)


def test_verse_21_covers_verse_and_commentary_pages():
    """Verse 21 sits on p.128 and its commentary runs to p.129."""
    out = regroup_by_verse(_pages(), "sri_ramanas_upadesa_saram__ebook_.pdf")
    v21 = [c for c in out if c.loc.startswith("Upadesa Saram \u00b7 Verse 21 \u00b7")]
    pages = sorted(int(re.search(r"p\. (\d+)", c.loc).group(1)) for c in v21)
    assert pages == [128, 129], pages
    assert v21[0].content.startswith("Upadesa Saram, Verse 21")


def test_commentary_pages_stay_separate_chunks():
    """Commentary must not be folded into one averaged chunk per verse.

    Verse 10 carries the Ashtanga Yoga section over pages 72-94. Each of those
    pages keeps its own embedding so a question about a specific point in the
    commentary can still match it.
    """
    out = regroup_by_verse(_pages(), "sri_ramanas_upadesa_saram__ebook_.pdf")
    v10 = [c for c in out if c.loc.startswith("Upadesa Saram \u00b7 Verse 10 \u00b7")]
    assert len(v10) == 23, f"expected pages 72-94 as 23 chunks, got {len(v10)}"
    assert sum(1 for c in v10 if "verse and commentary" in c.content) == 1
    assert sum(1 for c in v10 if "(commentary," in c.content) == 22


def test_every_page_survives_labelling():
    pages = _pages()
    out = regroup_by_verse(pages, "sri_ramanas_upadesa_saram__ebook_.pdf")
    assert len(out) == len(pages), f"{len(pages)} pages in, {len(out)} out"
    seen = {int(m.group(1)) for c in out
            for m in [re.search(r"Page No: (\d+)", c.content)] if m}
    assert seen == set(range(1, 166)), sorted(set(range(1, 166)) - seen)


def test_verse_number_is_in_the_embedded_text_too():
    """So semantic search gets a handle on it, not only the exact lookup."""
    out = regroup_by_verse(_pages(), "sri_ramanas_upadesa_saram__ebook_.pdf")
    for c in out:
        if "\u00b7 Verse 7 \u00b7" in c.loc:
            assert "Upadesa Saram, Verse 7" in c.content
            return
    raise AssertionError("verse 7 not found")


# ── 2. Nothing lost ──────────────────────────────────────────────────────────

def test_front_matter_is_preserved():
    out = regroup_by_verse(_pages(), "sri_ramanas_upadesa_saram__ebook_.pdf")
    front = [c for c in out if "\u00b7 Verse " not in c.loc]
    assert len(front) == 25, f"expected pages 1-25, got {len(front)}"


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
        "Explain verse 21 of Upadesa Saram": ("upadesa-saram", [21]),
        "What does the 21st verse of Upadesa Saram mean?": ("upadesa-saram", [21]),
        "Upadesa Undiyar sloka 30": ("upadesa-saram", [30]),
        "verse 12 of Ulladu Narpadu": ("ulladu-narpadu", [12]),
    }
    for q, exp in cases.items():
        assert parse_verse_query(q) == exp, q


def test_a_question_about_several_verses_returns_them_all():
    """The bug this exists to prevent.

    "verse 21, 22 and 23" used to return verse 21 alone, because the number
    was found with .search(). The answer then reported honestly that it did
    not have 22 and 23 — which was true of the context, and false of the
    corpus. It was never asked for them.
    """
    assert parse_verse_query("verse 21 , 22 and 23 of the upadesa saram") == (
        "upadesa-saram", [21, 22, 23])


def test_the_plural_form_is_understood():
    """"verses 21, 22 and 23" matched NOTHING before: the pattern wanted
    "verse" followed by digits, and the "s" broke it. The commonest way to
    ask about several verses was the one form guaranteed to fail."""
    for q in ["verses 21, 22 and 23 of Upadesa Saram",
              "Upadesa Saram verses 21 and 22",
              "explain slokas 4 and 5 of Upadesa Saram"]:
        got = parse_verse_query(q)
        assert got is not None, q
        assert len(got[1]) >= 2, (q, got)


def test_ranges_are_expanded():
    for q in ["explain verses 21-23 of Upadesa Saram",
              "verses 21 to 23 of Upadesa Saram",
              "verses 21 through 23 of Upadesa Saram"]:
        assert parse_verse_query(q) == ("upadesa-saram", [21, 22, 23]), q


def test_a_huge_range_is_capped_rather_than_refused():
    """"verses 1 through 30" must not put the whole work in one prompt, and
    must not fail either. It is capped."""
    got = parse_verse_query("verses 1 through 30 of Upadesa Saram")
    assert got is not None
    assert len(got[1]) == MAX_VERSES_PER_QUERY
    assert got[1][0] == 1


def test_out_of_range_numbers_are_dropped_not_fatal():
    """Ulladu Narpadu has 40 verses; Upadesa Saram has 30."""
    assert parse_verse_query("verses 12 and 40 of Ulladu Narpadu") == (
        "ulladu-narpadu", [12, 40])
    # 31 does not exist in Upadesa Saram, but 29 does — keep the good one.
    assert parse_verse_query("verses 29 and 31 of Upadesa Saram") == (
        "upadesa-saram", [29])


def test_duplicates_collapse_and_order_is_the_seekers():
    assert parse_verse_query("verses 23, 21 and 23 of Upadesa Saram") == (
        "upadesa-saram", [23, 21])


def test_verse_lookup_stays_conservative():
    """Must not fire without BOTH a work and an in-range verse number."""
    for q in ["What is self-enquiry?",          # neither
              "verse 21",                        # no work named
              "Tell me about Upadesa Saram",     # no verse number
              "verse 99 of Upadesa Saram",       # beyond 30
              "verses 41 and 55 of Ulladu Narpadu"]:  # all beyond 40
        assert parse_verse_query(q) is None, q


# ── 5. The Michael James / Muruganar edition (Upadesa Undiyar) ───────────────
# Upadesa Undiyar is the Tamil original that Bhagavan later rendered into
# Sanskrit as Upadesa Saram, so it maps to the same work. Its layout is taken
# from the live corpus: verses numbered "1." under a heading, TWO traps around
# them, and roughly two verses to a page.

JAMES_LAYOUT = {
    6: [1, 2], 7: [3, 4, 5, 6],              # Payiram: prefatory, own numbering
    8: [1, 2], 9: [3], 10: [4, 5], 11: [6, 7], 12: [8, 9], 13: [10, 11],
    14: [12, 13], 15: [14], 16: [15], 17: [16, 17], 18: [18], 19: [19, 20],
    20: [21], 21: [22], 22: [23, 24], 23: [25, 26], 24: [27, 28], 25: [29],
    26: [30, 1, 2], 27: [3, 4, 5],           # benedictory appendix restarts
}


def _james_pages():
    out = []
    for p in range(1, 28):
        b = f"Page No: {p}\nPage Text:\n```\n"
        if p == 8:
            b += "# E}y; **-** **Nul \u2013 Text**\n"
        for n in JAMES_LAYOUT.get(p, []):
            b += f"# {n}. # tamil\n\nEnglish of verse {n}\n\n**Note:** commentary {n}\n"
        out.append(Chunk(p - 1, b + "```", f"Page: {p}"))
    return out


def test_james_edition_labels_all_thirty_verses():
    """Two verses often share a page, so page-level labelling is not enough."""
    out = regroup_by_verse(_james_pages(), "Upadesa_Undiyar.pdf")
    got = sorted({int(re.search(r"Verse (\d+) \u00b7", c.loc).group(1))
                  for c in out if "\u00b7 Verse " in c.loc})
    assert got == list(range(1, 31)), [v for v in range(1, 31) if v not in got]


def test_james_prefatory_verses_do_not_hijack_numbering():
    """The Payiram numbers 1-6 BEFORE the main text and must be skipped.

    Without the start anchor, verse 1 would be taken from page 6 and every
    number after it would be wrong.
    """
    out = regroup_by_verse(_james_pages(), "Upadesa_Undiyar.pdf")
    v1 = [c for c in out if "\u00b7 Verse 1 \u00b7" in c.loc]
    pages = {int(re.search(r"p\. (\d+)", c.loc).group(1)) for c in v1}
    assert pages == {8}, f"verse 1 should come from p.8, got {pages}"


def test_james_verse_21_is_on_page_20():
    out = regroup_by_verse(_james_pages(), "Upadesa_Undiyar.pdf")
    v21 = [c for c in out if "\u00b7 Verse 21 \u00b7" in c.loc]
    assert v21, "verse 21 missing"
    assert all("p. 20" in c.loc for c in v21), [c.loc for c in v21]


def test_james_appendix_does_not_restart_the_count():
    """A benedictory appendix renumbers from 1 after verse 30."""
    out = regroup_by_verse(_james_pages(), "Upadesa_Undiyar.pdf")
    v1 = [c for c in out if "\u00b7 Verse 1 \u00b7" in c.loc]
    assert not any("p. 26" in c.loc or "p. 27" in c.loc for c in v1)


def test_james_no_page_is_lost():
    pages = _james_pages()
    out = regroup_by_verse(pages, "Upadesa_Undiyar.pdf")
    seen = {int(m.group(1)) for c in out
            for m in [re.search(r"Page No: (\d+)", c.content)] if m}
    assert seen == set(range(1, 28)), sorted(set(range(1, 28)) - seen)


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
