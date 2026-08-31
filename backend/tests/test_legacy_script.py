"""Tests for src/legacy_script.py.

The Bamini samples are real: they are the text actually extracted from
Upadesa_Undiyar.pdf and served in the verse 21 answer.

Priority under test:
  1. Never remove English. A lost sentence of Bhagavan's teaching is far worse
     than a line of leftover gibberish.
  2. Never touch Unicode Tamil. The site answers in Tamil.
  3. Then, remove the Bamini.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.legacy_script import strip_legacy_tamil  # noqa: E402


VERSE_21 = ("ehndDQ; nrhw;nghU shkJ ehSNk ehdw;w J}f;fj;J Ke;jPgw "
            "ekjpd;ik ePf;fj;jh Ye;jPgw")

# Verse 5, taken from a live answer. This one broke the first implementation:
# "thnkd", "topgl" and "g+rid" carry no semicolon, no brace and no mid-word
# capital, so marker-based span growth stopped short and left them behind.
VERSE_5 = ("vz;ZU ahT kpiwAU thnkd ntz;zp topgl Ye;jPgw "
           "tPrdw; g+rid Ae;jPgw")

# The word-by-word gloss the same PDF prints under the verse.
VERSE_5_GLOSS = "vz; cU ahTk; iw cU Mk; vd vz;zp topgly; ey; g+rid"


# ── 1. English must survive ──────────────────────────────────────────────────

def test_plain_english_is_untouched():
    s = ("The true import of the word 'I' is always 'I-I'. We do not become "
         "non-existent even in sleep, when the mind does not exist.")
    assert strip_legacy_tamil(s) == s


def test_english_with_ordinary_semicolons_is_untouched():
    s = "He asked; Bhagavan was silent; the question dissolved."
    assert strip_legacy_tamil(s) == s


def test_midword_capitals_alone_are_not_enough():
    """iPhone and McDonald have mid-word capitals. Without a semicolon anchor
    beside them they must never be removed."""
    s = "He read it on his iPhone outside McDonald's in Tiruvannamalai."
    assert strip_legacy_tamil(s) == s


def test_code_like_text_without_the_anchor_survives():
    s = "See verse 21; the commentary follows on page 20."
    assert strip_legacy_tamil(s) == s


# ── 2. Unicode Tamil must survive ────────────────────────────────────────────

def test_unicode_tamil_is_untouched():
    s = "நான் யார்? Who am I?"
    assert strip_legacy_tamil(s) == s


def test_unicode_tamil_next_to_english_semicolon():
    s = "உபதேச உந்தியார்; the Tamil original."
    assert strip_legacy_tamil(s) == s


# ── 3. Bamini must go ────────────────────────────────────────────────────────

def test_verse_21_bamini_is_removed_entirely():
    assert strip_legacy_tamil(VERSE_21) == ""


def test_bamini_removed_english_kept_on_one_line():
    s = f"Here is verse 21: {VERSE_21} The word 'I' always has that import."
    out = strip_legacy_tamil(s)
    assert "ehndDQ" not in out and "J}f" not in out and ";nghU" not in out
    assert "Here is verse 21:" in out
    assert "The word 'I' always has that import." in out


def test_bamini_line_dropped_english_lines_kept():
    s = f"Verse 21\n{VERSE_21}\nThe word 'I' always has the import of that 'I'."
    out = strip_legacy_tamil(s)
    assert "Verse 21" in out
    assert "The word 'I' always has the import of that 'I'." in out
    assert "ehndDQ" not in out


def test_the_whole_run_goes_not_just_the_semicolon_tokens():
    """'shkJ' and 'ehSNk' carry no semicolon. They are still Bamini and must be
    removed along with the run, or the answer keeps half the gibberish."""
    out = strip_legacy_tamil(VERSE_21)
    for tok in ["shkJ", "ehSNk", "Ke", "Ye"]:
        assert tok not in out, f"{tok} survived: {out!r}"


def test_verse_5_markerless_tokens_are_removed_too():
    """The case that broke the first version."""
    out = strip_legacy_tamil(VERSE_5)
    assert out == "", f"survived: {out!r}"


def test_verse_5_word_gloss_is_removed():
    assert strip_legacy_tamil(VERSE_5_GLOSS) == ""


def test_verse_5_line_dropped_english_kept():
    s = f"Verse 5 reads:\n{VERSE_5}\nWorship of any of the eight forms is good worship."
    out = strip_legacy_tamil(s)
    assert "thnkd" not in out and "topgl" not in out and "g+rid" not in out
    assert "Verse 5 reads:" in out
    assert "Worship of any of the eight forms is good worship." in out


def test_english_sentence_with_tamil_set_into_it_keeps_its_english():
    s = ("The teaching is this: vz;ZU ahT kpiwAU thnkd ntz;zp topgl "
         "and worship of every form is good worship.")
    out = strip_legacy_tamil(s)
    assert "The teaching is this:" in out
    assert "worship of every form is good worship." in out
    for tok in ["vz;ZU", "kpiwAU", "thnkd"]:
        assert tok not in out, f"{tok} survived: {out!r}"


def test_an_english_shaped_bamini_token_can_survive_inline():
    """A known and deliberate limit, recorded rather than papered over.

    "topgl" is Bamini, but it is lower case, starts with a letter and has a
    vowel, so it is indistinguishable from an English word by shape. Catching
    it would need a consonant-cluster rule, and "thoughts" has a four
    consonant cluster too. Dropping a word of Bhagavan's teaching is a worse
    failure than leaving one token of gibberish, so the token stays.

    This only bites when Tamil is set INSIDE an English sentence. In the
    corpus the Tamil sits on its own line, where the whole line is dropped and
    the leftover cannot arise; test_verse_5_line_dropped_english_kept covers
    that, which is the case that actually occurs.
    """
    s = ("The teaching is this: vz;ZU ahT kpiwAU thnkd ntz;zp topgl "
         "and worship of every form is good worship.")
    assert "topgl" in strip_legacy_tamil(s)


def test_a_real_english_paragraph_is_never_majority_dropped():
    """Guard against the line rule firing on prose that merely has a semicolon."""
    s = ("Bhagavan said; the Self alone is; all else is thought. Enquire "
         "within; hold to the I; and the rest falls away.")
    assert strip_legacy_tamil(s) == s


def test_no_semicolon_means_no_work_done():
    s = "shkJ ehSNk"  # no anchor anywhere
    assert strip_legacy_tamil(s) == s


def test_empty_and_none_safe():
    assert strip_legacy_tamil("") == ""
    assert strip_legacy_tamil(None) is None


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
