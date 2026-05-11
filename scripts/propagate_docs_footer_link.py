#!/usr/bin/env python3
"""One-off: add the /docs/ link to the Learn column after Benchmark on every page."""
from pathlib import Path

SITE = Path(__file__).parent.parent / "site"
SNIPPETS = SITE / "_snippets"

OLD = '<li><a href="/benchmark/">Benchmark</a></li>\n        <li><a href="/docs/cli/">CLI reference</a></li>'
NEW = '<li><a href="/benchmark/">Benchmark</a></li>\n        <li><a href="/docs/">Docs</a></li>\n        <li><a href="/docs/cli/">CLI reference</a></li>'

updated = []
nomatch = []
for html in sorted(SITE.rglob("*.html")):
    if html.name.startswith("og-"):
        continue
    if SNIPPETS in html.parents:
        continue
    raw = html.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8")
    old_block = OLD.replace("\n", "\r\n") if crlf else OLD
    new_block = NEW.replace("\n", "\r\n") if crlf else NEW
    if old_block not in text:
        nomatch.append(str(html.relative_to(SITE)))
        continue
    if new_block in text:
        # Already migrated
        continue
    text = text.replace(old_block, new_block, 1)
    html.write_bytes(text.encode("utf-8"))
    updated.append(str(html.relative_to(SITE)))

print(f"Updated: {len(updated)}")
if nomatch:
    print(f"No match: {len(nomatch)}")
    for p in nomatch:
        print(f"  {p}")
