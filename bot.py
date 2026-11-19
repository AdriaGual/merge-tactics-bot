"""
Main bot controller for Merge Tactics bot.
Refactored and modularized version with clean architecture.
"""

import json
import time
import logging
from core.adb_controller import ADBController
from core.image_processing import ImageProcessor
from core.game_logic import GameLogic
from core.composition_manager import CompositionManager
from gui.main_window import MainWindow
from utils.cache_manager import CacheManager
from config.paths import (
    GRID_FILE, COMPOSITION_FILE, ELIXIR_FILE, BENCH_FILE, ADB_PATH,
    load_unit_images
)
from config.game_phases import PHASE_TEMPLATES
from config.board_layout import END_BUTTONS, END_BUTTON_THRESHOLD
from config.constants import (
    BOT_LOOP_DELAY, ERROR_DELAY, ACTION_DELAY, BATTLE_WAIT,
    THRESHOLD
)
from config.logging_config import setup_logging
import cv2

# Setup logging
logger = setup_logging()

class MergeTacticsBot:
    def __init__(self):
        # Initialize core components
        self.adb = ADBController(ADB_PATH)
        self.image_processor = ImageProcessor()
        self.cache_manager = CacheManager()
        self.game_logic = GameLogic(self.adb, self.image_processor)
        self.composition_manager = CompositionManager(COMPOSITION_FILE)
        
        # Bot state
        self.bot_running = False
        self.composition = []
        self.last_elixir_value = 0
        self._last_deploy_ts = 0.0
        self._deploy_played = False
        
        # Load game data
        self._load_game_data()
        
        # Initialize GUI
        self.main_window = MainWindow(self.composition_manager, self)
        
    def _load_game_data(self):
        """Load all game data files and images"""
        # Load unit images (shop card templates, also shown in the GUI)
        self.unit_files, self.unit_imgs, _ = load_unit_images()

        # Load coordinate data
        with open(GRID_FILE, "r") as f:
            grid_data = json.load(f)
        self.grid_cells = [item for item in grid_data if item["name"].startswith("camp")]
        self.bench_cells = [item for item in grid_data if item["name"].startswith("banquillo")]

        with open(ELIXIR_FILE, "r") as f:
            elixir_data = json.load(f)
        self.elixir_rect = next(item["rect"] for item in elixir_data if item["name"]=="elixir")

        with open(BENCH_FILE, "r") as f:
            bench_data = json.load(f)
        self.bench_rect = next(item["rect"] for item in bench_data if item["name"]=="bench")

        logger.info("Game data loaded successfully")

    def start_bot(self):
        """Start the bot"""
        self.bot_running = True
        self.game_logic.start_run()
        logger.info(f"[DEBUG] Bot started - bot_running set to: {self.bot_running}")

    def stop_bot(self):
        """Stop the bot"""
        self.bot_running = False
        logger.info(f"[DEBUG] Bot stopped - bot_running set to: {self.bot_running}")

    def is_running(self):
        """Check if bot is running"""
        return self.bot_running

    def run_loop(self):
        """Main bot loop - optimized and modular"""
        logger.info("Bot loop started")
        iteration_count = 0
        
        while True:
            
            if self.bot_running:
                iteration_count += 1
                
                # Load composition if not loaded
                if not self.composition:
                    self.composition = self.composition_manager.load_composition()
                    if not self.composition:
                        logger.error("No composition loaded")
                        self.bot_running = False
                        continue
                    logger.info(f"Loaded composition: {self.composition}")
                
                try:
                    time.sleep(BOT_LOOP_DELAY)
                    screen = self.adb.screenshot()
                except Exception as e:
                    logger.error(f"Screenshot failed: {e}")
                    time.sleep(ERROR_DELAY)
                    continue

                # Process game phases
                if self._handle_game_phases(screen):
                    continue
                    
                time.sleep(ACTION_DELAY)
            else:
                time.sleep(ACTION_DELAY)

    def _handle_end_screen(self, screen):
        """Leave the results/elimination screens and start the next match"""
        for name in ("rematch", "view", "leave"):
            pos = self.image_processor.find_template(
                screen, END_BUTTONS[name], END_BUTTON_THRESHOLD
            )
            if not pos:
                continue
            logger.info(f"[END] tapping {name} button at {pos}")
            self.adb.tap(*pos)
            if name == "rematch":
                # A fresh match forgets the troops bought in the previous one.
                self._deploy_played = False
                self.game_logic.start_run()
            time.sleep(ACTION_DELAY)
            return True
        return False

    def _handle_game_phases(self, screen):
        """Handle different game phases"""
        # End-of-match screens come first: while spectating survivors the phase
        # label still reads "deploy", so these buttons must win over phase logic.
        if self._handle_end_screen(screen):
            return True

        phase = self.game_logic.phase(screen)
        if phase == "deploy":
            # Play each deploy phase once, but if the opening modal still hides
            # the elixir badge the read comes back empty: retry on the next
            # frames instead of skipping the whole round.
            if not self._deploy_played:
                summary = self._handle_deploy_phase(screen)
                if summary and summary.get("elixir") is not None:
                    self._deploy_played = True
            time.sleep(ERROR_DELAY)
            return True
        if phase == "battle":
            # The next round opens with its own deploy phase.
            self._deploy_played = False
            time.sleep(BATTLE_WAIT)
            return True

        # Check for reward
        reward_pos = self.image_processor.find_template(screen, PHASE_TEMPLATES['reward'], THRESHOLD)
        if reward_pos:
            logger.info("Collecting reward")
            self.adb.tap(*reward_pos)
            time.sleep(ERROR_DELAY)
            return True
        
        # Check for battle initialization
        init_pos = self.image_processor.find_template(screen, PHASE_TEMPLATES['init_battle'], THRESHOLD)
        if init_pos:
            logger.info("Starting battle")
            self.adb.tap(*init_pos)
            time.sleep(ACTION_DELAY)
            return True

        # Check for play again
        play_again = self.image_processor.find_template(screen, PHASE_TEMPLATES['play_again'], THRESHOLD)
        if play_again:
            logger.info("Playing again")
            self.adb.tap(*play_again)
            time.sleep(ACTION_DELAY)
            return True
        
        # Check for back button
        back = self.image_processor.find_template(screen, PHASE_TEMPLATES['back'], THRESHOLD)
        if back:
            logger.info("Going back")
            self.adb.tap(*back)
            time.sleep(ACTION_DELAY)
            return True

        # Check for quit
        quit_pos = self.image_processor.find_template(screen, PHASE_TEMPLATES['quit'], THRESHOLD)
        if quit_pos:
            logger.info("Quitting")
            self.adb.tap(*quit_pos)
            time.sleep(ACTION_DELAY)
            return True

        return False

    def _handle_deploy_phase(self, screen):
        """Play the deploy phase: pop the orbs, then buy and merge"""
        now = time.time()
        # Rounds are ~25s apart: a much longer gap means a new match started and
        # the troops remembered from the previous one are gone.
        if now - self._last_deploy_ts > 90:
            self.game_logic.start_run()
        self._last_deploy_ts = now

        summary = self.game_logic.deploy_phase(screen, self.composition)
        if summary["elixir"] is not None:
            self.last_elixir_value = summary["elixir"]
        return summary

    def run_gui(self):
        """Run the GUI application"""
        logger.info("Starting GUI application")
        
        # Initialize GUI with unit data
        self.main_window.initialize(self.unit_files, self.unit_imgs)
        
        # Start bot thread
        self.main_window.start_bot_thread()
        
        # Run main GUI loop
        self.main_window.run()

def main():
    """Main entry point"""
    try:
        bot = MergeTacticsBot()
        bot.run_gui()
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
        raise

if __name__ == "__main__":
    main()
