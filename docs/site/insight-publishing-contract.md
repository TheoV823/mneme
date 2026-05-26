# Insight publishing contract

Adding a new article under `site/insights/<slug>/index.html` is **not enough on its own**. The publishing pipeline does not auto-discover new articles. Each one requires explicit registration in four places. CI enforces this via `scripts/check_insights.py` (see `.github/workflows/check-insights.yml`).

## What the contract requires

For every `site/insights/<slug>/index.html`, the following must all be true:

1. **Sitemap entry** — a `<url><loc>https://mnemehq.com/insights/<slug>/</loc>...</url>` block in [`site/sitemap.xml`](../../site/sitemap.xml).
2. **Insights hub card** — an `<a href="/insights/<slug>/" class="insight-card-link">...</a>` card on [`site/insights/index.html`](../../site/insights/index.html) (and a matching entry in the page's `schema.org` `hasPart` JSON-LD array).
3. **Local OG image** — `og.png` co-located in the article directory: `site/insights/<slug>/og.png`.
4. **OG meta tags resolve** — both `<meta property="og:image">` and `<meta name="twitter:image">` in the article must point to a PNG file that actually exists under `site/`.
5. **At least one incoming internal link** — at least one other HTML file under `site/` must link to `/insights/<slug>/`. The hub card from check (2) satisfies this; reciprocal links from related articles are recommended for SEO depth.

## How to register a new insight

After writing `site/insights/<slug>/index.html`, do the following before opening the PR:

### 1. OG image

Add three entries to `scripts/ensure_og_coverage.py`:

- `TEMPLATES` — a `(filename, tag, heading, font_size, subtitle, url_path)` tuple. Choose a short `og-insights-<short-slug>.html` filename.
- `NEW_MAP_ENTRIES` — maps the template filename to the output `og.png` path (e.g. `"og-insights-<short-slug>.html": "insights/<slug>/og.png"`).
- `HTML_FIXES` is only needed if the article points at the generic site OG instead of its own. Articles whose `og:image` already points to the correct article-local PNG do not need an entry here.

Then run:

```bash
python scripts/ensure_og_coverage.py     # materializes the template and patches TEMPLATE_MAP
python scripts/generate_og_images.py     # renders all og.png files via Playwright
```

`generate_og_images.py` requires `playwright` and a chromium install (`pip install playwright && playwright install chromium`).

### 2. Sitemap

Append a `<url>` block to `site/sitemap.xml`:

```xml
<url>
  <loc>https://mnemehq.com/insights/<slug>/</loc>
  <changefreq>monthly</changefreq>
  <priority>0.8</priority>
</url>
```

### 3. Insights hub card

Add a card to `site/insights/index.html` in the most thematically appropriate `cards-section` (e.g. `governance-problem`, `ai-native`, `market-context`). Mirror the structure of neighboring cards: eyebrow tag, read time, `<h3>` title, summary `<p>`, and the `read-pill` footer. Also append a matching `{"@type": "Article", "name": "...", "url": "..."}` entry to the `hasPart` array in the `CollectionPage` JSON-LD block at the top of the file.

### 4. Internal links

The hub card from step 3 already satisfies the "at least one incoming internal link" requirement. For SEO depth, also add reciprocal cross-links from thematically related insights (the article's own `related-essays` panel links outward; the reciprocal inward links are the high-value pairing).

## Running the check locally

```bash
python scripts/check_insights.py
```

Exit code is `0` if every article is fully registered, `1` if any check fails. Error messages name the failing slug and condition, e.g.:

```
  my-new-article/
    - Missing sitemap entry for site/insights/my-new-article/
    - Missing og.png for site/insights/my-new-article/
    - No incoming internal links found for my-new-article
```

## CI behavior

`.github/workflows/check-insights.yml` runs `check_insights.py` on every PR that touches any of:

- `site/insights/**`
- `site/insights/index.html`
- `site/sitemap.xml`
- `scripts/**`

A failing check blocks the PR.

## What the publishing scripts do not do

- They do **not** auto-discover new articles.
- They do **not** auto-create OG templates from article HTML.
- They do **not** auto-insert sitemap entries.
- They do **not** auto-insert insights hub cards.
- They do **not** auto-insert reciprocal cross-links.

The deploy workflow (`.github/workflows/deploy-site.yml`) only uploads changed files via the cPanel API and purges the Cloudflare cache. It performs no content generation.

If automation for any of the above is desired in the future, it should be implemented as an additional script invoked from CI on a separate workflow — not bolted onto deploy.
