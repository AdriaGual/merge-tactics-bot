"""
Core game logic for the Merge Tactics bot.

A deploy phase is the only moment with real decisions: pop the quest orbs, then
spend the elixir on the shop while preferring duplicates (a duplicate merges and
refunds one elixir). The vision side lives in BoardReader, the decision rules in
DeployPlanner, and this class keeps the per-match state.
"""

import logging

from core.board_state import BoardReader
from core.strategy import DeployPlanner, RunState

logger = logging.getLogger(__name__)


class GameLogic:
    def __init__(self, adb_controller, image_processor):
        self.adb = adb_controller
        self.image_processor = image_processor
        self.reader = BoardReader(image_processor)
        self.planner = DeployPlanner(self.reader, self.adb)
        self.run_state = RunState()

    def start_run(self):
        """Forget the troops of the previous match"""
        self.run_state = RunState()
        logger.info("[RUN] new match state")

    def deploy_phase(self, screen):
        """Play one deploy phase and return a summary of what happened"""
        return self.planner.play(screen, self.run_state)

    def phase(self, screen):
        return self.reader.phase(screen)
