#!/usr/bin/env python3
"""Generate the static Open Graph image (1200x630) for link previews.

Deliberately shows no live score so the image never goes stale.
Brand: dark blue-tinted neutrals, Instrument Serif italic display,
JetBrains Mono labels, and the four-tier semantic spectrum.

Usage: python3 scripts/generate_og_image.py
Fonts are fetched from the Google Fonts repo into /tmp if not present.
Requires: Pillow
"""
import os
import urllib.request

from PIL import Image, ImageDraw, ImageFont

FONT_DIR = "/tmp/fonts"
FONTS = {
    "InstrumentSerif-Italic.ttf": "https://github.com/google/fonts/raw/main/ofl/instrumentserif/InstrumentSerif-Italic.ttf",
    "JetBrainsMono.ttf": "https://github.com/google/fonts/raw/main/ofl/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf",
}

W, H = 1200, 630
BG = (10, 10, 15)            # --bg-primary
TEXT_PRIMARY = (232, 232, 237)
TEXT_SECONDARY = (152, 152, 168)
TEXT_MUTED = (130, 130, 154)
GREEN = (0, 217, 160)
YELLOW = (255, 201, 64)
ORANGE = (255, 140, 64)
RED = (255, 77, 106)
BORDER = (40, 40, 58)


def ensure_fonts():
    os.makedirs(FONT_DIR, exist_ok=True)
    for name, url in FONTS.items():
        path = os.path.join(FONT_DIR, name)
        if not os.path.exists(path):
            urllib.request.urlretrieve(url, path)


def mono(size, weight=400):
    f = ImageFont.truetype(os.path.join(FONT_DIR, "JetBrainsMono.ttf"), size)
    try:
        f.set_variation_by_axes([weight])
    except Exception:
        pass
    return f


def serif_italic(size):
    return ImageFont.truetype(os.path.join(FONT_DIR, "InstrumentSerif-Italic.ttf"), size)


def tracked_text(draw, pos, text, font, fill, tracking=0):
    """Draw text with simple letter-spacing (tracking in px)."""
    x, y = pos
    for ch in text:
        draw.text((x, y), ch, font=font, fill=fill)
        x += draw.textlength(ch, font=font) + tracking
    return x


def main():
    ensure_fonts()
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img)

    margin = 90

    # Kicker
    kicker = "THE US LABOR MARKET, SCORED MONTHLY"
    tracked_text(d, (margin, 118), kicker, mono(20, 500), TEXT_MUTED, tracking=4)

    # Title — the question, in the editorial serif
    d.text((margin - 6, 168), "Is now a good time?", font=serif_italic(108), fill=TEXT_PRIMARY)

    # Standfirst
    sub1 = "One 0–100 score for whether the job market favors"
    sub2 = "you or employers — from official BLS & Fed data."
    d.text((margin, 330), sub1, font=mono(28), fill=TEXT_SECONDARY)
    d.text((margin, 372), sub2, font=mono(28), fill=TEXT_SECONDARY)

    # Spectrum scale — the four semantic tiers at their true thresholds
    bar_y, bar_h = 478, 12
    bar_x0, bar_x1 = margin, W - margin
    bar_w = bar_x1 - bar_x0
    stops = [(0.00, 0.40, RED), (0.40, 0.55, ORANGE), (0.55, 0.70, YELLOW), (0.70, 1.00, GREEN)]
    bar = Image.new("RGB", (int(bar_w), bar_h), BG)
    bd = ImageDraw.Draw(bar)
    for a, b, color in stops:
        bd.rectangle([a * bar_w, 0, b * bar_w, bar_h], fill=color)
    mask = Image.new("L", bar.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, bar.width - 1, bar.height - 1], radius=6, fill=255)
    img.paste(bar, (bar_x0, bar_y), mask)

    # Threshold ticks and tier labels
    tick_font = mono(19, 500)
    label_font = mono(19, 500)
    for frac, val in [(0.0, "0"), (0.40, "40"), (0.55, "55"), (0.70, "70"), (1.0, "100")]:
        x = bar_x0 + frac * bar_w
        tw = d.textlength(val, font=tick_font)
        tx = min(max(x - tw / 2, bar_x0), bar_x1 - tw)
        d.text((tx, bar_y + 26), val, font=tick_font, fill=TEXT_MUTED)

    labels = [(0.20, "TOUGH MARKET", RED), (0.475, "BUILD", ORANGE),
              (0.625, "EXPLORE", YELLOW), (0.85, "GOOD TIME", GREEN)]
    for frac, text, color in labels:
        x = bar_x0 + frac * bar_w
        tw = d.textlength(text, font=label_font)
        d.text((x - tw / 2, bar_y - 38), text, font=label_font, fill=color)

    # Footer rule + source line
    d.line([(margin, 566), (W - margin, 566)], fill=BORDER, width=2)
    d.text((margin, 580), "Updated monthly · BLS JOLTS · FRED · Federal Reserve",
           font=mono(19), fill=TEXT_MUTED)

    out = os.path.join(os.path.dirname(__file__), "..", "assets", "og-image.png")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    img.save(out, optimize=True)
    print("wrote", os.path.normpath(out), img.size)


if __name__ == "__main__":
    main()
