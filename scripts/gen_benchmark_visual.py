"""
gen_benchmark_visual.py

Generates site/benchmark-visual.png — a 1080×1350 dark-mode social graphic
showing Mneme's benchmark results as a before/after violation visualization.

Philosophy: Null Signal — the drama of absence. Bars that would fill with
violations collapse to zero when Mneme enforces project memory.
"""

from __future__ import annotations

import os
import math
from PIL import Image, ImageDraw, ImageFont

# ── Canvas ────────────────────────────────────────────────────────────────────
W, H = 1080, 1350

# ── Brand palette (from site/index.html CSS vars) ─────────────────────────────
BG       = (12,  12,  13)
SURFACE  = (20,  20,  22)
SURFACE2 = (26,  26,  29)
BORDER   = (34,  34,  38)
BORDER2  = (46,  46,  52)
TEXT     = (232, 232, 236)
MUTED    = (136, 136, 154)
ACCENT   = (200, 240, 96)    # lime #c8f060
TEAL     = (139, 224, 200)
DANGER   = (216, 86,  76)    # muted red for unguarded violations
DANG_DIM = (90,  36,  32)    # dark red for bar track

ACCENT_DIM = (40, 62, 16)    # dark lime for zero-bar background
CAT_COLORS = {
    "scope":        (90,  130, 210),
    "architecture": (155, 95,  215),
    "anti-pattern": (215, 155, 55),
}

# ── Font paths ────────────────────────────────────────────────────────────────
FONTS = (
    r"C:\Users\hi\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin"
    r"\51edae35-ca04-45d6-9040-75ec17a65f4e\4bb56a8f-0bbc-4467-8550-77f86265f5da"
    r"\skills\canvas-design\canvas-fonts"
)

def fnt(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(FONTS, name), size)

# ── Benchmark data ─────────────────────────────────────────────────────────────
SCENARIOS = [
    {"name": "feature boundary",      "cat": "scope",        "base": 6, "enh": 0},
    {"name": "storage backend",       "cat": "architecture", "base": 5, "enh": 0},
    {"name": "framework abstraction", "cat": "anti-pattern", "base": 3, "enh": 0},
    {"name": "retrieval complexity",  "cat": "architecture", "base": 3, "enh": 0},
    {"name": "infra scope creep",     "cat": "scope",        "base": 1, "enh": 0},
]
MAX_VIOLATIONS = 6

