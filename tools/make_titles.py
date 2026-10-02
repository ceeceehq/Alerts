#!/usr/bin/env python3
"""Render the email titles ("In season" / "Early October") as images.

Gmail ignores web fonts, so the decorative Fraunces title is drawn into a
transparent PNG per region and half-month: img/titles/<region>-<half-month>.png.
Rerun after adding a region or changing the wording. Needs Pillow.
"""
import sys
from datetime import date
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from produce_alert import REGIONS, period_name  # noqa: E402

FONT = Path(__file__).with_name("fonts") / "Fraunces-Italic.ttf"
OUT = ROOT / "img" / "titles"
WIDTH = 1120  # 2x the 560px email column, for sharp text on retina screens
GREEN, INK = (110, 128, 84), (38, 36, 31)


def fraunces(size, weight, opsz):
    font = ImageFont.truetype(str(FONT), size)
    axes = {"Optical Size": opsz, "Weight": weight, "Softness": 100, "Wonky": 1}
    font.set_variation_by_axes([axes[a["name"].decode()] for a in font.get_variation_axes()])
    return font


def render(kicker, period):
    small, big = fraunces(44, 400, 72), fraunces(96, 500, 144)
    img = Image.new("RGBA", (WIDTH, 220), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.text((8, 0), kicker, font=small, fill=GREEN)
    d.text((4, 58), period, font=big, fill=INK)
    return img.crop((0, 0, WIDTH, img.getbbox()[3] + 12))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for region, r in REGIONS.items():
        for month in range(1, 13):
            for half, day in (("a", 1), ("b", 15)):
                render(r["subject"], period_name(date(2027, month, day))).save(
                    OUT / f"{region}-{month}{half}.png", optimize=True)
    print(f"wrote {len(list(OUT.glob('*.png')))} titles to {OUT}")


if __name__ == "__main__":
    main()
