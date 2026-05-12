#!/usr/bin/env python3
"""
Extract text from a PDF file using pymupdf.
Outputs page-by-page text to stdout for use in Claude Code sessions.

Usage:
    python scripts/read_pdf.py <path_to_pdf> [--pages 1-5] [--max-chars 50000]
"""
import sys
import argparse
from pathlib import Path

def parse_page_range(spec, total):
    """Parse a page range like '1-5', '3', '1-5,8,10-12' into a sorted list of 0-based indices."""
    pages = set()
    for part in spec.split(','):
        part = part.strip()
        if '-' in part:
            a, b = part.split('-', 1)
            pages.update(range(int(a) - 1, int(b)))
        else:
            pages.add(int(part) - 1)
    return sorted(p for p in pages if 0 <= p < total)

def main():
    parser = argparse.ArgumentParser(description='Extract text from a PDF.')
    parser.add_argument('pdf', help='Path to PDF file')
    parser.add_argument('--pages', default=None, help='Page range, e.g. "1-5" or "1,3,5-8"')
    parser.add_argument('--max-chars', type=int, default=80000, help='Max characters to output (default 80000)')
    args = parser.parse_args()

    try:
        import fitz
    except ImportError:
        print('ERROR: pymupdf not installed. Run: pip install pymupdf', file=sys.stderr)
        sys.exit(1)

    path = Path(args.pdf)
    if not path.exists():
        print(f'ERROR: File not found: {path}', file=sys.stderr)
        sys.exit(1)

    doc = fitz.open(str(path))
    total = len(doc)
    print(f'PDF: {path.name}  |  {total} pages\n{"="*60}')

    if args.pages:
        page_indices = parse_page_range(args.pages, total)
    else:
        page_indices = list(range(total))

    out = []
    chars = 0
    for i in page_indices:
        page = doc[i]
        text = page.get_text()
        header = f'\n--- Page {i+1} ---\n'
        out.append(header + text)
        chars += len(header) + len(text)
        if chars >= args.max_chars:
            out.append(f'\n[truncated at {args.max_chars} chars — use --pages or --max-chars to adjust]')
            break

    print(''.join(out))
    doc.close()

if __name__ == '__main__':
    main()
