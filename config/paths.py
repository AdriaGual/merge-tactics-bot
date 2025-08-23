import os
import cv2

UNITS_DIR = "templates/units"       
FIELDS_DIR = "templates/field"      
BENCH_DIR = "templates/bench"       
GRID_FILE = "grid_positions.json"
COMPOSITION_FILE = "composition.json"
ELIXIR_FILE = "elixir.json"
BENCH_FILE = "bench.json"
ADB_PATH = "adb"
THRESHOLD = 0.85

TEMPLATES_DIR_MAIN = "templates"
INIT_BATTLE = os.path.join(TEMPLATES_DIR_MAIN, "battle.png")
PHASE_DEPLOY = os.path.join(TEMPLATES_DIR_MAIN, "deploy_phase.png")
PHASE_BATTLE = os.path.join(TEMPLATES_DIR_MAIN, "battle_phase.png")
PLAY_AGAIN_BATTLE = os.path.join(TEMPLATES_DIR_MAIN, "play_again.png")
QUIT = os.path.join(TEMPLATES_DIR_MAIN, "quit.png")
SELL_BUTTON = os.path.join(TEMPLATES_DIR_MAIN, "sell.png")
REWARD = os.path.join(TEMPLATES_DIR_MAIN, "reward.png")
EMPTY_BENCH = os.path.join(TEMPLATES_DIR_MAIN, "empty_bench.png")
BACK = os.path.join(TEMPLATES_DIR_MAIN, "back.png")

def load_unit_images():
    unit_files = [f for f in os.listdir(UNITS_DIR) if f.endswith(".png")]
    unit_imgs = [cv2.imread(os.path.join(UNITS_DIR, f)) for f in unit_files]
    selected = [False]*len(unit_imgs)
    return unit_files, unit_imgs, selected

def load_field_images():
    field_files = [f for f in os.listdir(FIELDS_DIR) if f.endswith(".png")]
    field_imgs = [cv2.imread(os.path.join(FIELDS_DIR, f)) for f in field_files]
    return field_files, field_imgs

def load_bench_images():
    bench_files = [f for f in os.listdir(BENCH_DIR) if f.endswith(".png")]
    bench_imgs = [cv2.imread(os.path.join(BENCH_DIR, f)) for f in bench_files]
    return bench_files, bench_imgs