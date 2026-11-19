"""
Play Merge Tactics in a loop (safe at the lobby).

Only acts inside a match and on the end-of-match screens:
  - deploy phase: pop orbs + buy/merge once per round
  - battle phase: wait
  - results/elimination/spectate: leave / rematch

At the lobby (or any unknown screen) it does nothing, so start the first match
yourself with Batalla; afterwards it keeps playing and rematching on its own.
"""
import os
import sys
import time
import types
import traceback

PROJECT = r"F:\WebPages\2025\merge-tactics-bot"
sys.path.insert(0, PROJECT)
os.chdir(PROJECT)

from bot import MergeTacticsBot
from core.adb_controller import ADBController
from core.image_processing import ImageProcessor
from core.game_logic import GameLogic
from config.paths import ADB_PATH
from config.target_comp import TARGET_COMP

adb = ADBController(ADB_PATH)
ip = ImageProcessor()
logic = GameLogic(adb, ip)
logic.start_run()


class Shim:
    pass


sh = Shim()
sh.adb = adb
sh.image_processor = ip
sh.game_logic = logic
sh.last_elixir_value = 0
sh._deploy_played = False
sh._last_deploy_ts = 0.0
sh._handle_end_screen = types.MethodType(MergeTacticsBot._handle_end_screen, sh)
sh._handle_deploy_phase = types.MethodType(MergeTacticsBot._handle_deploy_phase, sh)

print(f"[loop] armed, target comp starts with {TARGET_COMP[:6]}", flush=True)
last_phase = "?"
while True:
    try:
        screen = adb.screenshot()

        if sh._handle_end_screen(screen):
            last_phase = "end"
            continue

        phase = logic.phase(screen)
        if phase != last_phase:
            print(f"[loop] {time.strftime('%H:%M:%S')} phase -> {phase}", flush=True)
            last_phase = phase

        if phase == "deploy":
            if not sh._deploy_played:
                summary = sh._handle_deploy_phase(screen)
                if summary and summary.get("elixir") is not None:
                    sh._deploy_played = True
            time.sleep(0.8)
        elif phase == "battle":
            sh._deploy_played = False
            time.sleep(1.5)
        else:
            # lobby / unknown: idle until a match is started
            time.sleep(2.0)
    except KeyboardInterrupt:
        print("[loop] interrupted", flush=True)
        break
    except Exception as e:
        print(f"[loop] error: {e}", flush=True)
        traceback.print_exc()
        time.sleep(1.5)
