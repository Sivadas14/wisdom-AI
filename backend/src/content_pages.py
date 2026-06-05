"""
Server-rendered public content pages (SEO layer for migrated .in content).

The React app is a client-rendered SPA, so crawlers/AI engines see only an empty
shell. Public editorial content (the Framer .in pages) is served here as real,
server-rendered HTML — with <title>, meta description, canonical URL, Open Graph
tags, and schema.org JSON-LD — AND styled to match the original .in look & feel
(hero image with title overlay, warm serif palette, inline images, footer nav).

Additive only: it does not alter auth, chat, RAG, subscriptions, or any SPA
route. Wired in via a small documented addition to the server.py catch-all.
"""
from __future__ import annotations

import html as html_lib
import json
from typing import Any, Optional

PRIMARY_BASE_URL = "https://www.arunachalasamudra.com"


def render_content_page(page: dict[str, Any], base_url: str = PRIMARY_BASE_URL, lang: str = "en") -> str:
    """Render a `pages` row (dict) into a complete, SEO-ready, design-matched page.

    Keys: slug, title, body(HTML), meta_description, og_image, canonical_path,
    schema_json (optional), metadata (optional). metadata may contain:
      hero_image, subtitle, faqs[{q,a}], breadcrumb[{name,path}], footer_nav[{group,links[{label,href}]}]
    """
    title = page.get("title") or page["slug"]
    body_html = page.get("body") or ""
    meta_desc = (page.get("meta_description") or "").strip()
    canonical_path = page.get("canonical_path") or f"/{page['slug']}"
    canonical_url = f"{base_url}{canonical_path}"
    og_image = page.get("og_image") or f"{base_url}/og-default.png"
    md = page.get("metadata") or {}
    hero_image = md.get("hero_image")
    subtitle = md.get("subtitle")
    e = html_lib.escape

    # Language switcher disabled (auto-translation turned off; admin review workflow pending)
    _lang_switcher = ""
    _dir = ' dir="rtl"' if lang == "ar" else ""

    # ---------- JSON-LD ----------
    ld: list[dict] = []
    if page.get("schema_json"):
        sj = page["schema_json"]; ld.extend(sj if isinstance(sj, list) else [sj])
    else:
        ld.append({"@context": "https://schema.org", "@type": "Article",
                   "headline": title, "description": meta_desc,
                   "mainEntityOfPage": canonical_url, "image": og_image,
                   "author": {"@type": "Organization", "name": "Arunachala Samudra"},
                   "publisher": {"@type": "Organization", "name": "Arunachala Samudra", "url": base_url}})
    if md.get("breadcrumb"):
        ld.append({"@context": "https://schema.org", "@type": "BreadcrumbList",
                   "itemListElement": [{"@type": "ListItem", "position": i + 1, "name": c["name"],
                                        "item": f"{base_url}{c['path']}"} for i, c in enumerate(md["breadcrumb"])]})
    if md.get("faqs"):
        ld.append({"@context": "https://schema.org", "@type": "FAQPage",
                   "mainEntity": [{"@type": "Question", "name": f["q"],
                                   "acceptedAnswer": {"@type": "Answer", "text": f["a"]}} for f in md["faqs"]]})
    ld_script = "\n".join(f'<script type="application/ld+json">{json.dumps(b, ensure_ascii=False)}</script>' for b in ld)

    # ---------- fragments ----------
    crumbs_html = ""
    if md.get("breadcrumb"):
        parts = []
        for i, c in enumerate(md["breadcrumb"]):
            parts.append(f"<span>{e(c['name'])}</span>" if i == len(md["breadcrumb"]) - 1
                         else f"<a href='{e(c['path'])}'>{e(c['name'])}</a>")
        crumbs_html = "<nav class='crumbs'>" + " › ".join(parts) + "</nav>"

    hero_html = ""
    if hero_image:
        hero_html = f"""
    <header class="hero" style="background-image:linear-gradient(rgba(26,20,16,.28),rgba(26,20,16,.55)),url('{e(hero_image)}')">
      <div class="hero-inner">
        <h1>{e(title)}</h1>
        {f'<p class="hero-sub">{e(subtitle)}</p>' if subtitle else ''}
      </div>
    </header>"""
    else:
        hero_html = f'<header class="plainhead"><h1>{e(title)}</h1>{f"<p class=lead>{e(meta_desc)}</p>" if meta_desc else ""}</header>'

    faq_html = ""
    if md.get("faqs"):
        items = "\n".join(f"<div class='faq'><h3>{e(f['q'])}</h3><p>{e(f['a'])}</p></div>" for f in md["faqs"])
        faq_html = f"<section class='faqs'><h2>Common questions</h2>{items}</section>"

    footer_nav_html = ""
    if md.get("footer_nav"):
        cols = []
        for grp in md["footer_nav"]:
            links = "".join(f"<a href='{e(l['href'])}'>{e(l['label'])}</a>" for l in grp["links"])
            cols.append(f"<div class='fcol'><h4>{e(grp['group'])}</h4>{links}</div>")
        footer_nav_html = "<div class='fnav'>" + "".join(cols) + "</div>"

    return f"""<!doctype html>
<html lang="{e(lang)}"{_dir}>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)} · Arunachala Samudra</title>
<meta name="description" content="{e(meta_desc)}">
<link rel="canonical" href="{e(canonical_url)}">
<meta property="og:type" content="article">
<meta property="og:site_name" content="Arunachala Samudra">
<meta property="og:title" content="{e(title)}">
<meta property="og:description" content="{e(meta_desc)}">
<meta property="og:url" content="{e(canonical_url)}">
<meta property="og:image" content="{e(og_image)}">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{e(title)}">
<meta name="twitter:description" content="{e(meta_desc)}">
<meta name="twitter:image" content="{e(og_image)}">
{ld_script}
<style>
  :root{{--ink:#241c14;--ember:#9c3b12;--saffron:#c8651b;--stone:#6b6258;--sand:#faf5ec;--line:rgba(36,28,20,.12)}}
  *{{box-sizing:border-box}}
  body{{margin:0;background:var(--sand);color:var(--ink);
        font-family:'Iowan Old Style','Palatino Linotype',Georgia,serif;line-height:1.75}}
  .topbar{{background:var(--ember);color:#f7ead9;text-align:center;font-size:.82rem;
           padding:7px 12px;font-family:system-ui,sans-serif}}
  .nav{{display:flex;align-items:center;justify-content:space-between;max-width:1100px;
        margin:0 auto;padding:16px 22px}}
  .brand{{font-size:1.15rem;font-weight:700;color:var(--ember);letter-spacing:.3px}}
  .nav .links{{display:flex;gap:18px;font-family:system-ui,sans-serif;font-size:.9rem;color:var(--stone)}}
  .nav .links a{{color:var(--stone);text-decoration:none}}
  .hero{{background-size:cover;background-position:center;min-height:340px;display:flex;align-items:flex-end;
         background-color:#3a2a1c}}
  .hero-inner{{max-width:1100px;margin:0 auto;width:100%;padding:36px 22px 40px;color:#fff}}
  .hero h1{{font-size:2.6rem;line-height:1.12;margin:0;color:#fff;text-shadow:0 2px 18px rgba(0,0,0,.4)}}
  .hero-sub{{font-size:1.25rem;font-style:italic;margin:.5rem 0 0;color:#f3e7d6;text-shadow:0 1px 10px rgba(0,0,0,.4)}}
  .plainhead{{max-width:760px;margin:0 auto;padding:36px 22px 0}}
  .plainhead h1{{font-size:2.2rem;margin:.2em 0 .3em}}
  main{{max-width:760px;margin:0 auto;padding:8px 22px 56px}}
  .crumbs{{font-family:system-ui,sans-serif;font-size:.82rem;color:var(--stone);margin:18px 0 4px}}
  .crumbs a{{color:var(--ember);text-decoration:none}}
  .body{{margin-top:18px}}
  .body :is(p,li){{font-size:1.08rem}}
  .body h2{{font-size:1.55rem;color:var(--ember);margin:1.7em 0 .35em}}
  .body h3,.body h4{{margin:1.3em 0 .3em}}
  .body img{{max-width:100%;height:auto;border-radius:10px;margin:1.4em 0;display:block}}
  .body blockquote{{border-left:3px solid var(--saffron);margin:1.2em 0;padding:.2em 0 .2em 16px;
                    font-style:italic;color:#4a3a2a;font-size:1.2rem}}
  .faqs{{margin-top:34px}} .faqs h2{{font-size:1.55rem;color:var(--ember)}}
  .faq{{border-left:3px solid rgba(200,101,27,.4);padding-left:14px;margin:14px 0}}
  .faq h3{{margin:.2em 0;font-size:1.1rem}}
  .cta{{margin-top:40px;padding:22px;border:1px solid var(--line);border-radius:12px;background:#fff}}
  .cta a{{display:inline-block;margin-top:10px;background:var(--ember);color:#fbf1e3;padding:11px 20px;
          border-radius:8px;text-decoration:none;font-family:system-ui,sans-serif;font-size:.95rem}}
  footer{{background:#241c14;color:#cdbfae;margin-top:40px;font-family:system-ui,sans-serif}}
  .fnav{{max-width:1100px;margin:0 auto;padding:36px 22px;display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:24px}}
  .fcol h4{{color:#f0e2d0;font-size:.9rem;margin:0 0 10px}}
  .fcol a{{display:block;color:#cdbfae;text-decoration:none;font-size:.85rem;padding:3px 0}}
  .langsel{{margin-left:14px;font-family:system-ui,sans-serif;font-size:.82rem;color:var(--stone);background:#fff;border:1px solid var(--line);border-radius:6px;padding:3px 6px}}
  .copyright{{text-align:center;border-top:1px solid rgba(255,255,255,.1);padding:16px;font-size:.8rem;color:#9c8d7c}}
</style>
</head>
<body>
  <div class="topbar">Now live: Ask Wisdom AI your questions about Bhagavan's teachings →</div>
  <div class="nav">
    <span class="brand">Arunachala Samudra</span>
    <span class="links"><a href="/arunachala">Arunachala</a><a href="/temple/big-temple">Temple</a><a href="/ramana-maharshi">Ramana Maharshi</a><a href="/saints">Saints</a><a href="/sacred-teachings">Sacred Teachings</a><a href="/resources">Resources</a><a href="/about">About</a><a href="/">Wisdom AI</a>{_lang_switcher}</span>
  </div>
  {hero_html}
  <main>
    {crumbs_html}
    <article class="body">{body_html}</article>
    {faq_html}
    <div class="cta">
      <strong>Continue this inquiry with the Wisdom AI</strong>
      <div>Ask anything about Ramana Maharshi's teachings — grounded in the source texts.</div>
      <a href="/">Open the Wisdom AI →</a>
    </div>
  </main>
  <footer>
    {footer_nav_html}
    <div class="copyright">© Arunachala Samudra. All rights reserved.</div>
  </footer>
</body>
</html>"""


async def get_published_page(session, slug: str) -> Optional[dict]:
    """Return a published page row as a dict, or None. Read-only."""
    from sqlalchemy import text as sql_text
    result = await session.execute(
        sql_text(
            "SELECT slug, title, body, meta_description, og_image, canonical_path, "
            "schema_json, metadata, lang FROM pages WHERE slug = :slug AND published = TRUE LIMIT 1"
        ),
        {"slug": slug},
    )
    row = result.mappings().one_or_none()
    return dict(row) if row else None