# ── Helpers ────────────────────────────────────────────────────────────────────
def ctext(draw: ImageDraw.ImageDraw, text: str, y: int,
          font: ImageFont.FreeTypeFont, color: tuple, canvas_w: int = W) -> int:
    """Draw text centered horizontally. Returns text width."""
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((canvas_w - tw) // 2, y), text, font=font, fill=color)
    return tw

def rr(draw: ImageDraw.ImageDraw,
       x: int, y: int, w: int, h: int, r: int, color: tuple) -> None:
    """Draw a filled rounded rectangle."""
    draw.rounded_rectangle([x, y, x + w, y + h], radius=r, fill=color)

def dim(c: tuple, factor: float) -> tuple:
    """Multiply an RGB tuple by factor, clamped to [0,255]."""
    return tuple(min(255, max(0, int(v * factor))) for v in c)

def brighten(c: tuple, amount: int) -> tuple:
    return tuple(min(255, v + amount) for v in c)

# ── Build image ────────────────────────────────────────────────────────────────
img = Image.new("RGB", (W, H), BG)
draw = ImageDraw.Draw(img)

# ── Subtle radial glow near top-center ────────────────────────────────────────
cx, cy_glow = W // 2, 340
for r_step in range(700, 0, -4):
    intensity = int(6 * (700 - r_step) / 700)
    col = (BG[0] + intensity, BG[1] + intensity, BG[2] + intensity)
    draw.ellipse([cx - r_step, cy_glow - r_step,
                  cx + r_step, cy_glow + r_step], fill=col)

# ── Grid dots (very subtle) ────────────────────────────────────────────────────
for gx in range(0, W + 54, 54):
    for gy in range(0, H + 54, 54):
        draw.ellipse([gx - 1, gy - 1, gx + 1, gy + 1], fill=(20, 20, 22))

# ── Load fonts ────────────────────────────────────────────────────────────────
f_logo      = fnt("InstrumentSerif-Italic.ttf", 30)
f_hero      = fnt("InstrumentSerif-Italic.ttf", 250)
f_catch_lbl = fnt("InstrumentSerif-Regular.ttf", 48)
f_mono      = fnt("DMMono-Regular.ttf", 16)
f_mono_sm   = fnt("DMMono-Regular.ttf", 13)
f_mono_xs   = fnt("DMMono-Regular.ttf", 11)
f_geist_b   = fnt("GeistMono-Bold.ttf", 13)
f_geist_xl  = fnt("GeistMono-Bold.ttf", 42)
f_ibm       = fnt("IBMPlexMono-Regular.ttf", 13)
f_ibm_b     = fnt("IBMPlexMono-Bold.ttf", 13)

MARGIN = 72

# ═══════════════════════════════════════════════════════════════════
# SECTION 1: Header wordmark
# ═══════════════════════════════════════════════════════════════════
ctext(draw, "mneme", 54, f_logo, TEXT)
draw.line([(MARGIN, 108), (W - MARGIN, 108)], fill=BORDER2, width=1)

# Decorative tick marks flanking the hero zone
for tx, sign in [(MARGIN, 1), (W - MARGIN, -1)]:
    for j in range(5):
        ty = 130 + j * 22
        tlen = 18 if j == 0 else 9
        draw.line([(tx, ty), (tx + sign * tlen, ty)], fill=BORDER2, width=1)

# ═══════════════════════════════════════════════════════════════════
# SECTION 2: Hero "100%"
# ═══════════════════════════════════════════════════════════════════
hero_text = "100%"
hero_y = 120

# Measure actual bounding box so we can position subtext accurately
hero_bbox = draw.textbbox((0, 0), hero_text, font=f_hero)
hero_h = hero_bbox[3] - hero_bbox[1]
hero_tw = hero_bbox[2] - hero_bbox[0]

# Draw hero numeral centered
hero_x = (W - hero_tw) // 2
draw.text((hero_x, hero_y), hero_text, font=f_hero, fill=TEXT)

# Sub-text positioned using actual glyph bottom (bbox[3] = absolute bottom offset)
sub_y = hero_y + hero_bbox[3] + 20
ctext(draw, "violation catch rate", sub_y, f_mono, MUTED)
ctext(draw, "5 of 5 benchmark scenarios  ·  0 violations survived",
      sub_y + 26, f_mono_xs, MUTED)

# ═══════════════════════════════════════════════════════════════════
# SECTION 3: Divider + column headers
# ═══════════════════════════════════════════════════════════════════
div_y = sub_y + 68
draw.line([(MARGIN, div_y), (W - MARGIN, div_y)], fill=BORDER2, width=1)

LABEL_W = 64    # "before" / "mneme " label column width
BAR_X   = MARGIN + LABEL_W + 8   # bar starts here: 72+64+8 = 144
BAR_TRACK_W = W - MARGIN - BAR_X  # 1080-72-144 = 864px

col_hdr_y = div_y + 14
draw.text((MARGIN, col_hdr_y), "scenario", font=f_mono_xs, fill=MUTED)
draw.text((BAR_X, col_hdr_y),
          "without mneme   /   with mneme", font=f_mono_xs, fill=MUTED)

# ═══════════════════════════════════════════════════════════════════
# SECTION 4: Scenario rows
# ═══════════════════════════════════════════════════════════════════
ROW_H      = 108
ROW_START_Y = col_hdr_y + 28
BAR_H      = 22

for i, s in enumerate(SCENARIOS):
    ry = ROW_START_Y + i * ROW_H
    cat_c  = CAT_COLORS.get(s["cat"], (100, 100, 100))

    # Row background
    if i % 2 == 0:
        draw.rectangle([MARGIN, ry, W - MARGIN, ry + ROW_H - 2], fill=(14, 14, 15))

    # Category pill
    pill_bg = dim(cat_c, 0.22)
    rr(draw, MARGIN, ry + 10, 94, 15, 4, pill_bg)
    draw.text((MARGIN + 6, ry + 12), s["cat"], font=f_mono_xs,
              fill=brighten(cat_c, 70))

    # Scenario name
    draw.text((MARGIN, ry + 30), s["name"], font=f_mono, fill=TEXT)

    # ── Before bar: unguarded violations ──────────────────────────
    bar1_y   = ry + 56
    fill_pct = s["base"] / MAX_VIOLATIONS
    fill_w   = max(int(fill_pct * BAR_TRACK_W), 0)

    # Track (dark red)
    rr(draw, BAR_X, bar1_y, BAR_TRACK_W, BAR_H, 4, DANG_DIM)
    # Fill (danger)
    if fill_w > 0:
        rr(draw, BAR_X, bar1_y, fill_w, BAR_H, 4, DANGER)
        # Tick marks — one per violation, scored into the bar
        if s["base"] > 0:
            tick_interval = fill_w / s["base"]
            tick_color = dim(DANGER, 0.55)
            for t in range(s["base"]):
                tx = int(BAR_X + (t + 0.5) * tick_interval)
                draw.line([(tx, bar1_y + 5), (tx, bar1_y + BAR_H - 5)],
                          fill=tick_color, width=1)

    # "before" label
    draw.text((MARGIN, bar1_y + 4), "before", font=f_mono_xs, fill=(180, 80, 72))

    # Violation count to the right of fill
    vc_x = BAR_X + fill_w + 8
    if vc_x + 30 < BAR_X + BAR_TRACK_W:
        draw.text((vc_x, bar1_y + 4), f"×{s['base']}", font=f_mono_xs, fill=MUTED)
    else:
        draw.text((BAR_X + BAR_TRACK_W - 32, bar1_y + 4),
                  f"×{s['base']}", font=f_mono_xs, fill=TEXT)

    # ── After bar: Mneme-guarded (zero violations) ─────────────────
    bar2_y = ry + 82

    # Track (almost black)
    rr(draw, BAR_X, bar2_y, BAR_TRACK_W, BAR_H, 4, SURFACE2)

    # Tiny "0" fill pill at left edge
    rr(draw, BAR_X, bar2_y, 32, BAR_H, 4, ACCENT_DIM)
    draw.text((BAR_X + 8, bar2_y + 4), "0", font=f_mono_xs, fill=ACCENT)

    # "mneme " label
    draw.text((MARGIN, bar2_y + 4), "mneme ", font=f_mono_xs, fill=(130, 190, 60))

    # PASS badge at right
    pass_w = 44
    rr(draw, BAR_X + BAR_TRACK_W - pass_w - 4, bar2_y,
       pass_w, BAR_H, 4, ACCENT_DIM)
    draw.text((BAR_X + BAR_TRACK_W - pass_w + 4, bar2_y + 4),
              "PASS", font=f_mono_xs, fill=ACCENT)

    # Row separator
    if i < len(SCENARIOS) - 1:
        draw.line([(MARGIN, ry + ROW_H - 2), (W - MARGIN, ry + ROW_H - 2)],
                  fill=BORDER, width=1)

# ═══════════════════════════════════════════════════════════════════
# SECTION 5: Bottom summary
# ═══════════════════════════════════════════════════════════════════
summary_y = ROW_START_Y + len(SCENARIOS) * ROW_H + 16
draw.line([(MARGIN, summary_y), (W - MARGIN, summary_y)], fill=BORDER2, width=1)

# "5/5 PASS" in large monospaced
score_y = summary_y + 26
ctext(draw, "5 / 5  PASS", score_y, f_geist_xl, ACCENT)

# Category breakdown pills — centered
cat_pill_y = score_y + 70
PILL_W = 152
PILL_GAP = 14
CAT_ENTRIES = [("architecture", "2/2"), ("scope", "2/2"), ("anti-pattern", "1/1")]
total_pill_w = len(CAT_ENTRIES) * PILL_W + (len(CAT_ENTRIES) - 1) * PILL_GAP
pill_x = (W - total_pill_w) // 2
for cat, score_label in CAT_ENTRIES:
    c = CAT_COLORS.get(cat, (100, 100, 100))
    rr(draw, pill_x, cat_pill_y, PILL_W, 30, 6, dim(c, 0.22))
    lbl = f"{cat}  {score_label}"
    draw.text((pill_x + 10, cat_pill_y + 8), lbl, font=f_mono_xs, fill=brighten(c, 70))
    pill_x += PILL_W + PILL_GAP

# ── Tagline quote ─────────────────────────────────────────────────────────────
quote_y = cat_pill_y + 56
ctext(draw,
      "without memory, every conversation starts from scratch.",
      quote_y, fnt("InstrumentSerif-Italic.ttf", 22), MUTED)

# ═══════════════════════════════════════════════════════════════════
# SECTION 6: Footer
# ═══════════════════════════════════════════════════════════════════
footer_sep_y = H - 72
draw.line([(MARGIN, footer_sep_y), (W - MARGIN, footer_sep_y)],
          fill=BORDER, width=1)
ctext(draw, "mneme  ·  persistent project memory for llm workflows",
      footer_sep_y + 20, f_mono_xs, MUTED)

# ── Save ──────────────────────────────────────────────────────────────────────
out = os.path.join(os.path.dirname(__file__), "..", "site", "benchmark-visual.png")
out = os.path.normpath(out)
img.save(out, "PNG")
print(f"Saved: {out}")
print(f"Dimensions: {W}×{H}")
