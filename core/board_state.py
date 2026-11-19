"""
Read the live Merge Tactics board from a screenshot.

The deploy phase is the only moment where decisions matter: it shows the three
shop cards, the elixir balance and any quest orb waiting on the arena. This
module turns a screenshot into that state so the strategy can decide, and keeps
the vision details (SIFT card recognition, colour masks) in one place.
"""

import logging
import os
from dataclasses import dataclass, field

import cv2
import numpy as np

from config.board_layout import (
    ARENA_RECT,
    COST_BADGES,
    ELIXIR_RECT,
    ORB_HSV_HIGH,
    ORB_HSV_LOW,
    ORB_MAX_DIAMETER,
    ORB_MIN_DIAMETER,
    ORB_MIN_FILL,
    PHASE_LABELS,
    PHASE_LABEL_RECT,
    PHASE_THRESHOLD,
    SHOP_CENTERS,
    SHOP_TILES,
)
from config.unit_costs import unit_costs
from core.card_identifier import CardIdentifier, load_art_library

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ShopCard:
    name: str
    cost: int
    center: tuple


@dataclass
class BoardState:
    phase: str = None
    elixir: int = None
    cards: list = field(default_factory=list)
    orbs: list = field(default_factory=list)
    own_units: int = 0


class BoardReader:
    def __init__(self, image_processor, identifier=None):
        self.image_processor = image_processor
        self.identifier = identifier or CardIdentifier(load_art_library())
        self._label_templates = {}
        for phase, path in PHASE_LABELS.items():
            template = cv2.imread(path)
            if template is not None:
                self._label_templates[phase] = template
            else:
                logger.warning(f"[BOARD] phase label missing: {path}")

    def phase(self, screen):
        """Return 'deploy', 'battle' or None"""
        if screen is None:
            return None
        x0, y0, x1, y1 = PHASE_LABEL_RECT
        roi = screen[y0:y1, x0:x1]
        best_phase, best_score = None, 0.0
        for phase, template in self._label_templates.items():
            if roi.shape[0] < template.shape[0] or roi.shape[1] < template.shape[1]:
                continue
            res = cv2.matchTemplate(roi, template, cv2.TM_CCOEFF_NORMED)
            _, score, _, _ = cv2.minMaxLoc(res)
            if score > best_score:
                best_phase, best_score = phase, score
        return best_phase if best_score >= PHASE_THRESHOLD else None

    def shop_cards(self, screen):
        """Identify the three shop cards and pair them with their elixir cost"""
        cards = []
        if screen is None:
            return cards
        for index, (y0, y1, x0, x1) in enumerate(SHOP_TILES):
            name, inliers = self.identifier.identify(screen[y0:y1, x0:x1])
            if name is None:
                continue
            cost = self._read_cost(screen, index) or unit_costs.get(name)
            if cost is None:
                continue
            cards.append(ShopCard(name=name, cost=cost, center=SHOP_CENTERS[index]))
        return cards

    def _read_cost(self, screen, index):
        """Read the elixir cost badge of a shop card (digits are 1-5, so one glyph)"""
        y0, y1, x0, x1 = COST_BADGES[index]
        badge = screen[y0:y1, x0:x1]
        if badge.size == 0:
            return None
        # Cost digits are ~21px tall, much smaller than the elixir ones (~40px);
        # the badge corner also overlaps card art, so keep the digit-sized masks.
        glyphs = [
            glyph
            for glyph in self.image_processor.extract_glyphs(badge)
            if 15 <= glyph.shape[0] <= 28 and glyph.shape[1] <= 22
        ]
        if not glyphs:
            return None
        # The badge crop can still catch a sliver of bright card art; the digit
        # is the largest remaining blob, so it wins the tie.
        glyph = max(glyphs, key=lambda g: g.shape[0] * g.shape[1])
        value = self.image_processor.recognise_glyphs([glyph])
        return value if value in (1, 2, 3, 4, 5) else None

    def orbs(self, screen):
        """Centres of the quest orbs on the arena (any colour)"""
        if screen is None:
            return []
        x0, y0, x1, y1 = ARENA_RECT
        hsv = cv2.cvtColor(screen[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, ORB_HSV_LOW, ORB_HSV_HIGH)
        count, _, stats, centroids = cv2.connectedComponentsWithStats(mask, 8)
        found = []
        for i in range(1, count):
            x, y, w, h, area = stats[i]
            if not (ORB_MIN_DIAMETER <= w <= ORB_MAX_DIAMETER
                    and ORB_MIN_DIAMETER <= h <= ORB_MAX_DIAMETER):
                continue
            if area < ORB_MIN_FILL * w * h:
                continue
            found.append((int(centroids[i][0]) + x0, int(centroids[i][1]) + y0))
        return found

    def own_units(self, screen):
        """Count the troops standing on our half of the arena via their health bars"""
        if screen is None:
            return 0
        x0, y0, x1, y1 = ARENA_RECT
        hsv = cv2.cvtColor(screen[y0:y1, x0:x1], cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, (95, 140, 160), (110, 255, 255))
        count, _, stats, _ = cv2.connectedComponentsWithStats(mask, 8)
        units = 0
        for i in range(1, count):
            _, _, w, h, area = stats[i]
            # The bar is ~66x17 including the star badge and the level box.
            if 30 <= w <= 90 and 8 <= h <= 22 and area >= 200:
                units += 1
        return units

    def read(self, screen):
        """Full board state of the current screenshot"""
        return BoardState(
            phase=self.phase(screen),
            elixir=self.image_processor.read_elixir(screen, list(ELIXIR_RECT), force=True),
            cards=self.shop_cards(screen),
            orbs=self.orbs(screen),
            own_units=self.own_units(screen),
        )
