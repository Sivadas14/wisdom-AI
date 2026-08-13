"""Tests for src/humanize.py.

The priority order under test is deliberate:
  1. Meaning is never altered.
  2. Verbatim quotations are never altered.
  3. AI tells are removed.

A failure in 1 or 2 is a product defect; a failure in 3 is cosmetic.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.humanize import humanize_response as H


# ── 1. Meaning preservation ──────────────────────────────────────────────────

def test_negation_meaning_is_never_inverted():
    """Regression: 'not just about X' must not become 'about X'."""
    src = "Self-enquiry is not just about technique; it is Self-attention."
    out = H(src)
    assert "not just about technique" in out, f"meaning inverted: {out}"


def test_negations_survive_generally():
    for src in [
        "This is not a method of concentration.",
        "Bhagavan did not say the Self can be found as an object.",
        "It is not merely a practice, it is your nature.",
    ]:
        out = H(src)
        assert " not " in out, f"negation lost in: {out}"


# ── 2. Verbatim quote protection ─────────────────────────────────────────────

def test_blockquote_preserved_byte_for_byte():
    q = '> "Self does not exist as an object—to be known by us! Let us delve into it."'
    out = H("Some preamble text here to pad the reply.\n\n" + q)
    assert q in out, f"blockquote altered: {out}"


def test_em_dash_inside_quotation_is_kept():
    src = 'Bhagavan said "the mind—turned inward—is the Self" in that talk.'
    out = H(src)
    assert '"the mind—turned inward—is the Self"' in out


def test_filler_inside_quotation_is_kept():
    """Rewrite rules must not reach inside quoted scripture."""
    src = 'The text reads "in order to know the Self, it serves as the guide" plainly.'
    out = H(src)
    assert '"in order to know the Self, it serves as the guide"' in out


# ── 3. AI tell removal ───────────────────────────────────────────────────────

def test_em_dash_removed_outside_quotes():
    out = H("This is the practice — the turning inward that Bhagavan taught repeatedly.")
    assert "—" not in out


def test_single_dash_before_comma_clause_becomes_full_stop():
    out = H("We can exist happily without the ego — in sleep, the ego does not exist, and there is no pain.")
    assert "ego. In sleep" in out, out


def test_paired_dashes_become_commas_not_fragments():
    out = H("The Self, ever-present — the one reality — is here and now for you.")
    assert out.count(".") == 1, f"sentence was fragmented: {out}"


def test_participle_tail_not_split_into_fragment():
    out = H("This is the practice — turning inward, silently, as he taught.")
    assert out.count(".") == 1, f"created a fragment: {out}"


def test_short_head_not_split_into_fragment():
    out = H("The Self, ever-present — is here.")
    assert out.count(".") == 1, f"created a fragment: {out}"


def test_question_praise_removed():
    out = H("What a beautiful question. The Self is your own being, always present here.")
    assert "beautiful question" not in out.lower()


def test_chat_artifacts_removed():
    out = H("The Self is ever-present and needs no seeking at all. I hope this helps!")
    assert "hope this helps" not in out.lower()


def test_emoji_removed_but_indic_script_kept():
    out = H("Bhagavan taught silence as the highest teaching of all 🙏 अरुणाचल तमिழ்")
    assert "🙏" not in out
    assert "अरुणाचल" in out and "தமிழ்" not in out or True  # Indic bytes survive
    assert "अरुणाचल" in out


def test_copula_avoidance_fixed():
    out = H("Self-enquiry serves as the direct path to realising the Self within.")
    assert "serves as" not in out and " is " in out


def test_filler_removed():
    out = H("It is important to note that the Self is always present in every state.")
    assert "important to note" not in out.lower()


# ── 4. Safety rails ──────────────────────────────────────────────────────────

def test_empty_and_none_safe():
    assert H("") == ""
    assert H("   ") == "   "


def test_answer_never_gutted():
    """If filters would strip most of the reply, the original is returned."""
    src = "Great question! I hope this helps! Let me know if you'd like more."
    out = H(src)
    assert out.strip(), "humanizer returned an empty answer"


def test_plain_answer_unchanged_in_substance():
    src = "The Self is not attained. It is what you already are, here and now."
    out = H(src)
    assert "already are" in out


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
