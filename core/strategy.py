"""
Purchase planning for a Merge Tactics deploy phase.

What actually wins this mode is merging: buying a duplicate of a troop already
deployed merges it into the next star and refunds one elixir, so a duplicate is
almost always the best thing on the shelf. The shop does not reroll on its own;
a purchase replaces that slot with a new card, so the planner keeps buying - the
strongest target troop (see config/target_comp.py) or, if none is offered, the
cheapest card - to cycle the shop and find duplicates faster. When the bench is
full a purchase has no effect, so it sells one reserve unit and carries on.
"""

import logging
import time
from dataclasses import dataclass, field

from config.board_layout import (
    BENCH_CELLS,
    ELIXIR_RECT,
    SELL_BUTTON,
    SELL_THRESHOLD,
)
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

        # 2. Strengthen the target comp if a target troop is on offer.
        targets = [card for card in affordable if card.name in TARGET_COMP]
        if targets:
            targets.sort(key=lambda card: (target_rank(card.name), card.cost))
            return targets[0]

        # 3. Nothing we want on the shelf. Buy the cheapest card anyway: a
        #    purchase replaces that shop slot with a new card, so buying rerolls
        #    the shop and lets a target/duplicate appear instead of stalling
        #    with the same three cards every round.
        return min(affordable, key=lambda card: card.cost)

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
            if dry_run:
                state.buy(choice.name)
                bought.append(choice.name)
                elixir -= choice.cost
                continue

            elixir_before = elixir
            self.adb.tap(*choice.center)
            time.sleep(self.tap_delay)
            screen = self.adb.screenshot()
            read = self._read_elixir(screen)
            # A successful buy spends elixir and takes the card off the shelf, so
            # only treat it as "bench full" when the balance did not drop AND the
            # same card is still on offer.
            if read is not None and read >= elixir_before:
                still_offered = any(
                    c.name == choice.name and c.cost == choice.cost
                    for c in self.reader.shop_cards(screen)
                )
                if still_offered:
                    logger.info("[SHOP] buy had no effect (bench full?), selling a bench unit")
                    if self._sell_one(screen):
                        screen = self.adb.screenshot()
                        reason = "bench full"
                        continue
                    reason = "bench full, could not sell"
                    break

            state.buy(choice.name)
            bought.append(choice.name)
            elixir = read if read is not None else elixir_before - choice.cost

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

    def _sell_one(self, screen):
        """Sell one reserve (bench) unit to free space; True if one was sold.

        Only bench cells are tapped, never the board, so a merged or deployed
        troop is never sold.
        """
        ip = self.reader.image_processor
        for cx, cy in BENCH_CELLS:
            self.adb.tap(cx, cy)
            time.sleep(0.4)
            shot = self.adb.screenshot()
            pos = ip.find_template(shot, SELL_BUTTON, SELL_THRESHOLD)
            if pos:
                logger.info(f"[SELL] selling a bench unit at ({cx}, {cy})")
                self.adb.tap(*pos)
                time.sleep(0.6)
                return True
        return False

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
