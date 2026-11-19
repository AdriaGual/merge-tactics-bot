"""Diagnose what the bot sees in a screenshot."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
from core.image_processing import ImageProcessor
from core.board_state import BoardReader
from core.card_identifier import load_art_library
from config.game_phases import PHASE_TEMPLATES

screen = cv2.imread(sys.argv[1])
if screen is None:
    sys.exit("cannot read " + sys.argv[1])
print("shape", screen.shape)

ip = ImageProcessor()
print("\n== PHASE ==")
reader = BoardReader(ip)
print("phase:", reader.phase(screen))

print("\n== OLD TEMPLATES (max score over full screen) ==")
for name, path in PHASE_TEMPLATES.items():
    tpl = cv2.imread(path)
    if tpl is None:
        print(f"{name:12s} MISSING {path}")
        continue
    if tpl.shape[0] > screen.shape[0] or tpl.shape[1] > screen.shape[1]:
        print(f"{name:12s} template larger than screen")
        continue
    res = cv2.matchTemplate(screen, tpl, cv2.TM_CCOEFF_NORMED)
    _, mx, _, mloc = cv2.minMaxLoc(res)
    print(f"{name:12s} score={mx:.3f} at={mloc}")

print("\n== READ ==")
state = reader.read(screen)
print("phase:", state.phase)
print("elixir:", state.elixir)
print("orbs:", state.orbs)
print("own_units:", state.own_units)
print("cards:", [(c.name, c.cost, c.center) for c in state.cards])
