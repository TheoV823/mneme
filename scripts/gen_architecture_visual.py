"""
gen_architecture_visual.py

Generates site/benchmark-architecture.png — 1080×1350 architecture flow
diagram showing the Mneme enforcement pipeline as a before/after two-column
flow. Carousel slide 2.
"""

from __future__ import annotations

import os
import math
from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1350

BG        = (12,  12,  13)
SURFACE2  = (26,  26,  29)
BORDER    = (34,  34,  38)
BORDER2   = (46,  46,  52)
TEXT      = (232, 232, 236)
MUTED     = (136, 136, 154)
ACCENT    = (200, 240, 96)
TEAL      = (139, 224, 200)
DANGER    = (216, 86,  76)
DANG_DIM  = (80,  28,  26)
ACCENT_DIM = (40, 62,  16)
MEM_BG    = (28,  22,  60)
MEM_FG    = (130, 110, 240)
CHECK_BG  = (18,  48,  46)
CHECK_FG  = (100, 200, 188)

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

# ── Create canvas ──────────────────────────────────────────────────────────────
img = Image.new("RGB", (W, H), BG)
draw = ImageDraw.Draw(img)

# Grid dots
for gx in range(0, W + 54, 54):
    for gy in range(0, H + 54, 54):
        draw.ellipse([gx - 1, gy - 1, gx + 1, gy + 1], fill=(20, 20, 22))

