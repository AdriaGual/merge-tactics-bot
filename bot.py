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
    load_unit_images, load_field_images, load_bench_images
)
from config.game_phases import PHASE_TEMPLATES
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
        
        # Load game data
        self._load_game_data()
        
        # Initialize GUI
        self.main_window = MainWindow(self.composition_manager, self)
        
    def _load_game_data(self):
        """Load all game data files and images"""
        # Load unit images
        self.unit_files, self.unit_imgs, _ = load_unit_images()
        self.field_files, self.field_imgs = load_field_images()
        self.bench_files, self.bench_imgs = load_bench_images()
        
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

    def _handle_game_phases(self, screen):
        """Handle different game phases"""
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

        # Check for deploy phase
        deploy = self.image_processor.find_template(screen, PHASE_TEMPLATES['phase_deploy'], THRESHOLD)
        if deploy:
            logger.info("Deploy phase detected")
            self._handle_deploy_phase(screen)
            time.sleep(ERROR_DELAY)
            return True

        # Check for battle phase
        battle_phase = self.image_processor.find_template(screen, PHASE_TEMPLATES['phase_battle'], THRESHOLD)
        if battle_phase:
            logger.info("Battle phase - waiting")
            time.sleep(BATTLE_WAIT)
            return True

        return False

    def _handle_deploy_phase(self, screen):
        """Handle the deploy phase"""
        elixir_value = self.image_processor.read_elixir(screen, self.elixir_rect)
        
        if elixir_value is not None:
            self.last_elixir_value = elixir_value
        else:
            logger.warning("Failed to read elixir, using fallback taps")
            # Fallback: tap some common positions
            self.adb.tap(200, 1500)
            self.adb.tap(400, 1500)
            self.adb.tap(550, 1500)
            return

        if self.last_elixir_value > 0:
            self.last_elixir_value = self.game_logic.deploy_units(
                screen, self.composition, self.last_elixir_value,
                self.unit_files, self.unit_imgs, self.field_imgs, self.bench_imgs,
                self.field_files, self.bench_files, self.grid_cells, self.bench_cells,
                self.elixir_rect, THRESHOLD
            )
        else:
            logger.info("No elixir available")

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
