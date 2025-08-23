"""
Composition management module for the Merge Tactics bot.
Handles loading, saving, and managing unit compositions.
"""

import json
import os
import logging

logger = logging.getLogger(__name__)

class CompositionManager:
    def __init__(self, composition_file):
        self.composition_file = composition_file
        
    def save_composition(self, unit_files, selected):
        """Save the current composition to file"""
        chosen_units = [os.path.splitext(unit_files[i])[0] for i, sel in enumerate(selected) if sel]
        data = {"name": "Custom Deck", "units": chosen_units}
        
        try:
            with open(self.composition_file, "w") as f:
                json.dump(data, f, indent=4)
            print(f"[COMP] Composicio confirmada: {chosen_units}")
            return chosen_units
        except Exception as e:
            logger.error(f"Failed to save composition: {e}")
            return []

    def load_composition(self):
        """Load composition from file"""
        if not os.path.exists(self.composition_file):
            return []
            
        try:
            with open(self.composition_file, "r") as f:
                data = json.load(f)
                units = data.get("units", [])
                return [os.path.splitext(u)[0] for u in units]
        except (json.JSONDecodeError, FileNotFoundError) as e:
            logger.error(f"Failed to load composition: {e}")
            return []

    def get_composition_display(self):
        """Get composition for display purposes"""
        if not os.path.exists(self.composition_file):
            return []
            
        try:
            with open(self.composition_file, "r") as f:
                data = json.load(f)
                return data.get("units", [])
        except (json.JSONDecodeError, FileNotFoundError):
            return []
