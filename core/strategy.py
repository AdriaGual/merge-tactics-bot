"""
Purchase planning for a Merge Tactics deploy phase.

What actually wins this mode is merging: buying a duplicate of a troop already
deployed merges it into the next star and refunds one elixir, so a duplicate is
almost always the best thing on the shelf. When no duplicate is on offer the
planner buys a new troop while the roster is small (composition first, then the
strongest card it can afford) and otherwise keeps the elixir for the next shop.
"""

import logging
import time
from dataclasses import dataclass, field

from config.board_layout import ELIXIR_RECT

logger = logging.getLogger(__name__)

# Keeping the roster narrow is what makes merges reachable: every extra kind of
# troop spreads the same elixir over more copies.
MAX_DISTINCT_TROOPS = 6
# Star level thresholds: copies needed for 2, 3 and 4 stars
STAR_STEPS = (2, 4, 8)


@dataclass
class RunState:
    """Troops bought during the current match, and therefore their star level"""

    copies: dict = field(default_factory=dict)
    purchases: list = field(default_factory=list)

    def buy(self, name):
        self.copies[name] = self.copies.get(name, 0) + 1
        self.purchases.append(name)
        return self.copies[name]

    def star(self, name):
        copies = self.copies.get(name, 0)
        star = 1
        for step in STAR_STEPS:
            if copies >= step:
                star += 1
        return star

    def copies_to_next_star(self, name):
        copies = self.copies.get(name, 0)
        for step in STAR_STEPS:
            if copies < step:
                return step - copies
        return 0

    def report(self):
        if not self.copies:
            return "nothing bought yet"
        return ", ".join(
            f"{name} x{copies} ({self.star(name)}*)" for name, copies in sorted(self.copies.items())
        )


class DeployPlanner:
    def __init__(self, reader, adb, tap_delay=0.6):
        self.reader = reader
        self.adb = adb
        self.tap_delay = tap_delay

    def choose(self, cards, elixir, state, composition=()):
        """Pick the card to buy, or None to save the elixir"""
        affordable = [card for card in cards if card.cost <= elixir]
        if not affordable:
            return None

        # 1. A duplicate merges a deployed troop and hands one elixir back.
        duplicates = [card for card in affordable if card.name in state.copies]
        if duplicates:
            duplicates.sort(key=lambda card: (state.copies_to_next_star(card.name), card.cost))
            return duplicates[0]

        # 2. A new troop only while the roster still has room to merge later.
        if len(state.copies) >= MAX_DISTINCT_TROOPS:
            return None

        preferred = [card for card in affordable if card.name in composition]
        pool = preferred or affordable
        # Stronger troops cost more elixir; among equal costs the composition wins.
        pool.sort(key=lambda card: (card.cost, card.name in composition), reverse=True)
        return pool[0]

    def play(self, screen, state, composition=(), max_buys=6, dry_run=False):
        """Play one deploy phase: pop the orbs, then spend the elixir"""
        orbs = self.reader.orbs(screen)
        for x, y in orbs:
            logger.info(f"[ORB] popping quest orb at ({x}, {y})")
            if not dry_run:
                self.adb.tap(x, y)
                time.sleep(self.tap_delay)
        if orbs and not dry_run:
            screen = self.adb.screenshot()

        elixir = self._read_elixir(screen)
        units_before = self.reader.own_units(screen)

        bought = []
        for _ in range(max_buys):
            if screen is None or elixir is None:
                break
            cards = self.reader.shop_cards(screen)
            if not cards:
                logger.info("[SHOP] no shop cards recognised, stopping")
                break
            choice = self.choose(cards, elixir, state, composition)
            if choice is None:
                logger.info(
                    f"[SHOP] saving {elixir} elixir | shop {[(c.name, c.cost) for c in cards]}"
                )
                break

            logger.info(f"[BUY] {choice.name} ({choice.cost}) -> {state.star(choice.name)}*")
            if not dry_run:
                self.adb.tap(*choice.center)
                time.sleep(self.tap_delay)
                screen = self.adb.screenshot()
            state.buy(choice.name)
            bought.append(choice.name)
            elixir -= choice.cost
            if not dry_run:
                read = self._read_elixir(screen)
                if read is not None:
                    elixir = read

        units_after = self.reader.own_units(screen) if screen is not None else 0
        summary = {
            "elixir": elixir,
            "bought": bought,
            "orbs": len(orbs),
            "units": units_after,
            "units_before": units_before,
            "roster": state.report(),
        }
        logger.info(
            f"[DEPLOY] bought {bought or 'nothing'} | elixir left {elixir} | "
            f"units {units_before}->{units_after} | roster: {state.report()}"
        )
        return summary

    def _read_elixir(self, screen):
        if screen is None:
            return None
        return self.reader.image_processor.read_elixir(screen, list(ELIXIR_RECT), force=True)
