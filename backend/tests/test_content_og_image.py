"""og:image on content pages must be an absolute URL that exists.

2026-11-18: /saints/paul-brunton sent og:image "/images/paul-brunton/..." —
a bare path, which Facebook, WhatsApp and LinkedIn ignore, so shares had no
preview. Pages without an image fell back to /og-default.png, which never
existed.
"""
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.content_pages import PRIMARY_BASE_URL, render_content_page  # noqa: E402


def _og(html: str) -> str:
    return re.search(r'<meta property="og:image" content="([^"]*)"', html).group(1)


def _page(**kw):
    return {"slug": "saints/test", "title": "T", "body": "<p>x</p>", **kw}


def test_relative_image_is_made_absolute():
    html = render_content_page(_page(og_image="/images/paul-brunton/pb.jpg"))
    assert _og(html) == f"{PRIMARY_BASE_URL}/images/paul-brunton/pb.jpg"


def test_absolute_image_is_left_alone():
    url = "https://framerusercontent.com/images/x.jpg"
    assert _og(render_content_page(_page(og_image=url))) == url


def test_protocol_relative_is_not_double_prefixed():
    url = "//cdn.example.org/x.jpg"
    assert _og(render_content_page(_page(og_image=url))) == url


def test_missing_image_uses_a_file_that_exists():
    og = _og(render_content_page(_page()))
    assert og == f"{PRIMARY_BASE_URL}/images/og-image.png"
    here = os.path.dirname(__file__)
    assert os.path.exists(os.path.join(here, "..", "..", "frontend", "public", "images", "og-image.png"))


def test_twitter_image_matches():
    html = render_content_page(_page(og_image="/images/a.jpg"))
    tw = re.search(r'<meta name="twitter:image" content="([^"]*)"', html).group(1)
    assert tw == f"{PRIMARY_BASE_URL}/images/a.jpg"