# Radial glow (top half)
for r_s in range(600, 0, -5):
    intensity = int(6 * (600 - r_s) / 600)
    c = (BG[0] + intensity, BG[1] + intensity, BG[2] + intensity)
    draw.ellipse([W // 2 - r_s, 250 - r_s, W // 2 + r_s, 250 + r_s], fill=c)

# ── Fonts ─────────────────────────────────────────────────────────────────────
f_logo    = fnt("InstrumentSerif-Italic.ttf", 30)
f_serif_i = fnt("InstrumentSerif-Italic.ttf", 22)
f_mono    = fnt("DMMono-Regular.ttf", 14)
f_mono_sm = fnt("DMMono-Regular.ttf", 12)
f_mono_xs = fnt("DMMono-Regular.ttf", 11)
f_geist_b = fnt("GeistMono-Bold.ttf", 15)
f_verdict = fnt("GeistMono-Bold.ttf", 28)

MARGIN = 72

# ── Helpers ────────────────────────────────────────────────────────────────────
def ctext(draw, text, y, font, color):
    bb = draw.textbbox((0, 0), text, font=font)
    tw = bb[2] - bb[0]
    draw.text(((W - tw) // 2, y), text, font=font, fill=color)

def rr(draw, x, y, w, h, r, fill, outline=None, ow=1):
    draw.rounded_rectangle([x, y, x + w, y + h], radius=r, fill=fill,
                           outline=outline, width=ow)

def node_box(cx, cy, bw, bh):
    """Return top-left (x,y) of a centered box."""
    return (cx - bw // 2, cy - bh // 2)

def draw_node(cx, cy, bw, bh, bg, label, font, tc, outline=None):
    x, y = node_box(cx, cy, bw, bh)
    rr(draw, x, y, bw, bh, 8, bg, outline, 1)
    bb = draw.textbbox((0, 0), label, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    draw.text((cx - tw // 2, cy - th // 2), label, font=font, fill=tc)
    return (x, y, x + bw, y + bh)

def arrow_down(cx, y1, y2, color, w=1):
    draw.line([(cx, y1), (cx, y2)], fill=color, width=w)
    hs = 7
    draw.polygon([(cx, y2), (cx - hs, y2 - hs * 1.6), (cx + hs, y2 - hs * 1.6)],
                 fill=color)

def arrow_left(x1, cy, x2, color, w=1):
    """Arrow pointing left (x1 > x2)."""
    draw.line([(x1, cy), (x2, cy)], fill=color, width=w)
    hs = 7
    draw.polygon([(x2, cy), (x2 + hs * 1.6, cy - hs), (x2 + hs * 1.6, cy + hs)],
                 fill=color)

# ═══════════════════════════════════════════════════════════════════
# HEADER
# ═══════════════════════════════════════════════════════════════════
ctext(draw, "mneme", 54, f_logo, TEXT)
draw.line([(MARGIN, 108), (W - MARGIN, 108)], fill=BORDER2, width=1)
ctext(draw, "the enforcement pipeline", 128, f_serif_i, MUTED)

# Column headers
LX = 270    # left column center
RX = 740    # right column center
DIVIDER_X = 510

hdr_y = 174
# Left: WITHOUT MNEME
lhdr = "WITHOUT MNEME"
lbb = draw.textbbox((0, 0), lhdr, font=f_mono_xs)
draw.text((LX - (lbb[2] - lbb[0]) // 2, hdr_y), lhdr, font=f_mono_xs,
          fill=(170, 70, 60))

# Right: WITH MNEME
rhdr = "WITH MNEME"
rbb = draw.textbbox((0, 0), rhdr, font=f_mono_xs)
draw.text((RX - (rbb[2] - rbb[0]) // 2, hdr_y), rhdr, font=f_mono_xs,
          fill=(120, 185, 60))

# Vertical divider
draw.line([(DIVIDER_X, 168), (DIVIDER_X, 1060)], fill=BORDER2, width=1)

# ═══════════════════════════════════════════════════════════════════
# NODE GEOMETRY
# ═══════════════════════════════════════════════════════════════════
BW = 200   # box width
BH = 48    # box height

# Left column y positions (center of each node)
L_QUERY   = 260
L_LLM     = 410
L_RESP    = 570
L_VERDICT = 710

# Right column y positions
R_QUERY   = 260
R_MEM     = 370   # memory store (side-input to LLM)
R_LLM     = 460
R_CHECK   = 610
R_RESP    = 760
R_VERDICT = 910

MEM_W = 130   # memory store box width
MEM_H = 40
MEM_CX = 940  # memory store center x (to right of RX)

# ═══════════════════════════════════════════════════════════════════
# LEFT COLUMN: WITHOUT MNEME
# ═══════════════════════════════════════════════════════════════════

# QUERY
draw_node(LX, L_QUERY, BW, BH, SURFACE2, "QUERY", f_mono, TEXT, BORDER2)

# Arrow: QUERY → LLM
arrow_down(LX, L_QUERY + BH // 2, L_LLM - BH // 2 - 4, BORDER, 1)

# LLM
draw_node(LX, L_LLM, BW, BH, SURFACE2, "LLM", f_mono, TEXT, BORDER2)

# Arrow: LLM → RESPONSE
arrow_down(LX, L_LLM + BH // 2, L_RESP - BH // 2 - 4, BORDER, 1)

# RESPONSE (danger tinted)
rx1, ry1, rx2, ry2 = draw_node(LX, L_RESP, BW, BH, DANG_DIM, "RESPONSE", f_mono, TEXT, DANGER)

# Violation badges: small dots beside RESPONSE
vbadge_x = rx2 + 10
for vi in range(5):
    vby = ry1 + 8 + vi * 7
    draw.ellipse([vbadge_x, vby, vbadge_x + 5, vby + 5], fill=DANGER)

# Violation count label
draw.text((vbadge_x + 10, ry1 + 12), "x5", font=f_mono_xs, fill=DANGER)

# Arrow: RESPONSE → FAIL
arrow_down(LX, L_RESP + BH // 2, L_VERDICT - 22, DANGER, 1)

# FAIL verdict text
vbb = draw.textbbox((0, 0), "FAIL", font=f_verdict)
vtw = vbb[2] - vbb[0]
vth = vbb[3] - vbb[1]
draw.text((LX - vtw // 2, L_VERDICT - vth // 2), "FAIL", font=f_verdict, fill=DANGER)

# Explanation
exp_y = L_VERDICT + vth // 2 + 16
exp = "violations passed through"
ebb = draw.textbbox((0, 0), exp, font=f_mono_xs)
draw.text((LX - (ebb[2] - ebb[0]) // 2, exp_y), exp, font=f_mono_xs, fill=dim(DANGER, 0.65))

# ═══════════════════════════════════════════════════════════════════
# RIGHT COLUMN: WITH MNEME
# ═══════════════════════════════════════════════════════════════════

# QUERY
draw_node(RX, R_QUERY, BW, BH, SURFACE2, "QUERY", f_mono, TEXT, BORDER2)

# Memory store node (side input at R_MEM level)
draw_node(MEM_CX, R_MEM, MEM_W, MEM_H, MEM_BG, "memory store", f_mono_xs, MEM_FG, MEM_FG)

# Arrow: memory store → LLM (horizontal, pointing left)
# From memory store left edge to LLM right edge
mem_left = MEM_CX - MEM_W // 2
llm_right = RX + BW // 2
# Draw a stepped arrow: down from mem to LLM_Y level, then left into LLM
mid_y = R_LLM  # memory injects at LLM level
draw.line([(MEM_CX, R_MEM + MEM_H // 2), (MEM_CX, mid_y)], fill=MEM_FG, width=1)
arrow_left(MEM_CX, mid_y, llm_right + 4, MEM_FG, 1)

# Label on the memory arrow
mem_lbl = "context packet"
mlbb = draw.textbbox((0, 0), mem_lbl, font=f_mono_xs)
draw.text((RX + BW // 2 + 12, mid_y - 16), mem_lbl, font=f_mono_xs, fill=dim(MEM_FG, 0.65))

# Arrow: QUERY → LLM
arrow_down(RX, R_QUERY + BH // 2, R_LLM - BH // 2 - 4, BORDER, 1)

# LLM (right side, slightly different label)
draw_node(RX, R_LLM, BW, BH, SURFACE2, "LLM", f_mono, TEXT, BORDER2)

# Small "context" annotation on right LLM
ctx_lbl = "+ context"
clbb = draw.textbbox((0, 0), ctx_lbl, font=f_mono_xs)
draw.text((RX + BW // 2 - (clbb[2] - clbb[0]) - 6,
           R_LLM - BH // 2 + 6), ctx_lbl, font=f_mono_xs, fill=MEM_FG)

# Arrow: LLM → check_prompt
arrow_down(RX, R_LLM + BH // 2, R_CHECK - BH // 2 - 4, BORDER, 1)

# check_prompt() node (teal)
draw_node(RX, R_CHECK, BW, BH, CHECK_BG, "check_prompt()", f_mono_sm, CHECK_FG, CHECK_FG)

# Arrow: check_prompt → RESPONSE
arrow_down(RX, R_CHECK + BH // 2, R_RESP - BH // 2 - 4, BORDER, 1)

# RESPONSE (clean, lime tinted)
rr_box = draw_node(RX, R_RESP, BW, BH, ACCENT_DIM, "RESPONSE", f_mono, TEXT, ACCENT)

# Zero violations indicator
zero_lbl = "0 violations"
zlbb = draw.textbbox((0, 0), zero_lbl, font=f_mono_xs)
draw.text((RX + BW // 2 + 8, R_RESP - 8), zero_lbl, font=f_mono_xs, fill=ACCENT)

# Arrow: RESPONSE → PASS
arrow_down(RX, R_RESP + BH // 2, R_VERDICT - 22, ACCENT, 1)

# PASS verdict
pvbb = draw.textbbox((0, 0), "PASS", font=f_verdict)
ptw = pvbb[2] - pvbb[0]
pth = pvbb[3] - pvbb[1]
draw.text((RX - ptw // 2, R_VERDICT - pth // 2), "PASS", font=f_verdict, fill=ACCENT)

# Explanation
pexp = "all decisions enforced"
pebb = draw.textbbox((0, 0), pexp, font=f_mono_xs)
draw.text((RX - (pebb[2] - pebb[0]) // 2, R_VERDICT + pth // 2 + 16),
          pexp, font=f_mono_xs, fill=dim(ACCENT, 0.55))

# ═══════════════════════════════════════════════════════════════════
# BOTTOM CALLOUT
# ═══════════════════════════════════════════════════════════════════
callout_y = R_VERDICT + pth // 2 + 80
draw.line([(MARGIN, callout_y), (W - MARGIN, callout_y)], fill=BORDER2, width=1)

ctext(draw, "5 / 5  benchmark scenarios  ·  100% pass rate",
      callout_y + 22, fnt("GeistMono-Bold.ttf", 16), ACCENT)

quote_y = callout_y + 60
ctext(draw, "mneme enforces what you've decided.",
      quote_y, fnt("InstrumentSerif-Italic.ttf", 22), MUTED)

# ═══════════════════════════════════════════════════════════════════
# FOOTER
# ═══════════════════════════════════════════════════════════════════
footer_y = H - 72
draw.line([(MARGIN, footer_y), (W - MARGIN, footer_y)], fill=BORDER, width=1)
ctext(draw, "mneme  ·  persistent project memory for llm workflows",
      footer_y + 20, fnt("DMMono-Regular.ttf", 11), MUTED)

# ── Save ──────────────────────────────────────────────────────────────────────
out = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "site",
                                    "benchmark-architecture.png"))
img.save(out, "PNG")
print(f"Saved: {out}")
