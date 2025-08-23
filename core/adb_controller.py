"""
ADB controller module for the Merge Tactics bot.
Handles all Android Debug Bridge interactions.
"""

import subprocess
import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)

class ADBController:
    def __init__(self, adb_path):
        self.adb_path = adb_path
        
    def screenshot(self):
        """Take a screenshot using ADB"""
        try:
            result = subprocess.run([self.adb_path, "exec-out", "screencap", "-p"], stdout=subprocess.PIPE)
            img = cv2.imdecode(np.frombuffer(result.stdout, np.uint8), cv2.IMREAD_COLOR)
            return img
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            raise

    def tap(self, x, y):
        """Perform a tap at coordinates (x, y)"""
        try:
            subprocess.run([self.adb_path, "shell", "input", "tap", str(x), str(y)])
        except Exception as e:
            logger.error(f"Tap failed at ({x}, {y}): {e}")
            raise
