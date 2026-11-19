"""
Harvest elixir digit glyphs from a Merge Tactics screenshot.

The elixir counter shows a number on a hexagon badge. Telling 8 from 19 needs the
digit glyphs, and they can only be taken from the game itself. Point this at a
screenshot where you can read the value by eye:

    python utils/elixir_glyphs.py debug_images/mt_5.png 19

Each glyph is stored as a 32x32 mask in templates/digits_hex/<digit>.png, so the
reader works for any value built from digits already harvested.
"""

import argparse
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.image_processing import (  # noqa: E402
    ELIXIR_RECT,
    GLYPH_DIR,
    GLYPH_SIZE,
    extract_glyphs,
)

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("screenshot", help="screenshot of a deploy phase")
    parser.add_argument("value", type=int, help="elixir value shown in the screenshot")
    parser.add_argument("--rect", nargs=4, type=int, default=list(ELIXIR_RECT),
                        help="elixir badge rectangle x0 y0 x1 y1")
    args = parser.parse_args()

    screen = cv2.imread(args.screenshot)
    if screen is None:
        sys.exit(f"cannot read {args.screenshot}")

    x0, y0, x1, y1 = args.rect
    roi = screen[y0:y1, x0:x1]
    glyphs = extract_glyphs(roi)
    digits = str(args.value)

    if len(glyphs) != len(digits):
        sys.exit(f"found {len(glyphs)} glyphs but the value has {len(digits)} digits")

    os.makedirs(GLYPH_DIR, exist_ok=True)
    for digit, glyph in zip(digits, glyphs):
        resized = cv2.resize(glyph, GLYPH_SIZE)
        path = os.path.join(GLYPH_DIR, f"{digit}.png")
        cv2.imwrite(path, resized)
        print(f"saved glyph {digit} -> {path}")

    have = sorted(os.path.splitext(f)[0] for f in os.listdir(GLYPH_DIR) if f.endswith(".png"))
    print("glyphs available:", ", ".join(have))


if __name__ == "__main__":
    main()
