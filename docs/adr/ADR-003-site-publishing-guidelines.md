# ADR-003: Site Publishing Guidelines

**Status:** Accepted  
**Date:** 2026-05-01  
**Deciders:** Theo Valmis

---

## Context

The Mneme marketing site (`mnemehq.com`) is maintained as static HTML in `site/` and deployed
directly to cPanel hosting via a Python script. Without documented conventions, the following
problems recur:

- Working files (downloaded pages, edits in progress) accumulate in the repo root alongside site assets
- Asset naming causes stale-cache issues when overwriting files on the server
- Logo and image formats get confused between dark/light variants and transparent vs. opaque PNGs
- Deploy scope is ambiguous — which files belong in `site/` and which don't

This ADR documents the decisions made to resolve these problems.

---

## Decisions

### 1. Canonical deploy path

All site assets that belong on `mnemehq.com` live under `site/`. The deploy script
(`scripts/deploy.py`) walks `site/` recursively, skipping `.md` files, and uploads everything
else to `/home/cadafdd1/mnemehq.com` via the cPanel Fileman API.

**Do not** place site assets in the repo root or other directories and expect them to be deployed.

### 2. Working files stay out of `site/`

Files downloaded for editing from external domains (e.g. `theovalmis_index.html`,
`why-i-built-mneme.html`) are working copies only. They must:

- Live in the repo root or a `scratch/` directory during editing
- Be uploaded directly to their target host via the cPanel API once complete
- Not be committed to `site/` or deployed via `scripts/deploy.py`

### 3. Asset versioning for cache-busting

cPanel does not reliably overwrite files in-place when re-uploading. When a static asset
(image, font, etc.) is updated, use a versioned filename rather than relying on overwrite:

```
logo.png   →  logo-v2.png, logo-v3.png ...
og.png     →  og-v2.png ...
```

Update all HTML references to the new filename as part of the same change. Do not rely on
query-string cache-busting (`?v=2`) as it does not affect the server-side file.

### 4. Logo and image format requirements

The site uses a dark background (`#0c0c0d`). Assets must be prepared accordingly:

| Asset | Required format | Notes |
|-------|----------------|-------|
| Nav logo | Transparent PNG, light-coloured marks | Use `mneme_logo_light.png` as source; remove white background; recolour dark text to `#e8e8ec` |
| Favicon | PNG 512×512, any background | Use `mneme_favicon.png` directly |
| OG image | Opaque PNG 1200×630 | Background must be opaque; no transparency |

Source logo files live in `mneme logo/` (repo root). Do not commit processed variants back to
`mneme logo/` — the source files are the truth.

The `mneme_logo_dark.png` variant (2000×2000, dark navy background) is **not suitable** for
use on the dark site — it creates a visible background box in the nav.

### 5. Nav and page structure conventions

All pages share a canonical nav:

```
Logo  |  How it works  ·  Demo  ·  Benchmarks  ·  Use cases  ·  GitHub  |  Get started (CTA)
```

- Pages within `/use-cases/` mark `Use cases` as `.active`
- `/demo.html` marks `Demo` as `.active`
- Anchor links to homepage sections use `/#section-id` from all subpages
- `id="benchmarks"` is on the "See the difference" section in `index.html`
- `id="how-it-works"` is on the how-it-works section in `index.html`

### 6. Typography rules

- **Body / nav / UI:** Inter
- **Hero `h1` only:** Instrument Serif
- **Code / terminal / labels:** DM Mono
- Instrument Serif must not be used on `h2`, `h3`, or any sub-heading level

### 7. theovalmis.com files

Pages on `theovalmis.com` are edited by downloading via cPanel API, modifying locally, and
re-uploading to `/home/cadafdd1/public_html/`. They are **not** part of the Mneme site deploy
and must not appear in `site/`.

---

## Rationale

- **Cache-busting by rename** is the only reliable method on cPanel shared hosting without CDN
  invalidation controls.
- **Working files in root** prevents `scripts/deploy.py` from accidentally uploading half-edited
  content to production.
- **Logo format rules** exist because the dark-background site requires transparent assets; the
  original logo PNGs ship with opaque backgrounds that are invisible or create visible boxes
  without processing.

---

## Consequences

- New site assets must be placed in `site/` before running the deploy script
- Any updated static asset gets a new versioned filename
- Working/scratch files for external domains go in repo root and are gitignored if sensitive
- Logo processing (background removal, text recolour) is a manual step when updating brand assets

---

## Related

- ADR-001: Positioning and Messaging
- ADR-002: Repository Boundary for Internal Operational Tooling
- `scripts/deploy.py` — canonical deploy script
- `mneme logo/` — source brand assets
