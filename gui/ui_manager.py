"""
GUI management module for the Merge Tactics bot.
Handles OpenCV-based user interface and interactions.
"""

import cv2
import numpy as np
import os
import json
import logging
from config.constants import IMG_SIZE, MARGIN, COLS, LOG_HEIGHT, INFO_PANEL_WIDTH, BUTTONS_OFFSET, MAX_LOG_ENTRIES
from config.ui import BUTTONS

logger = logging.getLogger(__name__)

class UIManager:
    def __init__(self, composition_manager):
        self.composition_manager = composition_manager
        self.logs = []
        self.selected = []
        self.unit_files = []
        self.unit_imgs = []
        
    def initialize_units(self, unit_files, unit_imgs):
        """Initialize unit data for the UI"""
        self.unit_files = unit_files
        self.unit_imgs = unit_imgs
        self.selected = [False] * len(unit_files)
        
    def add_log(self, msg):
        """Add a log message and limit the length"""
        self.logs.append(msg)
        if len(self.logs) > MAX_LOG_ENTRIES:
            self.logs = self.logs[-MAX_LOG_ENTRIES:]
        logger.info(f"[UI] {msg}")

    def draw_ui(self, bot_running=False, elixir_value=None):
        """Draw the main UI canvas"""
        rows = (len(self.unit_imgs)-1)//COLS + 1
        canvas_h = rows*(IMG_SIZE[1]+MARGIN) + MARGIN + LOG_HEIGHT
        canvas_w = max(COLS*(IMG_SIZE[0]+MARGIN)+MARGIN, 400) + INFO_PANEL_WIDTH
        canvas = np.ones((canvas_h, canvas_w, 3), dtype=np.uint8) * 255
        
        # Draw unit thumbnails
        self._draw_unit_thumbnails(canvas)
        
        # Draw buttons
        self._draw_buttons(canvas, bot_running)
        
        # Calculate info panel position
        info_x0 = max(COLS*(IMG_SIZE[0]+MARGIN)+MARGIN, 400) + MARGIN
        y_offset = MARGIN + 20
        self._draw_info_panel(canvas, info_x0, y_offset, elixir_value)
        
        return canvas

    def _draw_unit_thumbnails(self, canvas):
        """Draw unit thumbnail grid with selection indicators"""
        from config.unit_costs import unit_costs
        
        for idx, img in enumerate(self.unit_imgs):
            row = idx // COLS
            col = idx % COLS
            x = col * (IMG_SIZE[0] + MARGIN) + MARGIN
            y = row * (IMG_SIZE[1] + MARGIN) + MARGIN
            
            # Draw thumbnail
            thumb = cv2.resize(img, IMG_SIZE)
            canvas[y:y+IMG_SIZE[1], x:x+IMG_SIZE[0]] = thumb
            
            # Draw selection border
            if self.selected[idx]:
                cv2.rectangle(canvas, (x, y), (x+IMG_SIZE[0], y+IMG_SIZE[1]), (0, 255, 0), 3)
            
            # Draw unit cost
            unit_name = os.path.splitext(self.unit_files[idx])[0]
            cost = unit_costs.get(unit_name, "?")
            cv2.putText(canvas, str(cost), (x+5, y+20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    def _draw_buttons(self, canvas, bot_running):
        """Draw control buttons"""
        draw_buttons = {
            name: (x0, y0+BUTTONS_OFFSET, x1, y1+BUTTONS_OFFSET) 
            for name, (x0, y0, x1, y1) in BUTTONS.items()
        }

        for name, (x0, y0, x1, y1) in draw_buttons.items():
            if name == "start":
                color = (0, 200, 0) if not bot_running else (150, 150, 150)
            elif name == "stop":
                color = (0, 0, 255) if bot_running else (150, 150, 150)
            else:
                color = (100, 100, 200)
                
            cv2.rectangle(canvas, (x0, y0), (x1, y1), color, -1)
            cv2.putText(canvas, name.capitalize(), (x0+5, y0+25), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    def _draw_info_panel(self, canvas, info_x0, y_offset, elixir_value=None):
        """Draw the information panel with composition and logs"""
        info_x1 = canvas.shape[1] - MARGIN
        canvas_h = canvas.shape[0]
        
        # Draw panel background
        cv2.rectangle(canvas, (info_x0, MARGIN), (info_x1, canvas_h-MARGIN), (245, 245, 245), -1)
        
        # Draw current composition
        y_offset = self._draw_composition_section(canvas, info_x0, y_offset)
        
        # Draw elixir value
        if elixir_value is not None:
            cv2.putText(canvas, f"Elixir: {elixir_value}", (info_x0+5, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 100, 255), 1)
            y_offset += 25
            
        # Draw logs
        self._draw_logs_section(canvas, info_x0, y_offset)

    def _draw_composition_section(self, canvas, info_x0, y_offset):
        """Draw the current composition section"""
        cv2.putText(canvas, "Actual Composition:", (info_x0+5, y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 0), 2)
        y_offset += 25
        
        composition_display = self.composition_manager.get_composition_display()
        
        if composition_display:
            for unit in composition_display:
                unit_display = os.path.splitext(unit)[0] if isinstance(unit, str) else str(unit)
                cv2.putText(canvas, f"- {" ".join(word.capitalize() for word in unit_display.split("_"))}", (info_x0+10, y_offset), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (50, 50, 50), 1)
                y_offset += 18
        else:
            cv2.putText(canvas, "  Cap composicio", (info_x0+10, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (100, 100, 100), 1)
            y_offset += 18
            
        return y_offset + 10

    def _draw_logs_section(self, canvas, info_x0, y_offset):
        """Draw the logs section"""
        cv2.putText(canvas, "Logs:", (info_x0+5, y_offset), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 2)
        y_offset += 20
        
        for log_line in self.logs[-10:]:
            cv2.putText(canvas, log_line, (info_x0+5, y_offset), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (80, 80, 80), 1)
            y_offset += 18

    def handle_click(self, x, y, bot_controller):
        """Handle mouse click events"""
        # Check unit thumbnail clicks
        if self._handle_unit_click(x, y):
            return True
            
        # Check button clicks
        return self._handle_button_click(x, y, bot_controller)

    def _handle_unit_click(self, x, y):
        """Handle clicks on unit thumbnails"""
        for idx in range(len(self.unit_imgs)):
            row = idx // COLS
            col = idx % COLS
            x0 = col * (IMG_SIZE[0] + MARGIN) + MARGIN
            y0 = row * (IMG_SIZE[1] + MARGIN) + MARGIN
            x1 = x0 + IMG_SIZE[0]
            y1 = y0 + IMG_SIZE[1]
            
            if x0 <= x <= x1 and y0 <= y <= y1:
                self.selected[idx] = not self.selected[idx]
                unit_name = os.path.splitext(self.unit_files[idx])[0]
                status = 'selected' if self.selected[idx] else 'deselected'
                self.add_log(f"{unit_name} {status}")
                return True
        return False

    def _handle_button_click(self, x, y, bot_controller):
        """Handle clicks on control buttons"""
        for name, (x0, y0, x1, y1) in BUTTONS.items():
            # Apply the same offset used when drawing buttons
            offset_y0 = y0 + BUTTONS_OFFSET
            offset_y1 = y1 + BUTTONS_OFFSET
            
            if x0 <= x <= x1 and offset_y0 <= y <= offset_y1:
                if name == "start":
                    bot_controller.start_bot()
                    self.add_log("Bot started")
                elif name == "stop":
                    bot_controller.stop_bot()
                    self.add_log("Bot stopped")
                elif name == "confirm":
                    composition = self.composition_manager.save_composition(self.unit_files, self.selected)
                    self.add_log(f"Composition saved: {composition}")
                return True
        return False

    def get_selected_units(self):
        """Get currently selected units"""
        return [i for i, selected in enumerate(self.selected) if selected]

    def clear_selection(self):
        """Clear all unit selections"""
        self.selected = [False] * len(self.selected)
        self.add_log("Selection cleared")
