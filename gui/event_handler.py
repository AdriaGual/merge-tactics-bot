"""
Event handling module for the GUI.
Manages OpenCV window events and user interactions.
"""

import cv2
import logging

logger = logging.getLogger(__name__)

class EventHandler:
    def __init__(self, ui_manager, bot_controller):
        self.ui_manager = ui_manager
        self.bot_controller = bot_controller
        
    def setup_window(self, window_name="Merge Tactics Bot"):
        """Setup the OpenCV window and mouse callback"""
        cv2.namedWindow(window_name)
        cv2.setMouseCallback(window_name, self._mouse_callback)
        return window_name
        
    def _mouse_callback(self, event, x, y, flags, param):
        """Handle mouse events"""
        if event == cv2.EVENT_LBUTTONDOWN:
            self.ui_manager.handle_click(x, y, self.bot_controller)
            
    def handle_keyboard(self, key):
        """Handle keyboard events"""
        if key == 27:  # ESC key
            return False  # Signal to exit
        elif key == ord('s'):
            self.bot_controller.start_bot()
            self.ui_manager.add_log("Bot started (keyboard)")
        elif key == ord('q'):
            self.bot_controller.stop_bot()
            self.ui_manager.add_log("Bot stopped (keyboard)")
        elif key == ord('c'):
            composition = self.ui_manager.composition_manager.save_composition(
                self.ui_manager.unit_files, self.ui_manager.selected
            )
            self.ui_manager.add_log(f"Composition saved (keyboard): {composition}")
        elif key == ord('r'):
            self.ui_manager.clear_selection()
            
        return True  # Continue running
