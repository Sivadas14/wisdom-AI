#!/usr/bin/env python3
"""
generate_sitemaps.py — produce per-language XML sitemaps + index for SEO.

Reads the list of indexable pages from the wisdom-AI database (the existing
`source_documents` table by default — adapt to your CMS if you have a `pages`
table). For each page emits one entry per Phase-1 language with proper
hreflang annotations.

USAGE
-----
    python scripts/generate_sitemaps.py                  # writes to frontend/public/sitemaps/
    python scripts/generate_sitemaps.py --output-dir /tmp/maps/

ENVIRONMENT
-----------
    ASAM_DB_URL  — Postgres connection string (asyncpg dialect)
    SITE_ORIGIN  — site origin URL (default https://www.arunachalasamudra.co.in)

CRON
----
Schedule via Cloud Scheduler / GitHub Actions to run daily 04:00 IST so new
content gets indexed by search engines without manual intervention. Example
GitHub Actions workflow in deploy/cloud_scheduler.sh.

OUTPUT
------
    frontend/public/sitemap.xml         (sitemap index)
    frontend/public/sitemaps/en.xml     (English sitemap)
    frontend/public/sitemaps/hi.xml
    frontend/public/sitemaps/ta.xml
    ... etc, one per Phase-1 language ...
"""
from __future__ import annotations

import argparse
import asyncio
import datetime
import os
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import asyncpg

PHASE_1_LANGS = ["en", "hi", "ta", "te", "bn", "ml", "es", "fr", "ar"]


# ---------------------------------------------------------------------------
# Page list — adapt this to your actual data source
# ---------------------------------------------------------------------------

# Static pages that are always part of the sitemap, regardless of DB content.
STATIC_PAGES = [
    {"slug": "",                "priority": 1.0, "changefreq": "daily"},   # home
    {"slug": "library",         "priority": 0.9, "changefreq": "weekly"},
    {"slug": "wisdom-portal",   "priority": 0.9, "changefreq": "weekly"},
    {"slug": "subscription",    "priority": 0.7, "changefreq": "monthly"},
    {"slug": "about",           "priority": 0.5, "changefreq": "monthly"},
    {"slug": "privacy",         "priority": 0.3, "changefreq": "yearly"},
    {"slug": "terms",           "priority": 0.3, "changefreq": "yearly"},
]


async def fetch_dynamic_pages(conn) -> list[dict]:
    """Fetch any DB-driven indexable content. Adapt this to your schema."""
    pages: list[dict] = []
    # Example: pull teaching slugs from source_documents
    try:
        rows = await conn.fetch("""
            SELECT name AS slug, created_at::text AS lastmod
            FROM source_documents
            ORDER BY created_at DESC
            LIMIT 1000
        """)
        for row in rows:
            slug = (row["slug"] or "").strip()
            if not slug:
                continue
            pages.append({
                "slug":       f"library/{slug}",
                "lastmod":    row["lastmod"][:10] if row["lastmod"] else None,
                "priority":   0.7,
                "changefreq": "monthly",
            })
    except asyncpg.exceptions.UndefinedTableError:
        pass

    # Example: a `pages` table if you've added one
    try:
        rows = await conn.fetch("""
            SELECT slug, last_updated::text AS lastmod
            FROM pages
            WHERE published = TRUE
            ORDER BY last_updated DESC
        """)
        for row in rows:
            pages.append({
                "slug":       row["slug"],
                "lastmod":    row["lastmod"][:10] if row["lastmod"] else None,
                "priority":   0.8,
                "changefreq": "weekly",
            })
    except asyncpg.exceptions.UndefinedTableError:
        pass

    return pages


# ---------------------------------------------------------------------------
# Sitemap XML emission
# ---------------------------------------------------------------------------

def render_url_entry(slug: str, language: str, all_langs: list[str], origin: str,
                     lastmod: str | None, priority: float, changefreq: str) -> str:
    """One <url> block with all hreflang alternates."""
    canonical = f"{origin}/{language}/{slug}".rstrip("/")
    alternates = "".join(
        f'    <xhtml:link rel="alternate" hreflang="{l}" '
        f'href="{origin}/{l}/{slug}".rstrip(\'/\')\'/>\n'
        for l in all_langs
    )
    # Cleaner output (xml-escape the slug)
    s = escape(slug)
    alt_lines = []
    for l in all_langs:
        url = f"{origin}/{l}/{s}".rstrip("/")
        alt_lines.append(f'    <xhtml:link rel="alternate" hreflang="{l}" href="{url}"/>')
    # Add x-default
    alt_lines.append(f'    <xhtml:link rel="alternate" hreflang="x-default" href="{origin}/{s}".rstrip(\'/\')\'/>')

    canonical_url = f"{origin}/{language}/{s}".rstrip("/")
    lastmod_xml = f"\n    <lastmod>{lastmod}</lastmod>" if lastmod else ""
    return (
        f"  <url>\n"
        f"    <loc>{canonical_url}</loc>\n"
        + "\n".join(alt_lines) + "\n"
        f"    <xhtml:link rel=\"alternate\" hreflang=\"x-default\" href=\"{origin}/{s}\".rstrip(\'/\')\'/>\n"
        f"{lastmod_xml}"
        f"    <changefreq>{changefreq}</changefreq>\n"
        f"    <priority>{priority:.1f}</priority>\n"
        f"  </url>"
    )


