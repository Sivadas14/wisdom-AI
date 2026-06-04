"""Public content pages — loader for the migrated .in content.

Lives under src/ so it is bundled into the Docker image (the build copies
backend/src, not backend/scripts). Converts the JSON files in pages_json/ into
rows for the `pages` table; used by the startup seeder in src/migrations.py.
"""
import glob, json, os

JSON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pages_json")

FOOTER_NAV = [
    {"group": "Arunachala", "links": [
        {"label": "Overview", "href": "/arunachala"},
        {"label": "Significance", "href": "/arunachala/significance"},
        {"label": "Girivalam", "href": "/arunachala/girivalam"},
        {"label": "Lingams", "href": "/arunachala/lingams"},
        {"label": "Deepam Festival", "href": "/arunachala/deepam-festival"}]},
    {"group": "Ramana Maharshi", "links": [
        {"label": "Biography", "href": "/ramana-maharshi"},
        {"label": "Disciples", "href": "/ramana-maharshi/disciples"},
        {"label": "Teachings", "href": "/ramana-maharshi/teachings"},
        {"label": "Library", "href": "/library"}]},
    {"group": "Temple", "links": [
        {"label": "Big Temple", "href": "/temple/big-temple"},
        {"label": "Prakarams", "href": "/temple/prakarams"},
        {"label": "Architecture", "href": "/temple/architecture"},
        {"label": "Festivals", "href": "/temple/festivals"}]},
    {"group": "Explore", "links": [
        {"label": "Saints", "href": "/saints"},
        {"label": "Daily Teachings", "href": "/sacred-teachings"},
        {"label": "Articles", "href": "/articles"},
        {"label": "Ebooks", "href": "/library/ebooks"}]},
]


def _readable(seg):
    return seg.replace("-", " ").title()


def breadcrumb_for(canonical_path):
    crumbs = [{"name": "Home", "path": "/"}]
    acc = ""
    for s in [x for x in canonical_path.strip("/").split("/") if x]:
        acc += "/" + s
        crumbs.append({"name": _readable(s), "path": acc})
    return crumbs


def json_to_row(j):
    canonical = j.get("canonical_path") or "/" + j["slug"]
    metadata = {
        "hero_image": j.get("hero_image"),
        "subtitle": j.get("subtitle"),
        "breadcrumb": breadcrumb_for(canonical),
        "footer_nav": FOOTER_NAV,
        "faqs": j.get("faqs") or [],
    }
    return {
        "slug": j["slug"],
        "title": j["title"],
        "body": j.get("body_html") or "",
        "meta_description": j.get("meta_description") or "",
        "og_image": j.get("hero_image") or "https://www.arunachalasamudra.com/og-default.png",
        "canonical_path": canonical,
        "schema_json": j.get("schema_json"),
        "metadata": metadata,
        "lang": "en",
        "source_url": (j.get("source_urls") or [None])[0],
        "published": (j.get("status") == "ok"),
    }


def load_rows():
    return [json_to_row(json.load(open(f, encoding='utf-8'))) for f in sorted(glob.glob(JSON_DIR + "/*.json"))]


# ---------------------------------------------------------------------------
# Shared async seeder — used by startup migration AND the diagnostic endpoint.
# Commits per row so one bad row never discards the good ones.
# ---------------------------------------------------------------------------
_UPSERT_SQL = """
INSERT INTO pages (slug,title,body,meta_description,og_image,canonical_path,
                   schema_json,metadata,lang,source_url,published)
VALUES (:slug,:title,:body,:meta_description,:og_image,:canonical_path,
        CAST(:schema_json AS jsonb),CAST(:metadata AS jsonb),:lang,:source_url,:published)
ON CONFLICT (slug) DO UPDATE SET
    title=EXCLUDED.title, body=EXCLUDED.body,
    meta_description=EXCLUDED.meta_description, og_image=EXCLUDED.og_image,
    canonical_path=EXCLUDED.canonical_path, schema_json=EXCLUDED.schema_json,
    metadata=EXCLUDED.metadata, lang=EXCLUDED.lang,
    source_url=EXCLUDED.source_url, published=EXCLUDED.published,
    last_updated=timezone('UTC', now())
"""


async def upsert_pages(session, rows=None):
    """Upsert page rows; returns (inserted_count, first_error_or_None)."""
    import json as _json
    from sqlalchemy import text as _text
    if rows is None:
        rows = load_rows()
    inserted = 0
    first_error = None
    for p in rows:
        try:
            await session.execute(_text(_UPSERT_SQL), {
                **p,
                "schema_json": _json.dumps(p["schema_json"]) if p.get("schema_json") else None,
                "metadata": _json.dumps(p.get("metadata") or {}),
            })
            await session.commit()
            inserted += 1
        except Exception as e:
            try:
                await session.rollback()
            except Exception:
                pass
            if first_error is None:
                first_error = f"{p.get('slug')}: {e!r}"
    return inserted, first_error
