"""
Capture Merge Tactics shop cards from the running game and save them as templates.

The bot recognises shop cards with SIFT against the card art, but the shop tiles
also carry a colour grade that changes with the season, so keeping a crop of the
current tiles is useful for debugging. This script:

  1. grabs screenshots from the connected device (or reads saved ones),
  2. crops the three shop tiles of a deploy phase,
  3. identifies each tile against the art library (scale/pan invariant, SIFT),
  4. stores it as templates/units/<card>.png and reports roster coverage.

Usage:
    python utils/card_sync.py --live 10          # capture while a deploy phase is open
    python utils/card_sync.py --screenshots debug_images/mt_5.png

Tiles already present in templates/units are skipped, so it is safe to run it
repeatedly and let the library grow over several matches.
"""

import argparse
import os
import sys

import cv2

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.board_layout import SHOP_TILES  # noqa: E402
from config.paths import UNITS_DIR, ADB_PATH  # noqa: E402
from core.adb_controller import ADBController  # noqa: E402
from core.card_identifier import (  # noqa: E402
    ART_MAP,
    CardIdentifier as TileIdentifier,
    ensure_art_library,
    load_art_library,
)

CAPTURE_WIDTH = 900


def crop_shop_tiles(screen):
    """Crop the three shop tiles of a deploy phase"""
    if screen is None:
        return []
    scale = screen.shape[1] / CAPTURE_WIDTH
    tiles = []
    for y0, y1, x0, x1 in SHOP_TILES:
        rect = (int(y0 * scale), int(y1 * scale), int(x0 * scale), int(x1 * scale))
        tiles.append(screen[rect[0]:rect[1], rect[2]:rect[3]])
    return [t for t in tiles if t.size > 0]


def capture_live(count, delay):
    import time

    adb = ADBController(ADB_PATH)
    screens = []
    for i in range(count):
        try:
            screens.append(adb.screenshot())
            print(f"[capture] {i + 1}/{count}")
        except Exception as e:
            print(f"[capture] failed: {e}")
        if i + 1 < count:
            time.sleep(delay)
    return screens


def process_screens(screens, identifier, overwrite=False):
    saved, unknown = [], 0
    for screen in screens:
        for tile in crop_shop_tiles(screen):
            name, inliers = identifier.identify(tile)
            if name is None:
                unknown += 1
                continue
            path = os.path.join(UNITS_DIR, f"{name}.png")
            if os.path.exists(path) and not overwrite:
                print(f"[skip] {name} already has a template")
                continue
            cv2.imwrite(path, tile)
            saved.append(name)
            print(f"[save] {name} (inliers={inliers}) -> {path}")
    return saved, unknown


def report_coverage():
    present = {os.path.splitext(f)[0] for f in os.listdir(UNITS_DIR) if f.endswith(".png")}
    have = sorted(present & set(ART_MAP))
    missing = sorted(set(ART_MAP) - present)
    print(f"\n[roster] {len(have)}/{len(ART_MAP)} cards have a shop template")
    if missing:
        print("[roster] missing:", ", ".join(missing))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", type=int, default=0, help="number of live screenshots to take")
    parser.add_argument("--delay", type=float, default=3.0, help="seconds between live captures")
    parser.add_argument("--screenshots", nargs="*", default=[], help="existing screenshots to process")
    parser.add_argument("--overwrite", action="store_true", help="replace existing templates")
    args = parser.parse_args()

    art_files = ensure_art_library()
    identifier = TileIdentifier(load_art_library(art_files))

    screens = [cv2.imread(p) for p in args.screenshots]
    screens = [s for s in screens if s is not None]
    if args.live:
        screens += capture_live(args.live, args.delay)

    if not screens:
        parser.error("nothing to process: pass --live N or --screenshots ...")

    saved, unknown = process_screens(screens, identifier, overwrite=args.overwrite)
    print(f"\n[done] saved {len(saved)} new templates, {unknown} unrecognised tiles")
    report_coverage()


if __name__ == "__main__":
    main()
