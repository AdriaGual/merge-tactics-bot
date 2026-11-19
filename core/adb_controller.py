"""
ADB controller module for the Merge Tactics bot.
Handles all Android Debug Bridge interactions.
"""

import os
import subprocess
import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)


class ADBController:
    def __init__(self, adb_path, serial=None):
        self.adb_path = adb_path
        # BlueStacks exposes the same instance twice (emulator-5554 + 127.0.0.1:5555),
        # so a bare "adb" call fails with "more than one device/emulator".
        self.serial = serial or os.environ.get("ADB_SERIAL") or self._detect_serial()

    def _detect_serial(self):
        """Pick the device to control when more than one is attached"""
        try:
            result = subprocess.run(
                [self.adb_path, "devices"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=15,
            )
        except Exception as e:
            logger.warning(f"Could not list adb devices: {e}")
            return None

        devices = []
        for line in result.stdout.splitlines()[1:]:
            parts = line.split()
            if len(parts) >= 2 and parts[1] == "device":
                devices.append(parts[0])

        if not devices:
            logger.warning("No online adb device found")
            return None

        if len(devices) == 1:
            logger.info(f"Using adb device {devices[0]}")
            return devices[0]

        emulator = next((d for d in devices if d.startswith("emulator-")), devices[0])
        logger.warning(
            f"Multiple adb devices ({', '.join(devices)}), using {emulator}. "
            f"Set ADB_SERIAL to override."
        )
        return emulator

    def _adb_cmd(self, *args):
        """Build an adb command bound to the selected device"""
        cmd = [self.adb_path]
        if self.serial:
            cmd += ["-s", self.serial]
        return cmd + list(args)

    def screenshot(self):
        """Take a screenshot using ADB"""
        try:
            result = subprocess.run(
                self._adb_cmd("exec-out", "screencap", "-p"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            raise

        if not result.stdout:
            error = result.stderr.decode(errors="replace").strip() or "empty output"
            logger.error(f"Screenshot failed: {error}")
            raise RuntimeError(f"Screenshot failed: {error}")

        img = cv2.imdecode(np.frombuffer(result.stdout, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            logger.error("Screenshot failed: could not decode image")
            raise RuntimeError("Screenshot failed: could not decode image")
        return img

    def tap(self, x, y):
        """Perform a tap at coordinates (x, y)"""
        try:
            subprocess.run(self._adb_cmd("shell", "input", "tap", str(x), str(y)))
        except Exception as e:
            logger.error(f"Tap failed at ({x}, {y}): {e}")
            raise
