"""
Main window controller for the Merge Tactics bot GUI.
Coordinates the UI components and main application loop.
"""

import cv2
import threading
import logging
from gui.ui_manager import UIManager
from gui.event_handler import EventHandler

logger = logging.getLogger(__name__)

class MainWindow:
    def __init__(self, composition_manager, bot_controller):
        self.composition_manager = composition_manager
        self.bot_controller = bot_controller
        self.ui_manager = UIManager(composition_manager)
        self.event_handler = EventHandler(self.ui_manager, bot_controller)
        self.window_name = "Merge Tactics Bot"
        self.running = True
        
    def initialize(self, unit_files, unit_imgs):
        """Initialize the window with unit data"""
        self.ui_manager.initialize_units(unit_files, unit_imgs)
        self.window_name = self.event_handler.setup_window(self.window_name)
        
    def start_bot_thread(self):
        """Start the bot loop in a separate thread"""
        bot_thread = threading.Thread(target=self.bot_controller.run_loop, daemon=True)
        bot_thread.start()
        logger.info("Bot thread started")
        
    def run(self):
        """Run the main GUI loop"""
        logger.info("Starting main GUI loop")
        
        while self.running:
            try:
                # Draw UI
                canvas = self.ui_manager.draw_ui(
                    bot_running=self.bot_controller.is_running(),
                    elixir_value=getattr(self.bot_controller, 'last_elixir_value', None)
                )
                
                # Display
                cv2.imshow(self.window_name, canvas)
                
                # Handle keyboard input
                key = cv2.waitKey(20) & 0xFF
                if not self.event_handler.handle_keyboard(key):
                    break
                    
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                break
                
        self.cleanup()
        
    def cleanup(self):
        """Clean up resources"""
        logger.info("Cleaning up GUI resources")
        self.bot_controller.stop_bot()
        cv2.destroyAllWindows()
        self.running = False
        
    def stop(self):
        """Stop the main window"""
        self.running = False
