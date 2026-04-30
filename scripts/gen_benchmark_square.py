"""
gen_benchmark_square.py

Generates site/benchmark-square.png — 1080×1080 square crop
showing the headline stats only. Optimized for Twitter/X and square Instagram.
"""

from __future__ import annotations

import os
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1080

BG        = (12,  12,  13)
SURFACE2  = (26,  26,  29)
BORDER    = (34,  34,  38)
BORDER2   = (46,  46,  52)
TEXT      = (232, 232, 236)
MUTED     = (136, 136, 154)
ACCENT    = (200, 240, 96)
DANG_DIM  = (80,  28,  26)
DANGER    = (216, 86,  76)
ACCENT_DIM = (40, 62,  16)
CAT_COLORS = {
    "scope":        (90,  130, 210),
    "architecture": (155, 95,  215),
    "anti-pattern": (215, 155, 55),
}

FONTS = (
    r"C:\Users\hi\AppData\Roaming\Claude\local-agent-mode-sessions\skills-plugin"
    r"\51edae35-ca04-45d6-9040-75ec17a65f4e\4bb56a8f-0bbc-4467-8550-77f86265f5da"
    r"\skills\canvas-design\canvas-fonts"
)

def fnt(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(FONTS, name), size)

def dim(c: tuple, f: float) -> tuple:
    return tuple(min(255, max(0, int(v * f))) for v in c)

def brighten(c: tuple, a: int) -> tuple:
    return tuple(min(255, v + a) for v in c)

img = Image.new("RGB", (W, H), BG)
draw = ImageDraw.Draw(img)

# Grid dots
for gx in range(0, W + 54, 54):
    for gy in range(0, H + 54, 54):
        draw.ellipse([gx - 1, gy - 1, gx + 1, gy + 1], fill=(20, 20, 22))

# Radial glow
for r_s in range(550, 0, -5):
    intensity = int(7 * (550 - r_s) / 550)
    c = (BG[0] + intensity, BG[1] + intensity, BG[2] + intensity)
    draw.ellipse([W // 2 - r_s, H // 3 - r_s, W // 2 + r_s, H // 3 + r_s], fill=c)

f_logo    = fnt("InstrumentSerif-Italic.ttf", 26)
f_hero    = fnt("InstrumentSerif-Italic.ttf", 340)
f_mono    = fnt("DMMono-Regular.ttf", 15)
f_mono_xs = fnt("DMMono-Regular.ttf", 11)
f_geist_b = fnt("GeistMono-Bold.ttf", 40)

MARGIN = 72

def ctext(draw, text, y, font, color):
    bb = draw.textbbox((0, 0), text, font=font)
    tw = bb[2] - bb[0]
    draw.text(((W - tw) // 2, y), text, font=font, fill=color)

def rr(draw, x, y, w, h, r, color):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=r, fill=color)

# ── Header ─────────────────────────────────────────────────────────────────────
ctext(draw, "mneme", 34, f_logo, TEXT)
draw.line([(MARGIN, 76), (W - MARGIN, 76)], fill=BORDER2, width=1)

# Tick marks flanking hero
for tx, sign in [(MARGIN, 1), (W - MARGIN, -1)]:
    for j in range(5):
        ty = 88 + j * 20
        tlen = 16 if j == 0 else 8
        draw.line([(tx, ty), (tx + sign * tlen, ty)], fill=BORDER2, width=1)

# ── Hero "100%" — full-width dominant ──────────────────────────────────────────
hero_text = "100%"
hero_y = 80
hero_bb = draw.textbbox((0, 0), hero_text, font=f_hero)
hero_tw = hero_bb[2] - hero_bb[0]
draw.text(((W - hero_tw) // 2, hero_y), hero_text, font=f_hero, fill=TEXT)

sub_y = hero_y + hero_bb[3] + 14
ctext(draw, "violation catch rate", sub_y, f_mono, MUTED)
ctext(draw, "5 of 5 benchmark scenarios  ·  0 violations survived",
      sub_y + 24, f_mono_xs, MUTED)

# ── Divider ─────────────────────────────────────────────────────────────────────
div_y = sub_y + 52
draw.line([(MARGIN, div_y), (W - MARGIN, div_y)], fill=BORDER2, width=1)

# ── Summary section below hero ────────────────────────────────────────────────
FOOTER_Y = H - 64
score_y = div_y + 28
ctext(draw, "5 / 5  PASS", score_y, f_geist_b, ACCENT)

# ── Compact scenario rows: name  ×N → 0 ───────────────────────────────────────
SCENARIOS = [
    ("feature boundary",      "scope",        6),
    ("storage backend",       "architecture", 5),
    ("framework abstraction", "anti-pattern", 3),
    ("retrieval complexity",  "architecture", 3),
    ("infra scope creep",     "scope",        1),
]

row_start_y = score_y + 58
ROW_H = 44
BAR_X = MARGIN + 220
MAX_V = 6
BAR_TRACK = W - MARGIN - BAR_X  # 1008 - 220 - 72 = 716

f_mono_sm2 = fnt("DMMono-Regular.ttf", 12)

for i, (name, cat, violations) in enumerate(SCENARIOS):
    ry = row_start_y + i * ROW_H
    cat_c = CAT_COLORS.get(cat, (100, 100, 100))

    if i % 2 == 0:
        draw.rectangle([MARGIN, ry, W - MARGIN, ry + ROW_H - 2], fill=(14, 14, 15))

    # Name
    draw.text((MARGIN, ry + 12), name, font=f_mono_sm2, fill=TEXT)

    # Before bar (compact, 12px tall)
    bh = 14
    by = ry + 8
    fw = int(violations / MAX_V * BAR_TRACK)
    rr(draw, BAR_X, by, BAR_TRACK, bh, 3, (70, 24, 22))
    if fw > 0:
        rr(draw, BAR_X, by, fw, bh, 3, DANGER)
        # tick marks
        ti = fw / violations
        for t in range(violations):
            tx = int(BAR_X + (t + 0.5) * ti)
            draw.line([(tx, by + 3), (tx, by + bh - 3)], fill=dim(DANGER, 0.5), width=1)

    # After (zero)
    by2 = ry + 26
    rr(draw, BAR_X, by2, BAR_TRACK, bh, 3, SURFACE2)
    rr(draw, BAR_X, by2, 26, bh, 3, ACCENT_DIM)
    draw.text((BAR_X + 6, by2 + 1), "0", font=f_mono_xs, fill=ACCENT)
    # PASS badge
    pw = 38
    rr(draw, BAR_X + BAR_TRACK - pw - 2, by2, pw, bh, 3, ACCENT_DIM)
    draw.text((BAR_X + BAR_TRACK - pw + 4, by2 + 1), "PASS", font=f_mono_xs, fill=ACCENT)

# ── Tagline + footer — anchored relative to content bottom ────────────────────
tagline_y = row_start_y + len(SCENARIOS) * ROW_H + 24
ctext(draw, "without memory, every conversation starts from scratch.",
      tagline_y, fnt("InstrumentSerif-Italic.ttf", 19), MUTED)

footer_rule_y = tagline_y + 60
draw.line([(MARGIN, footer_rule_y), (W - MARGIN, footer_rule_y)], fill=BORDER, width=1)
ctext(draw, "mneme  ·  persistent project memory for llm workflows",
      footer_rule_y + 16, f_mono_xs, MUTED)

# ── Save ────────────────────────────────────────────────────────────────────────
out = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "site",
                                    "benchmark-square.png"))
img.save(out, "PNG")
print(f"Saved: {out}")
