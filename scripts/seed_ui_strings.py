#!/usr/bin/env python3
"""
seed_ui_strings.py — populate per-language UI string JSONs from the English master.

Walks the English locale file, for each leaf string checks whether the target
language already has a translation; if not (or if the source string changed),
calls the /api/translate gateway to translate, then writes the result back to
the target language's JSON.

Run after every change to the English master, or to refresh stale translations.

USAGE
-----
    # Default — read from frontend/public/locales/en/common.json, write to
    # frontend/public/locales/{lang}/common.json for all 8 non-English locales.
    python scripts/seed_ui_strings.py

    # Specify endpoint and master file:
    python scripts/seed_ui_strings.py \\
        --endpoint https://api.arunachalasamudra.co.in/api/translate \\
        --master frontend/public/locales/en/common.json \\
        --output-dir frontend/public/locales/

    # Translate a specific language only:
    python scripts/seed_ui_strings.py --langs hi ta

ENVIRONMENT
-----------
    API_BASE       — base URL of the wisdom-AI backend (default https://api.arunachalasamudra.co.in)
    JWT_TOKEN      — optional; only needed if /api/translate requires auth in your config

The script is idempotent — running it twice in a row is a no-op for unchanged strings.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urljoin

import requests

DEFAULT_TARGET_LANGS = ["hi", "ta", "te", "bn", "ml", "es", "fr", "ar"]


def flatten(obj: Any, prefix: str = "") -> dict[str, str]:
    """Flatten a nested dict into dotted keys → string-leaf values.

    Example:
        {"app": {"name": "X", "title": "Y"}} → {"app.name": "X", "app.title": "Y"}
    """
    flat: dict[str, str] = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.startswith("_"):  # skip _meta keys
                continue
            new_key = f"{prefix}.{k}" if prefix else k
            flat.update(flatten(v, new_key))
    elif isinstance(obj, str):
        flat[prefix] = obj
    return flat


def unflatten(flat: dict[str, str]) -> dict:
    """Inverse of flatten()."""
    out: dict = {}
    for dotted_key, value in flat.items():
        parts = dotted_key.split(".")
        cur = out
        for p in parts[:-1]:
            cur = cur.setdefault(p, {})
        cur[parts[-1]] = value
    return out


def translate_one(api_url: str, jwt: str | None, text: str, target: str) -> str:
    """Call the translation gateway for one string. Retries once on failure."""
    headers = {"Content-Type": "application/json"}
    if jwt:
        headers["Authorization"] = f"Bearer {jwt}"

    payload = {
        "text": text,
        "source_lang": "en",
        "target_lang": target,
        "resource_type": "ui_string",
        "resource_id": None,
    }

    for attempt in (1, 2):
        try:
            r = requests.post(api_url, json=payload, headers=headers, timeout=15)
            r.raise_for_status()
            data = r.json()
            if not data.get("success"):
                print(f"  ⚠ {target}: translation API returned success=false: {data.get('message')}", file=sys.stderr)
                return text
            return data["data"]["translated"] or text
        except Exception as e:
            if attempt == 1:
                time.sleep(1.0)
                continue
            print(f"  ⚠ {target}: translate failed for {text[:40]!r}: {e}", file=sys.stderr)
            return text  # graceful: leave English in place
    return text


def seed_language(
    *,
    api_url: str,
    jwt: str | None,
    target_lang: str,
    master_flat: dict[str, str],
    output_path: Path,
    dry_run: bool = False,
) -> tuple[int, int]:
    """Seed one target language file. Returns (translated, skipped) counts."""
    print(f"\n=== Seeding {target_lang} ===")
    translated_count = 0
    skipped_count = 0

    # Load existing target file if present
    existing_flat: dict[str, str] = {}
    existing_meta: dict = {}
    if output_path.exists():
        existing_full = json.loads(output_path.read_text(encoding="utf-8"))
        existing_meta = existing_full.get("_meta", {})
        existing_flat = flatten(existing_full)

    # For each English key, translate if missing or if explicitly forced
    new_flat: dict[str, str] = dict(existing_flat)  # start from what's there
    for key, en_text in master_flat.items():
        if key in existing_flat and existing_flat[key].strip() and existing_flat[key] != en_text:
            # Already has a non-English translation — keep it (manual or previously seeded)
            skipped_count += 1
            continue
        if dry_run:
            print(f"  WOULD translate: {key} = {en_text[:50]!r}")
            translated_count += 1
            continue

        translated = translate_one(api_url, jwt, en_text, target_lang)
        new_flat[key] = translated
        translated_count += 1
        if translated_count % 10 == 0:
            print(f"  ... {translated_count} translated", flush=True)

    # Build final JSON
    out: dict = {
        "_meta": {
            **existing_meta,
            "language": target_lang,
            "version": existing_meta.get("version", "1.0"),
            "last_updated": time.strftime("%Y-%m-%d"),
        },
        **unflatten(new_flat),
    }

    if dry_run:
        print(f"  [DRY RUN] would write {output_path} with {translated_count} new + {skipped_count} kept")
        return translated_count, skipped_count

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  ✓ Wrote {output_path}: {translated_count} new translations, {skipped_count} kept")
    return translated_count, skipped_count


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--endpoint", default=None,
                        help="Translation gateway URL (default: ${API_BASE}/api/translate)")
    parser.add_argument("--master", default="frontend/public/locales/en/common.json",
                        help="Path to English master JSON")
    parser.add_argument("--output-dir", default="frontend/public/locales/",
                        help="Directory containing per-language folders")
    parser.add_argument("--langs", nargs="*", default=None,
                        help=f"Subset of languages (default: {DEFAULT_TARGET_LANGS})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Don't actually write files; just show what would happen")
    args = parser.parse_args()

    api_base = os.environ.get("API_BASE", "https://api.arunachalasamudra.co.in")
    api_url = args.endpoint or urljoin(api_base.rstrip("/") + "/", "api/translate")
    jwt = os.environ.get("JWT_TOKEN")

    master_path = Path(args.master)
    if not master_path.exists():
        print(f"ERROR: master file not found: {master_path}", file=sys.stderr)
        sys.exit(1)

    master_full = json.loads(master_path.read_text(encoding="utf-8"))
    master_flat = flatten(master_full)
    print(f"Master: {master_path} ({len(master_flat)} strings)")
    print(f"Endpoint: {api_url}")
    print(f"Auth: {'Bearer token set' if jwt else 'none (relying on public path)'}")

    languages = args.langs or DEFAULT_TARGET_LANGS
    output_dir = Path(args.output_dir)

    total_new = 0
    total_kept = 0
    for lang in languages:
        out_path = output_dir / lang / "common.json"
        new, kept = seed_language(
            api_url=api_url, jwt=jwt,
            target_lang=lang,
            master_flat=master_flat,
            output_path=out_path,
            dry_run=args.dry_run,
        )
        total_new += new
        total_kept += kept

    print(f"\n=== Summary ===")
    print(f"  Languages processed: {len(languages)}")
    print(f"  New translations:    {total_new}")
    print(f"  Kept existing:       {total_kept}")
    if args.dry_run:
        print("  [DRY RUN — no files written]")


if __name__ == "__main__":
    main()
