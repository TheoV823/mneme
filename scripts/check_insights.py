#!/usr/bin/env python3
"""
Validates that every site/insights/<slug>/index.html is fully registered for
publishing. Per docs/site/insight-publishing-contract.md, a new insight needs
explicit registration in: sitemap, insights hub (card + JSON-LD), local og.png,
correct og:image / twitter:image meta tags, and at least one incoming internal
link from elsewhere on the site.

Checks (all hard errors):
  ERROR  -- slug missing from site/sitemap.xml
  ERROR  -- slug has no card on site/insights/index.html
  ERROR  -- og.png missing in the article directory
  ERROR  -- og:image points to a PNG that does not exist
  ERROR  -- twitter:image points to a PNG that does not exist
  ERROR  -- no incoming internal links from elsewhere in site/

Exit codes:  0 = clean   1 = errors found
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SITE_DIR = REPO_ROOT / "site"
INSIGHTS_DIR = SITE_DIR / "insights"
HUB = INSIGHTS_DIR / "index.html"
SITEMAP = SITE_DIR / "sitemap.xml"

SITE_BASE = "https://mnemehq.com"


def article_slugs() -> list[str]:
    """Return every <slug> with an insights/<slug>/index.html, excluding the hub."""
    out = []
    for child in sorted(INSIGHTS_DIR.iterdir()):
        if not child.is_dir():
            continue
        if (child / "index.html").exists():
            out.append(child.name)
    return out


def sitemap_slugs() -> set[str]:
    """Return slugs listed under https://mnemehq.com/insights/<slug>/ in sitemap.xml."""
    if not SITEMAP.exists():
        return set()
    text = SITEMAP.read_text(encoding="utf-8")
    return set(re.findall(r"https://mnemehq\.com/insights/([^/]+)/", text))


def hub_card_slugs() -> set[str]:
    """Return slugs that have a card (<a ... class='insight-card-link'>) on the hub."""
    if not HUB.exists():
        return set()
    html = HUB.read_text(encoding="utf-8")
    slugs = set()
    for m in re.finditer(r'<a\s+([^>]+)>', html):
        attrs = m.group(1)
        if "insight-card-link" not in attrs:
            continue
        href_m = re.search(r'href="/insights/([^/"]+)/"', attrs)
        if href_m:
            slugs.add(href_m.group(1))
    return slugs


def article_meta_image_urls(article_html: str) -> tuple[str | None, str | None]:
    """Return (og:image, twitter:image) URL values from an article's meta tags."""
    og = re.search(r'<meta\s+property="og:image"\s+content="([^"]+)"', article_html)
    tw = re.search(r'<meta\s+name="twitter:image"\s+content="([^"]+)"', article_html)
    return (og.group(1) if og else None, tw.group(1) if tw else None)


def site_url_to_local_path(url: str) -> Path | None:
    """Convert an absolute mnemehq.com URL to a local site/ path, or None if foreign."""
    if not url.startswith(SITE_BASE + "/"):
        return None
    rel = url[len(SITE_BASE) + 1:]
    return SITE_DIR / rel


def incoming_link_pages(slug: str) -> list[Path]:
    """Find every site/**.html that contains /insights/<slug>/, excluding the article itself."""
    needle = f"/insights/{slug}/"
    article_dir = INSIGHTS_DIR / slug
    hits: list[Path] = []
    for path in SITE_DIR.rglob("*.html"):
        # Skip the article's own files
        try:
            path.relative_to(article_dir)
            continue
        except ValueError:
            pass
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if needle in text:
            hits.append(path)
    return hits


def check_slug(slug: str, sitemap_set: set[str], hub_set: set[str]) -> list[str]:
    """Return a list of error messages for this slug (empty = clean)."""
    errors: list[str] = []
    article_dir = INSIGHTS_DIR / slug
    article_path = article_dir / "index.html"
    rel = f"site/insights/{slug}/"

    # 1. sitemap
    if slug not in sitemap_set:
        errors.append(f"Missing sitemap entry for {rel}")

    # 2. hub card
    if slug not in hub_set:
        errors.append(f"Missing insights index card for {slug}")

    # 3. og.png present
    og_path = article_dir / "og.png"
    if not og_path.exists():
        errors.append(f"Missing og.png for {rel}")

    # 4. og:image / twitter:image point to existing PNGs
    try:
        html = article_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        errors.append(f"Could not read {article_path.relative_to(REPO_ROOT)}: {exc}")
        return errors

    og_url, tw_url = article_meta_image_urls(html)
    for label, url in (("og:image", og_url), ("twitter:image", tw_url)):
        if url is None:
            errors.append(f"{label} meta tag missing in {rel}")
            continue
        local = site_url_to_local_path(url)
        if local is None:
            errors.append(
                f"{label} for {slug} points off-site ({url}); expected a mnemehq.com PNG"
            )
            continue
        if not local.exists():
            errors.append(
                f"{label} for {slug} points to a PNG that does not exist: {url}"
            )

    # 5. at least one incoming internal link from another site page
    incoming = incoming_link_pages(slug)
    if not incoming:
        errors.append(f"No incoming internal links found for {slug}")

    return errors


def main() -> int:
    if not HUB.exists():
        print(f"ERROR  Hub not found: {HUB}", file=sys.stderr)
        return 1
    if not SITEMAP.exists():
        print(f"ERROR  Sitemap not found: {SITEMAP}", file=sys.stderr)
        return 1

    slugs = article_slugs()
    sitemap_set = sitemap_slugs()
    hub_set = hub_card_slugs()

    all_errors: dict[str, list[str]] = {}
    for slug in slugs:
        errs = check_slug(slug, sitemap_set, hub_set)
        if errs:
            all_errors[slug] = errs

    total_errors = sum(len(v) for v in all_errors.values())

    if total_errors:
        print(
            f"FAIL  {len(all_errors)}/{len(slugs)} insight articles failed publishing "
            f"checks ({total_errors} error(s)). Each new insight requires explicit "
            f"registration; see docs/site/insight-publishing-contract.md.",
            file=sys.stderr,
        )
        print(file=sys.stderr)
        for slug in sorted(all_errors):
            print(f"  {slug}/", file=sys.stderr)
            for msg in all_errors[slug]:
                print(f"    - {msg}", file=sys.stderr)
        return 1

    print(f"OK  {len(slugs)} insight articles fully registered.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
