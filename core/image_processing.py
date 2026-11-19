"""
Image processing module for the Merge Tactics bot.
Handles template matching, elixir reading, and unit detection.
"""

import cv2
import numpy as np
import os
import time
import logging

logger = logging.getLogger(__name__)

# Elixir counter: elixir drop badge in the bottom right of the deploy screen (900x1600)
ELIXIR_RECT = (660, 1455, 820, 1580)
GLYPH_DIR = "templates/digits_hex"
GLYPH_SIZE = (32, 32)
GLYPH_MIN_SCORE = 0.7


def extract_glyphs(roi):
    """Split the white digits of the elixir badge into glyph masks, left to right"""
    if roi is None or roi.size == 0:
        return []

    hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (0, 0, 185), (180, 95, 255))

    count, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
    boxes = []
    for i in range(1, count):
        x, y, w, h, area = stats[i]
        # The badge digits are ~40px tall at 900x1600, whether the value has one
        # digit (taller glyph) or two. Filter by absolute size instead of by a
        # fraction of the ROI: the ROI also holds the card art and the shop icon.
        if area < 120 or h < 20 or h > 75 or w > 60:
            continue
        boxes.append((x, y, w, h))

    boxes.sort(key=lambda b: b[0])
    return [mask[y:y + h, x:x + w] for x, y, w, h in boxes]


class ImageProcessor:
    def __init__(self):
        self.digit_templates = self._load_digit_templates()
        self.glyph_templates = self._load_glyph_templates()
        self._elixir_cache = {"value": None, "timestamp": 0}
        self.ELIXIR_CACHE_DURATION = 1.0

    def _load_digit_templates(self):
        """Load digit templates for template matching"""
        templates = {}
        templates_dir = "templates/digits"

        if not os.path.exists(templates_dir):
            return templates

        for digit in range(20):
            template_path = os.path.join(templates_dir, f"{digit}.png")
            if os.path.exists(template_path):
                template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
                if template is not None:
                    _, template_thresh = cv2.threshold(template, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                    if np.mean(template_thresh) < 127:
                        template_thresh = cv2.bitwise_not(template_thresh)
                    templates[digit] = template_thresh

        return templates

    def _load_glyph_templates(self):
        """Load single digit glyphs harvested from the current in-game font"""
        templates = {}
        if not os.path.exists(GLYPH_DIR):
            return templates

        for entry in os.listdir(GLYPH_DIR):
            stem, ext = os.path.splitext(entry)
            if ext != ".png" or not stem.isdigit():
                continue
            glyph = cv2.imread(os.path.join(GLYPH_DIR, entry), cv2.IMREAD_GRAYSCALE)
            if glyph is not None:
                templates[int(stem)] = cv2.resize(glyph, GLYPH_SIZE)

        return templates

    def extract_glyphs(self, roi):
        """Digit masks of a badge ROI, left to right"""
        return extract_glyphs(roi)

    def recognise_glyphs(self, glyphs):
        """Turn digit masks into an integer, or None if a digit is unknown"""
        if not self.glyph_templates or not glyphs:
            return None

        digits = []
        for glyph in glyphs:
            glyph = cv2.resize(glyph, GLYPH_SIZE)
            best_digit, best_score = None, -1.0
            for digit, template in self.glyph_templates.items():
                score = cv2.matchTemplate(glyph, template, cv2.TM_CCOEFF_NORMED)
                _, max_val, _, _ = cv2.minMaxLoc(score)
                if max_val > best_score:
                    best_digit, best_score = digit, max_val
            if best_digit is None or best_score < GLYPH_MIN_SCORE:
                return None
            digits.append(str(best_digit))

        return int("".join(digits))

    def _read_glyph_value(self, roi):
        """Read a multi digit elixir value by matching its glyphs"""
        return self.recognise_glyphs(extract_glyphs(roi))

    def find_template(self, screen, template_path, threshold=0.8):
        """Find template in screen with given threshold"""
        if screen is None or not os.path.exists(template_path):
            return None
        template = cv2.imread(template_path, cv2.IMREAD_COLOR)
        res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(res)

        if max_val >= threshold:
            h, w = template.shape[:2]
            return max_loc[0]+w//2, max_loc[1]+h//2
        return None

    def find_units_on_screen(self, screen, templates, threshold=0.75, min_dist=40):
        """Detect units on screen using template matching"""
        detected = []

        if screen is None:
            return detected

        screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY) if screen.ndim == 3 else screen

        for i, template in enumerate(templates):
            if template is None:
                continue
            template_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY) if template.ndim == 3 else template
            res = cv2.matchTemplate(screen_gray, template_gray, cv2.TM_CCOEFF_NORMED)
            loc = np.where(res >= threshold)
            h, w = template_gray.shape[:2]

            centers = [(pt[0]+w//2, pt[1]+h//2) for pt in zip(*loc[::-1])]
            final_centers = []
            for c in centers:
                if all(np.hypot(c[0]-fc[0], c[1]-fc[1]) > min_dist for fc in final_centers):
                    final_centers.append(c)

            detected.extend([(i, c) for c in final_centers])

        return detected

    def read_elixir(self, screen, elixir_rect=None, force=False):
        """Read elixir value from screen using template matching with caching"""
        current_time = time.time()
        elixir_rect = elixir_rect or ELIXIR_RECT

        # Cache check
        if (not force and self._elixir_cache["value"] is not None and
            current_time - self._elixir_cache["timestamp"] < self.ELIXIR_CACHE_DURATION):
            return self._elixir_cache["value"]

        if screen is None:
            return None

        # Extract ROI and convert to grayscale
        x0, y0, x1, y1 = elixir_rect
        roi = screen[y0:y1, x0:x1]
        if roi.size == 0:
            return None

        # Current in-game counter: digits on the hexagon badge
        value = self._read_glyph_value(roi)
        if value is not None:
            self._elixir_cache["value"] = value
            self._elixir_cache["timestamp"] = current_time
            return value

        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if roi.ndim == 3 else roi

        best_match, best_val = None, 1

        for value, template in self.digit_templates.items():
            # Ensure template is grayscale
            tpl_gray = cv2.cvtColor(template, cv2.COLOR_BGR2GRAY) if template.ndim == 3 else template

            # Resize if necessary
            if roi_gray.shape != tpl_gray.shape:
                tpl_gray = cv2.resize(tpl_gray, (roi_gray.shape[1], roi_gray.shape[0]))

            res = cv2.matchTemplate(roi_gray, tpl_gray, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(res)
            if max_val < best_val:
                best_val = max_val
                best_match = value

        if best_match is not None and best_val <= -0.7:
            self._elixir_cache["value"] = best_match
            self._elixir_cache["timestamp"] = current_time
            return best_match

        # No confident read: report nothing instead of a wrong value.
        return None
