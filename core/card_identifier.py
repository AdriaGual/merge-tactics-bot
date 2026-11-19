"""
Identify Merge Tactics shop cards with SIFT against a downloaded art library.

The card art downloaded from the stats site is used only as a reference: a shop
tile carries a colour grade and a crop, so plain template matching fails, while
SIFT keypoints survive both. Each card of the current season maps to one art
file, which is cached in debug_images/cards/raw/.
"""

import os
import subprocess
import urllib.parse

import cv2
import numpy as np

ART_HOST = "https://crownstats.com"
ART_SUBDIR = "/icons/merge/cards/"
ART_CACHE_DIR = os.path.join("debug_images", "cards", "raw")

# card template name -> file served by the art library (roster of the season)
ART_MAP = {
    "archer": "Archer_card.png",
    "archer_queen": "Archer_Queen_card.png",
    "baby_dragon": "BabyDragon_AC_card (1).png",
    "bandit": "Bandit_card.png",
    "barbarian": "Barbarian_AC_card.png",
    "bomber": "Bomber_card.png",
    "boss_bandit": "BOSSBANDIT_AC_CARD.png",
    "dark_prince": "darkprince.png",
    "dart_goblin": "Goblin_Dart_card.png",
    "electro_giant": "EGiant_card.png",
    "electro_wizard": "EWizard_card.png",
    "executioner": "Executioner_card.png",
    "firecracker": "FIRECRACKER_AC_CARD.png",
    "giant": "Giant_AC_card.png",
    "giant_skeleton": "Giant_Skeleton_AC_card.png",
    "goblin": "Goblin_card.png",
    "goblin_cage": "Goblin_cage_card.png",
    "goblin_demolisher": "Goblin_Demolisher_AC_card.png",
    "goblin_machine": "Goblin_machine_card.png",
    "golden_knight": "Golden_Knight_card.png",
    "hog_rider": "hogrider.png",
    "knight": "Knight_card.png",
    "magic_archer": "MAGICARCHER_AC_CARD.png",
    "mega_knight": "MegaKnight_card.png",
    "mini_pekka": "MiniPekka_AC_card.png",
    "monk": "the_monk_AC_card.png",
    "musketeer": "Musketeer_card.png",
    "pekka": "Pekka_card.png",
    "prince": "Prince_card.png",
    "princess": "Princess_card.png",
    "ram_rider": "ramrider.png",
    "royal_ghost": "RoyalGhost_card.png",
    "royal_giant": "Royal_Giant_AC_card.png",
    "skeleton_dragons": "SkeletonDragon_AC_card.png",
    "skeleton_king": "Skeleton_King_card.png",
    "spear_goblin": "Spear_Goblin_card.png",
    "valkyrie": "Valkyrie_AC_card.png",
    "witch": "Witch_card.png",
    "wizard": "Wizard_card.png",
}


def ensure_art_library():
    """Download any missing art file into the debug cache and return the usable map"""
    os.makedirs(ART_CACHE_DIR, exist_ok=True)
    usable = {}
    for name, filename in ART_MAP.items():
        path = os.path.join(ART_CACHE_DIR, filename)
        if not (os.path.exists(path) and os.path.getsize(path) > 0):
            url = ART_HOST + ART_SUBDIR + urllib.parse.quote(filename)
            result = subprocess.run(
                ["curl", "-fsSL", "-A", "Mozilla/5.0", "-o", path, url],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if result.returncode != 0 or not os.path.exists(path):
                print(f"[warn] art not available for {name} ({filename})")
                continue
        usable[name] = filename
    return usable


def load_art_library(art_files=None):
    """Load the art images referenced by the map (downloading what is missing)"""
    art_files = art_files if art_files is not None else ensure_art_library()
    library = {}
    for name, filename in art_files.items():
        img = cv2.imread(os.path.join(ART_CACHE_DIR, filename))
        if img is not None:
            library[name] = img
    return library


class CardIdentifier:
    """Match a cropped card tile to a card name using SIFT + RANSAC inliers"""

    def __init__(self, library):
        self.library = library
        self.sift = cv2.SIFT_create()
        self.descriptors = {}
        self.art_gray = {}
        for name, img in library.items():
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            keypoints, desc = self.sift.detectAndCompute(gray, None)
            if desc is not None and len(keypoints) > 0:
                self.descriptors[name] = (keypoints, desc)
                self.art_gray[name] = gray
        self.matcher = cv2.BFMatcher()

    @staticmethod
    def _warp_correlation(art_gray, homography, tile_gray):
        """Correlate the art warped through the homography with the tile.

        Raw RANSAC inlier counts can favour the wrong card when two arts share
        repetitive textures, so the geometry is only trusted once the warped
        art actually looks like the tile. Returns None when there is too little
        overlap to judge.
        """
        h, w = tile_gray.shape[:2]
        warped = cv2.warpPerspective(art_gray, homography, (w, h))
        valid = cv2.warpPerspective(
            np.full(art_gray.shape, 255, np.uint8), homography, (w, h)
        ) > 0
        if valid.sum() < 0.15 * h * w:
            return None
        a = warped[valid].astype(np.float32)
        b = tile_gray[valid].astype(np.float32)
        if a.std() < 1e-3 or b.std() < 1e-3:
            return None
        return float(np.corrcoef(a, b)[0, 1])

    def identify(self, tile, min_inliers=12, min_corr=0.45):
        """Return (card name, inliers) for a shop tile, or (None, inliers)"""
        if tile is None or tile.size == 0:
            return None, 0
        gray = cv2.cvtColor(tile, cv2.COLOR_BGR2GRAY)
        keypoints, desc = self.sift.detectAndCompute(gray, None)
        if desc is None or len(keypoints) < 8:
            return None, 0

        best = None  # (correlation, inliers, name)
        for name, (art_kp, art_desc) in self.descriptors.items():
            matches = self.matcher.knnMatch(art_desc, desc, k=2)
            good = [m for pair in matches if len(pair) == 2 for m, n in [pair] if m.distance < 0.75 * n.distance]
            if len(good) < 8:
                continue
            src = np.float32([art_kp[m.queryIdx].pt for m in good]).reshape(-1, 1, 2)
            dst = np.float32([keypoints[m.trainIdx].pt for m in good]).reshape(-1, 1, 2)
            homography, mask = cv2.findHomography(src, dst, cv2.RANSAC, 5.0)
            if homography is None or mask is None:
                continue
            inliers = int(mask.sum())
            if inliers < min_inliers:
                continue
            corr = self._warp_correlation(self.art_gray[name], homography, gray)
            if corr is None:
                continue
            if best is None or (corr, inliers) > (best[0], best[1]):
                best = (corr, inliers, name)

        if best is None or best[0] < min_corr:
            return None, best[1] if best else 0
        return best[2], best[1]
