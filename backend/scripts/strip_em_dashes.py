#!/usr/bin/env python3
"""Remove em dashes from content page bodies, protecting verbatim quotes.

The dashes in these pages are not all the same thing, so a single blanket
substitution would produce bad English ("Day by Day with Bhagavan, A. Devaraja
Mudaliar"). Rules are applied in order, most specific first:

  PROTECTED  blockquotes, double-quoted speech, <em> spans holding a quotation,
             and numeric ranges (1984-1988) keep their punctuation exactly.
  ATTRIBUTION "<p>- Sri Ramana Maharshi</p>" loses the dash entirely.
  TITLE/AUTHOR "Upadesa Saram - Rajiv Kapur" inside link text becomes "by".
  SEPARATOR   "</a> - East" becomes a comma.
  PROSE       everything else follows the humanizer: comma, or a full stop when
             a comma would splice.

Usage:
    python3 scripts/strip_em_dashes.py            # dry run, prints every change
    python3 scripts/strip_em_dashes.py --apply    # write the files
"""
from __future__ import annotations

import glob
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
JSON_DIR = os.path.join(HERE, "..", "src", "content_data", "pages_json")

DASH = "[—―]"          # em dash, horizontal bar
MARK = "\x00P{}\x00"

# Spans whose punctuation must survive untouched.
PROTECT = [
    re.compile(r"<blockquote>.*?</blockquote>", re.S | re.I),
    re.compile(r"\"[^\"\n]{0,800}\""),
    re.compile(r"[“][^”\n]{0,800}[”]"),
    # <em> spans are quotations UNLESS they open with an attribution dash.
    re.compile(r"<em>(?!\s*[—―])[^<]{0,800}</em>", re.I),
    re.compile(r"\d\s*[–—]\s*\d"),          # 1984-1988
]


def _mask(text):
    store = []

    def sub(m):
        store.append(m.group(0))
        return MARK.format(len(store) - 1)

    for pat in PROTECT:
        text = pat.sub(sub, text)
    return text, store


def _unmask(text, store):
    # Masks nest: a <em> span can be stored while already containing the mark of
    # a quoted span inside it. Restoring forwards would replace the inner mark
    # before the outer one reappeared, losing it for good. Repeat until stable.
    for _ in range(len(store) + 2):
        before = text
        for i in reversed(range(len(store))):
            text = text.replace(MARK.format(i), store[i])
        if text == before:
            break
    return text


def _prose_dash(text):
    """Comma, or a full stop where a comma would splice. Mirrors humanize.py."""
    def fix(sentence):
        n = len(re.findall(DASH, sentence))
        if n == 0:
            return sentence
        if n % 2 == 0:                       # paired: parenthetical aside
            return re.sub(r"\s*" + DASH + r"\s*", ", ", sentence)
        head, _, tail = sentence.partition(re.search(DASH, sentence).group(0))
        tail = tail.lstrip()
        first = re.match(r"[A-Za-z']+", tail)
        participle = bool(first) and first.group(0).lower().endswith("ing")
        if "," in tail and tail and not participle and head.strip():
            return head.rstrip().rstrip(",") + ". " + tail[:1].upper() + tail[1:]
        return re.sub(r"\s*" + DASH + r"\s*", ", ", sentence)

    return " ".join(fix(p) for p in re.split(r"(?<=[.!?])\s+", text))


def clean(body: str) -> tuple[str, list[str]]:
    notes: list[str] = []

    def note(kind, before, after):
        notes.append(f"    [{kind}] {before.strip()[:72]!r}\n           -> {after.strip()[:72]!r}")

    # 1. Attribution dash opening a text run: "<p>- Name" / "<em>- By Name".
    #    Runs BEFORE masking, because attributions usually sit inside the
    #    blockquote they credit ("<em>- Paul Brunton</em>"). The dash is not part
    #    of the quoted words, so it goes. Restricted to a dash immediately after
    #    a tag, which no genuine quotation starts with.
    def attribution(m):
        out = m.group(1) + m.group(2)
        note("attribution", m.group(0), out)
        return out
    body = re.sub(r"(<(?:p|em|i|b|strong|br|cite|h[1-6])[^>]*>|^)\s*" + DASH
                  + r"\s*((?:By\s+)?[A-Z])", attribution, body)

    body, store = _mask(body)

    # 2. Separator immediately after a link: "</a> - East" becomes a comma.
    def sep(m):
        note("separator", m.group(0), "</a>, ")
        return "</a>, "
    body = re.sub(r"</a>\s*" + DASH + r"\s*", sep, body)

    # 3. Inside anchor text: "Title - Author" becomes "by", but "Title -
    #    Sixth Hymn to Arunachala" is a subtitle, not a person, so it takes a
    #    comma. A personal name carries no lowercase words except "and".
    def anchor(m):
        inner = m.group(2)
        if not re.search(DASH, inner):
            return m.group(0)
        right = re.split(DASH, inner, 1)[1].strip()
        words = re.findall(r"[A-Za-z][A-Za-z.']*", right)
        looks_like_name = bool(words) and all(
            w[0].isupper() or w.lower() == "and" for w in words
        )
        repl = " by " if looks_like_name else ", "
        fixed = re.sub(r"\s*" + DASH + r"\s*", repl, inner)
        note("title/author" if looks_like_name else "title/subtitle", inner, fixed)
        return m.group(1) + fixed + "</a>"
    body = re.sub(r"(<a\b[^>]*>)([^<]*)</a>", anchor, body)

    # 4. Remaining prose dashes.
    if re.search(DASH, body):
        for seg in re.findall(r"[^<>]*" + DASH + r"[^<>]*", body):
            fixed = _prose_dash(seg)
            if fixed != seg:
                note("prose", seg, fixed)
                body = body.replace(seg, fixed)

    body = _unmask(body, store)
    return body, notes


def main():
    apply = "--apply" in sys.argv
    total_before = total_after = 0
    changed_files = 0

    for path in sorted(glob.glob(os.path.join(JSON_DIR, "*.json"))):
        d = json.load(open(path, encoding="utf-8"))
        body = d.get("body_html") or ""
        before = len(re.findall(DASH, body))
        if not before:
            continue

        new_body, notes = clean(body)
        after = len(re.findall(DASH, new_body))
        total_before += before
        total_after += after

        print(f"\n{os.path.basename(path)}  {before} -> {after}")
        for n in notes:
            print(n)
        if after:
            for m in re.finditer(r".{40}" + DASH + r".{40}", new_body, re.S):
                print(f"    [KEPT, protected] ...{m.group(0).strip()[:76]}...")

        if apply and new_body != body:
            d["body_html"] = new_body
            json.dump(d, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
            changed_files += 1

    print(f"\n{'APPLIED' if apply else 'DRY RUN'}: {total_before} dashes -> "
          f"{total_after} kept (protected). Files written: {changed_files}")


if __name__ == "__main__":
    main()
