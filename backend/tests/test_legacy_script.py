"""Tests for src/legacy_script.py.

The Bamini samples are real: they are the text actually extracted from
Upadesa_Undiyar.pdf and served in live answers.

Priority under test, in order:
  1. Never lose the vocabulary of these texts. "vichara", "Ramanasramam" and
     "I-I" are not gibberish. Dropping a word of the teaching is a far worse
     failure than leaving a stray token behind.
  2. Then, drop everything that is not English.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.legacy_script import keep_english_only  # noqa: E402


# Verse 21, from a live answer.
VERSE_21 = ("ehndDQ; nrhw;nghU shkJ ehSNk ehdw;w J}f;fj;J Ke;jPgw "
            "ekjpd;ik ePf;fj;jh Ye;jPgw")

# Verse 5, from a live answer. "thnkd", "topgl" and "g+rid" carry no
# semicolon, brace or mid-word capital, so a marker-based rule missed them.
VERSE_5 = ("vz;ZU ahT kpiwAU thnkd ntz;zp topgl Ye;jPgw "
           "tPrdw; g+rid Ae;jPgw")

# The word-by-word gloss the same PDF prints under the verse.
VERSE_5_GLOSS = "vz; cU ahTk; iw cU Mk; vd vz;zp topgly; ey; g+rid"


# ── 1. The teaching must survive ─────────────────────────────────────────────

def test_plain_english_is_untouched():
    s = ("The true import of the word 'I' is always 'I-I'. We do not become "
         "non-existent even in sleep, when the mind does not exist.")
    assert keep_english_only(s) == s


def test_sanskrit_and_tamil_vocabulary_in_latin_script_survives():
    """These are the words the corpus is written in. Losing them is the worst
    outcome this module could produce."""
    s = ("Bhagavan taught vichara at Sri Ramanasramam in Tiruvannamalai. "
         "The jnani abides as the Self; Muruganar recorded it in Guru Vachaka "
         "Kovai, and Upadesa Undiyar says the same.")
    assert keep_english_only(s) == s


def test_iast_diacritics_survive():
    s = "Upadeśa Sāram speaks of the Ātman, and of mokṣa."
    assert keep_english_only(s) == s


def test_hyphenated_and_possessive_words_survive():
    s = "Self-enquiry is Bhagavan's method; the 'I-I' shines as the Self."
    assert keep_english_only(s) == s


def test_all_caps_headings_survive():
    s = "UPADESA SARAM\nVERSE 21\nThe import of the word I."
    assert keep_english_only(s) == s


def test_english_with_ordinary_semicolons_is_untouched():
    s = "He asked; Bhagavan was silent; the question dissolved."
    assert keep_english_only(s) == s


def test_english_paragraph_is_never_majority_dropped():
    s = ("Bhagavan said; the Self alone is; all else is thought. Enquire "
         "within; hold to the I; and the rest falls away.")
    assert keep_english_only(s) == s


# ── 2. Gibberish must go ─────────────────────────────────────────────────────

def test_verse_21_is_removed_entirely():
    assert keep_english_only(VERSE_21) == ""


def test_verse_5_is_removed_entirely():
    assert keep_english_only(VERSE_5) == ""


def test_verse_5_word_gloss_is_removed():
    assert keep_english_only(VERSE_5_GLOSS) == ""


def test_gibberish_line_dropped_english_lines_kept():
    s = f"Verse 21\n{VERSE_21}\nThe word 'I' always has the import of that 'I'."
    out = keep_english_only(s)
    assert "Verse 21" in out
    assert "The word 'I' always has the import of that 'I'." in out
    assert "ehndDQ" not in out


def test_markerless_gibberish_goes_too():
    """'thnkd' and 'shkJ' carry no semicolon but are still not English."""
    out = keep_english_only(VERSE_5 + "\n" + VERSE_21)
    for tok in ["thnkd", "topgl", "g+rid", "shkJ", "ehSNk"]:
        assert tok not in out, f"{tok} survived: {out!r}"


def test_gibberish_inside_an_english_sentence_goes():
    s = ("The teaching is this: vz;ZU ahT kpiwAU thnkd ntz;zp and worship "
         "of every form is good worship.")
    out = keep_english_only(s)
    assert "The teaching is this:" in out
    assert "worship of every form is good worship." in out
    for tok in ["vz;ZU", "ahT", "kpiwAU", "thnkd", "ntz;zp"]:
        assert tok not in out, f"{tok} survived: {out!r}"


# ── 3. Non-Latin script ──────────────────────────────────────────────────────

def test_tamil_script_is_removed():
    out = keep_english_only("நான் யார்? Who am I?")
    assert "நான்" not in out
    assert "Who am I?" in out


def test_devanagari_is_removed_english_kept():
    out = keep_english_only("अहम् ब्रह्मास्मि — I am Brahman.")
    assert "ब्रह्मास्मि" not in out
    assert "I am Brahman." in out


def test_a_line_that_is_only_script_disappears():
    s = "Verse 21\nநான் யார் நான் யார் நான்\nThe import of the word I."
    out = keep_english_only(s)
    assert "Verse 21" in out
    assert "The import of the word I." in out
    assert "நான்" not in out


# ── 4. Edges ─────────────────────────────────────────────────────────────────

def test_empty_and_none_safe():
    assert keep_english_only("") == ""
    assert keep_english_only(None) is None


def test_numbers_and_punctuation_do_not_swing_a_line():
    s = "1. 2. 3. The Self alone is."
    assert keep_english_only(s) == s


# ── 5. Regressions found by running this over 48 real documents ──────────────
# Every case below is a word this module actually deleted from real English
# prose at some point while being built.

def test_abbreviations_with_full_stops_survive():
    """"e.g." was read as one malformed word and deleted mid-sentence."""
    s = "Offer a button (e.g., transform this into a video) after the reply."
    assert keep_english_only(s) == s


def test_vowelless_acronyms_survive():
    """"LLM" has no vowel. The no-vowel rule was deleting it."""
    s = "Title generation uses an open LLM like Llama, and exports a PDF."
    assert keep_english_only(s) == s


def test_letter_digit_tokens_survive():
    s = "Downloadable in MP3/MP4 format on the 21st of the month."
    assert keep_english_only(s) == s


def test_camel_case_names_survive():
    s = "The ChatGPT and OpenAI comparison, built with FastAPI."
    assert keep_english_only(s) == s


def test_lower_camel_and_acronym_plurals_survive():
    s = "Guides & eBooks, with URLs and CTAs on every page."
    assert keep_english_only(s) == s


def test_a_hyphenated_brand_does_not_take_the_english_with_it():
    """"ChatGPT-like" was dropped whole, losing the ordinary word "like"."""
    out = keep_english_only("A ChatGPT-like intuitive search covering the texts.")
    assert "like" in out
    assert "intuitive search covering the texts." in out


def test_urls_survive():
    s = "See https://www.arunachalasamudra.co.in for the library."
    assert keep_english_only(s) == s


def test_unchanged_lines_are_returned_byte_for_byte():
    """No reflowing whitespace in passages it has no quarrel with."""
    s = "  The Self   alone is.  "
    assert keep_english_only(s) == s.strip()


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