def render_per_lang_sitemap(language: str, all_langs: list[str], pages: list[dict], origin: str) -> str:
    """Build a complete sitemap.xml for one language."""
    s = escape  # alias

    url_blocks = []
    for p in pages:
        slug = p["slug"]
        canonical_url = f"{origin}/{language}/{slug}".rstrip("/")
        alt_lines = []
        for l in all_langs:
            url = f"{origin}/{l}/{slug}".rstrip("/")
            alt_lines.append(f'    <xhtml:link rel="alternate" hreflang="{l}" href="{s(url)}"/>')
        # x-default
        xdefault_url = f"{origin}/{slug}".rstrip("/")
        alt_lines.append(f'    <xhtml:link rel="alternate" hreflang="x-default" href="{s(xdefault_url)}"/>')

        lastmod_line = f"\n    <lastmod>{p['lastmod']}</lastmod>" if p.get("lastmod") else ""
        block = (
            f"  <url>\n"
            f"    <loc>{s(canonical_url)}</loc>\n"
            + "\n".join(alt_lines) +
            f"{lastmod_line}\n"
            f"    <changefreq>{p.get('changefreq', 'weekly')}</changefreq>\n"
            f"    <priority>{p.get('priority', 0.5):.1f}</priority>\n"
            f"  </url>"
        )
        url_blocks.append(block)

    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap-0.9"\n'
        '        xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
        + "\n".join(url_blocks) + "\n"
        '</urlset>\n'
    )


def render_sitemap_index(origin: str, languages: list[str]) -> str:
    """Build the sitemap index pointing to per-language sitemaps."""
    today = datetime.date.today().isoformat()
    entries = []
    for l in languages:
        entries.append(
            f"  <sitemap>\n"
            f"    <loc>{origin}/sitemaps/{l}.xml</loc>\n"
            f"    <lastmod>{today}</lastmod>\n"
            f"  </sitemap>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap-0.9">\n'
        + "\n".join(entries) + "\n"
        '</sitemapindex>\n'
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main_async(output_dir: Path, origin: str, db_url: str | None) -> int:
    pages = list(STATIC_PAGES)

    # Try to enrich with DB-driven pages
    if db_url:
        try:
            conn = await asyncpg.connect(db_url)
            try:
                dyn = await fetch_dynamic_pages(conn)
                pages.extend(dyn)
            finally:
                await conn.close()
        except Exception as e:
            print(f"⚠ DB connection failed, using static pages only: {e}", file=sys.stderr)

    # De-dupe by slug
    seen = set()
    deduped = []
    for p in pages:
        if p["slug"] in seen:
            continue
        seen.add(p["slug"])
        deduped.append(p)
    pages = deduped

    print(f"Generating sitemaps for {len(pages)} pages × {len(PHASE_1_LANGS)} languages → {output_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    sitemaps_dir = output_dir / "sitemaps"
    sitemaps_dir.mkdir(parents=True, exist_ok=True)

    # Per-language sitemaps
    for lang in PHASE_1_LANGS:
        xml = render_per_lang_sitemap(lang, PHASE_1_LANGS, pages, origin)
        out = sitemaps_dir / f"{lang}.xml"
        out.write_text(xml, encoding="utf-8")
        print(f"  ✓ {out} ({len(pages)} URLs)")

    # Sitemap index
    index_xml = render_sitemap_index(origin, PHASE_1_LANGS)
    index_out = output_dir / "sitemap.xml"
    index_out.write_text(index_xml, encoding="utf-8")
    print(f"  ✓ {index_out} (index of {len(PHASE_1_LANGS)} sitemaps)")

    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output-dir", default="frontend/public/", help="Where to write sitemap.xml + sitemaps/")
    parser.add_argument("--origin", default=os.environ.get("SITE_ORIGIN", "https://www.arunachalasamudra.co.in"),
                        help="Site origin URL")
    parser.add_argument("--db-url", default=os.environ.get("ASAM_DB_URL"), help="Postgres URL (asyncpg)")
    args = parser.parse_args()

    rc = asyncio.run(main_async(Path(args.output_dir), args.origin, args.db_url))
    sys.exit(rc)


if __name__ == "__main__":
    main()
