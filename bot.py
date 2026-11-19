"""
Headless Merge Tactics bot.

Run it on the game lobby: it presses "Batalla" to search for a match, plays every
round (pops orbs, buys/merges toward the season target comp) and rematches on the
results screen, forever. No GUI.

    python bot.py                 # search for a match and play non-stop
    python bot.py --no-search     # already in a match: just play it
    python bot.py --duration 1800 # stop after 30 minutes
"""

import argparse
import time

from core.adb_controller import ADBController
from core.image_processing import ImageProcessor
from core.game_logic import GameLogic
from config.paths import ADB_PATH
from config.board_layout import (
    END_BUTTONS,
    END_BUTTON_THRESHOLD,
    SEARCH_BUTTON,
    SEARCH_THRESHOLD,
)
from config.constants import ERROR_DELAY, BATTLE_WAIT
from config.target_comp import TARGET_COMP, SEASON
from config.logging_config import setup_logging

logger = setup_logging()

# Re-press "Batalla" at most this often while no match is running
SEARCH_RETRY_SECONDS = 8.0


class MergeTacticsBot:
    def __init__(self):
        self.adb = ADBController(ADB_PATH)
        self.image_processor = ImageProcessor()
        self.game_logic = GameLogic(self.adb, self.image_processor)
        self.last_elixir_value = 0
        self._deploy_played = False
        self._last_deploy_ts = 0.0
        logger.info(f"[BOT] season {SEASON} | target comp: {', '.join(TARGET_COMP[:8])} ...")

    def search_match(self, screen):
        """Press the lobby 'Batalla' button to start a match"""
        pos = self.image_processor.find_template(screen, SEARCH_BUTTON, SEARCH_THRESHOLD)
        if not pos:
            return False
        logger.info(f"[SEARCH] pressing Batalla at {pos}")
        self.adb.tap(*pos)
        self._deploy_played = False
        self._last_deploy_ts = 0.0
        self.game_logic.start_run()
        time.sleep(2.5)
        return True

    def handle_end_screen(self, screen):
        """Leave the results/elimination screens and start the next match"""
        for name in ("rematch", "view", "leave"):
            pos = self.image_processor.find_template(screen, END_BUTTONS[name], END_BUTTON_THRESHOLD)
            if not pos:
                continue
            logger.info(f"[END] tapping {name} at {pos}")
            self.adb.tap(*pos)
            if name == "rematch":
                self._deploy_played = False
                self.game_logic.start_run()
            time.sleep(1.0)
            return True
        return False

    def handle_deploy_phase(self, screen):
        """Pop the orbs, then buy and merge; returns the planner summary"""
        now = time.time()
        # Rounds are ~25s apart; a much longer gap means a new match started.
        if now - self._last_deploy_ts > 90:
            self.game_logic.start_run()
        self._last_deploy_ts = now

        summary = self.game_logic.deploy_phase(screen)
        if summary["elixir"] is not None:
            self.last_elixir_value = summary["elixir"]
        return summary

    def collect_orbs(self, screen):
        """Tap every quest orb on the arena; they hand out money"""
        for x, y in self.game_logic.reader.orbs(screen):
            logger.info(f"[ORB] collect at ({x}, {y})")
            self.adb.tap(x, y)
            time.sleep(0.15)

    def run(self, auto_search=True, duration=None):
        deadline = time.time() + duration if duration else None
        last_search = 0.0
        logger.info("[BOT] running" + (" (auto search)" if auto_search else ""))

        while True:
            if deadline and time.time() >= deadline:
                logger.info("[BOT] duration reached, stopping")
                break

            try:
                screen = self.adb.screenshot()
            except Exception as e:
                logger.error(f"[BOT] screenshot failed: {e}")
                time.sleep(ERROR_DELAY)
                continue

            if self.handle_end_screen(screen):
                last_search = time.time()
                continue

            phase = self.game_logic.phase(screen)
            # Orbs give money and can show up in any colour during deploy and
            # battle, so grab any on screen every frame.
            if phase in ("deploy", "battle"):
                self.collect_orbs(screen)
            if phase == "deploy":
                if not self._deploy_played:
                    summary = self.handle_deploy_phase(screen)
                    # Only commit the round when the shop was actually read.
                    # "no_cards" means recognition failed (e.g. purchase
                    # animation), so retry on a later frame instead of skipping.
                    if (summary and summary.get("elixir") is not None
                            and summary.get("reason") != "no_cards"):
                        self._deploy_played = True
                time.sleep(0.8)
            elif phase == "battle":
                self._deploy_played = False
                time.sleep(BATTLE_WAIT)
            else:
                # Lobby or unknown screen: search for a match (throttled).
                if auto_search and time.time() - last_search >= SEARCH_RETRY_SECONDS:
                    if self.search_match(screen):
                        last_search = time.time()
                time.sleep(2.0)


def main():
    parser = argparse.ArgumentParser(description="Headless Merge Tactics bot")
    parser.add_argument("--no-search", action="store_true",
                        help="do not press Batalla; only play a match already started")
    parser.add_argument("--duration", type=float, default=None,
                        help="stop after this many seconds")
    args = parser.parse_args()

    try:
        MergeTacticsBot().run(auto_search=not args.no_search, duration=args.duration)
    except KeyboardInterrupt:
        logger.info("[BOT] interrupted by user")


if __name__ == "__main__":
    main()
