"""
Purchase planning for a Merge Tactics deploy phase.

What actually wins this mode is merging: buying a duplicate of a troop already
deployed merges it into the next star and refunds one elixir, so a duplicate is
almost always the best thing on the shelf. When no duplicate is on offer the
planner buys the strongest troop of the target composition it can afford (see
config/target_comp.py) and otherwise keeps the elixir for the next shop.
"""

import logging
import time
from dataclasses import dataclass, field

from config.board_layout import ELIXIR_RECT
from config.target_comp import TARGET_COMP, target_rank

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

    def choose(self, cards, elixir, state):
        """Pick the card to buy, or None to save the elixir"""
        affordable = [card for card in cards if card.cost <= elixir]
        if not affordable:
            return None

        # 1. A duplicate merges a deployed troop and hands one elixir back.
        duplicates = [card for card in affordable if card.name in state.copies]
        if duplicates:
            duplicates.sort(key=lambda card: (state.copies_to_next_star(card.name), card.cost))
            return duplicates[0]

        # 2. Otherwise strengthen the target comp. The roster is kept narrow so
        #    merges stay reachable, and weak troops outside the target list are
        #    never bought: elixir is saved until a target troop shows up.
        if len(state.copies) >= MAX_DISTINCT_TROOPS:
            return None

        targets = [card for card in affordable if card.name in TARGET_COMP]
        if not targets:
            return None
        targets.sort(key=lambda card: (target_rank(card.name), card.cost))
        return targets[0]

    def play(self, screen, state, max_buys=6, dry_run=False):
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
        if elixir is None and not dry_run:
            # A round opens with a modal notification that covers the elixir
            # badge and the shop for a few seconds, so poll until it clears.
            for _ in range(10):
                time.sleep(0.7)
                fresh = self.adb.screenshot()
                if fresh is not None:
                    screen = fresh
                    elixir = self._read_elixir(screen)
                if elixir is not None:
                    break
        units_before = self.reader.own_units(screen)

        bought = []
        reason = "done"
        for _ in range(max_buys):
            if screen is None or elixir is None:
                reason = "no_elixir"
                break
            cards = self.reader.shop_cards(screen)
            if not cards and not dry_run:
                # The purchase animation briefly hides the shop; retry before
                # giving up so leftover elixir is not wasted.
                for _ in range(5):
                    time.sleep(0.6)
                    screen = self.adb.screenshot()
                    cards = self.reader.shop_cards(screen)
                    if cards:
                        break
            if not cards:
                # Could not see the shop at all. Do not treat this as a decision:
                # the caller retries on a later frame of the same deploy phase.
                reason = "no_cards"
                logger.info("[SHOP] no shop cards recognised, will retry")
                break
            choice = self.choose(cards, elixir, state)
            if choice is None:
                reason = self._save_reason(cards, elixir, state)
                logger.info(
                    f"[SHOP] saving {elixir} elixir ({reason}) | "
                    f"shop {[(c.name, c.cost) for c in cards]}"
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
            "reason": reason,
        }
        logger.info(
            f"[DEPLOY] bought {bought or 'nothing'} | elixir left {elixir} ({reason}) | "
            f"units {units_before}->{units_after} | roster: {state.report()}"
        )
        return summary

    def _save_reason(self, cards, elixir, state):
        """Human-readable reason the planner chose to save elixir"""
        affordable = [card for card in cards if card.cost <= elixir]
        if not affordable:
            return "nothing affordable"
        if len(state.copies) >= MAX_DISTINCT_TROOPS and all(
            card.name not in state.copies for card in affordable
        ):
            return f"roster full ({MAX_DISTINCT_TROOPS} kinds), waiting for duplicates"
        return "no target troop on offer"

    def _read_elixir(self, screen):
        if screen is None:
            return None
        return self.reader.image_processor.read_elixir(screen, list(ELIXIR_RECT), force=True)
