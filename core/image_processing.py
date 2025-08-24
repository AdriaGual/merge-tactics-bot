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

class ImageProcessor:
    def __init__(self):
        self.digit_templates = self._load_digit_templates()
        self._elixir_cache = {"value": None, "timestamp": 0}
        self.ELIXIR_CACHE_DURATION = 1.0
        
    def _load_digit_templates(self):
        """Load digit templates for template matching"""
        templates = {}
        templates_dir = "templates/digits"
        
        if not os.path.exists(templates_dir):
            return {}
        
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

    def find_template(self, screen, template_path, threshold=0.8):
        """Find template in screen with given threshold"""
        if not os.path.exists(template_path):
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

        screen_gray = cv2.cvtColor(screen, cv2.COLOR_BGR2GRAY) if screen.ndim == 3 else screen

        for i, template in enumerate(templates):
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

    def read_elixir(self, screen, elixir_rect):
        """Read elixir value from screen using template matching with caching"""
        current_time = time.time()

        # Cache check
        if (self._elixir_cache["value"] is not None and
            current_time - self._elixir_cache["timestamp"] < self.ELIXIR_CACHE_DURATION):
            return self._elixir_cache["value"]

        # Extract ROI and convert to grayscale
        x0, y0, x1, y1 = elixir_rect
        roi = screen[y0:y1, x0:x1]
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

        return self._elixir_cache.get("value", 0)
