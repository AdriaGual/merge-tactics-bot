import cv2
import numpy as np
import os
import json
import threading
import time
import subprocess
import pytesseract
import logging
from functools import wraps

# 🔧 Configuració
UNITS_DIR = "templates/units"       
FIELDS_DIR = "templates/field"      
BENCH_DIR = "templates/bench"       
GRID_FILE = "grid_positions.json"
COMPOSITION_FILE = "composition.json"
ELIXIR_FILE = "elixir.json"
ADB_PATH = "adb"
THRESHOLD = 0.6

# Botons Start/Stop/Confirm
BUTTONS = {
    "start": (10, 10, 100, 50),
    "stop":  (120, 10, 210, 50),
    "confirm": (230, 10, 350, 50)
}

bot_running = False

# Templates bot
TEMPLATES_DIR_MAIN = "templates"
INIT_BATTLE = os.path.join(TEMPLATES_DIR_MAIN, "battle.png")
PHASE_DEPLOY = os.path.join(TEMPLATES_DIR_MAIN, "deploy_phase.png")
PHASE_BATTLE = os.path.join(TEMPLATES_DIR_MAIN, "battle_phase.png")
PLAY_AGAIN_BATTLE = os.path.join(TEMPLATES_DIR_MAIN, "play_again.png")
QUIT = os.path.join(TEMPLATES_DIR_MAIN, "quit.png")
SELL_BUTTON = os.path.join(TEMPLATES_DIR_MAIN, "sell.png")
REWARD = os.path.join(TEMPLATES_DIR_MAIN, "reward.png")
EMPTY_BENCH = os.path.join(TEMPLATES_DIR_MAIN, "empty_bench.png")

# 🔹 Carregar unitats i costos
unit_files = [f for f in os.listdir(UNITS_DIR) if f.endswith(".png")]
unit_imgs = [cv2.imread(os.path.join(UNITS_DIR, f)) for f in unit_files]
selected = [False]*len(unit_imgs)

field_files = [f for f in os.listdir(FIELDS_DIR) if f.endswith(".png")]
field_imgs = [cv2.imread(os.path.join(FIELDS_DIR, f)) for f in field_files]

bench_files = [f for f in os.listdir(BENCH_DIR) if f.endswith(".png")]
bench_imgs = [cv2.imread(os.path.join(BENCH_DIR, f)) for f in bench_files]

# Assigna el cost manualment aquí
unit_costs = {
    "barbarian": 2, "archer": 3, "knight": 2, "archer_queen": 5, "bandit": 4,
    "bomber": 2, "dart_goblin": 3, "executioner": 3, "giant_skeleton": 3,
    "goblin": 2, "goblin_machine": 4, "golden_knight": 5, "mega_knight": 4,
    "pekka": 3, "prince": 3, "princess": 4, "royal_ghost": 4, "skeleton_king": 5,
    "spear_goblin": 2, "valkyrie": 3,   
}

# Carregar coordenades del camp i banquillo
with open(GRID_FILE, "r") as f:
    grid_data = json.load(f)

grid_cells = [item for item in grid_data if item["name"].startswith("camp")]
bench_cells = [item for item in grid_data if item["name"].startswith("banquillo")]

# Carregar coordenades elixir
with open(ELIXIR_FILE, "r") as f:
    elixir_data = json.load(f)
elixir_rect = next(item["rect"] for item in elixir_data if item["name"]=="elixir")

logging.basicConfig(level=logging.WARNING, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

DEBUG_MODE = False  # Disabled debug mode for performance
DEBUG_SAVE_IMAGES = False

# 🔹 Carregar plantilles de dígits
def load_digit_templates():
    """Load digit templates for template matching"""
    templates = {}
    templates_dir = "templates/digits"
    
    if not os.path.exists(templates_dir):
        return {}
    
    for digit in range(16):  # Only 0-15 for common elixir values
        template_path = os.path.join(templates_dir, f"{digit}.png")
        if os.path.exists(template_path):
            template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
            if template is not None:
                _, template_thresh = cv2.threshold(template, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                if np.mean(template_thresh) < 127:
                    template_thresh = cv2.bitwise_not(template_thresh)
                templates[digit] = template_thresh
    
    return templates

digit_templates = load_digit_templates()


# 🔹 Funcions ADB
def adb_screenshot():
    result = subprocess.run([ADB_PATH, "exec-out", "screencap", "-p"], stdout=subprocess.PIPE)
    img = cv2.imdecode(np.frombuffer(result.stdout, np.uint8), cv2.IMREAD_COLOR)
    return img

def adb_tap(x, y):
    subprocess.run([ADB_PATH, "shell", "input", "tap", str(x), str(y)])

def find_template(screen, template_path, threshold=THRESHOLD):
    if not os.path.exists(template_path):
        return None
    template = cv2.imread(template_path, cv2.IMREAD_COLOR)
    res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(res)
    if max_val >= threshold:
        h, w = template.shape[:2]
        return max_loc[0]+w//2, max_loc[1]+h//2
    return None

def save_composition():
    chosen_units = [os.path.splitext(unit_files[i])[0] for i, sel in enumerate(selected) if sel]
    data = {"name": "Custom Deck", "units": chosen_units}
    with open(COMPOSITION_FILE, "w") as f:
        json.dump(data, f, indent=4)
    print(f"[COMP] Composicio confirmada: {chosen_units}")
    return chosen_units

# 🔹 Detectar unitats a pantalla - OPTIMIZED
def find_units_on_screen(screen, templates, threshold=THRESHOLD, min_dist=40):  # Reduced min_dist for faster processing
    detected = []
    for i, template in enumerate(templates):
        res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        loc = np.where(res >= threshold)
        h, w = template.shape[:2]
        centers = [(pt[0]+w//2, pt[1]+h//2) for pt in zip(*loc[::-1])]
        final_centers = []
        for c in centers:
            if all(np.hypot(c[0]-fc[0], c[1]-fc[1]) > min_dist for fc in final_centers):
                final_centers.append(c)
        detected.extend([(i, c) for c in final_centers])
    return detected

# 🔹 Saber posició d'una unitat - CACHED
_position_cache = {}
def get_unit_position(center):
    cache_key = f"{center[0]}_{center[1]}"
    if cache_key in _position_cache:
        return _position_cache[cache_key]
    
    x, y = center
    for cell in grid_cells:
        x0, y0, x1, y1 = cell["rect"]
        if x0 <= x <= x1 and y0 <= y <= y1:
            _position_cache[cache_key] = cell["name"]
            return cell["name"]
    for cell in bench_cells:
        x0, y0, x1, y1 = cell["rect"]
        if x0 <= x <= x1 and y0 <= y <= y1:
            _position_cache[cache_key] = cell["name"]
            return cell["name"]
    _position_cache[cache_key] = "desconegut"
    return "desconegut"

# 🔹 IMPROVED elixir reading - more robust but still optimized
_elixir_cache = {"value": None, "timestamp": 0}
ELIXIR_CACHE_DURATION = 1.0  # Reduced cache duration for better accuracy

def read_elixir(screen):
    global digit_templates
    
    current_time = time.time()
    
    if (_elixir_cache["value"] is not None and 
        current_time - _elixir_cache["timestamp"] < ELIXIR_CACHE_DURATION):
        return _elixir_cache["value"]
    
    x0, y0, x1, y1 = elixir_rect
    roi = screen[y0:y1, x0:x1]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    
    _, thresh_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    _, thresh_adaptive = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
    
    # Try with inverted image too
    thresh_otsu_inv = cv2.bitwise_not(thresh_otsu)
    
    processed_images = [thresh_otsu, thresh_adaptive, thresh_otsu_inv]
    
    if digit_templates:
        for processed_img in processed_images:
            for number in range(10, 16):
                if number in digit_templates:
                    res = cv2.matchTemplate(processed_img, digit_templates[number], cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, _ = cv2.minMaxLoc(res)
                    if max_val >= 0.8:  # Restored higher threshold for accuracy
                        _elixir_cache["value"] = number
                        _elixir_cache["timestamp"] = current_time
                        return number
        
        for processed_img in processed_images:
            detected_digits = []
            for digit in range(10):
                if digit in digit_templates:
                    res = cv2.matchTemplate(processed_img, digit_templates[digit], cv2.TM_CCOEFF_NORMED)
                    locations = np.where(res >= 0.75)  # Increased threshold for better accuracy
                    h, w = digit_templates[digit].shape[:2]
                    for pt in zip(*locations[::-1]):
                        confidence = res[pt[1], pt[0]]
                        detected_digits.append((pt[0], pt[1], digit, confidence, w))
            
            if detected_digits:
                # Remove overlapping detections
                detected_digits.sort(key=lambda x: x[3], reverse=True)  # Sort by confidence
                final_digits = []
                for digit_info in detected_digits:
                    x, y, digit, conf, w = digit_info
                    # Check if this digit overlaps with any already selected
                    overlap = False
                    for fx, fy, _, _, fw in final_digits:
                        if abs(x - fx) < max(w, fw) * 0.5:  # 50% overlap threshold
                            overlap = True
                            break
                    if not overlap:
                        final_digits.append(digit_info)
                
                if final_digits:
                    final_digits.sort(key=lambda x: x[0])  # Sort by x position
                    elixir_str = ''.join([str(digit) for _, _, digit, _, _ in final_digits[:2]])  # Max 2 digits
                    if elixir_str and len(elixir_str) <= 2:
                        try:
                            value = int(elixir_str)
                            if 0 <= value <= 15:  # Reasonable elixir range
                                _elixir_cache["value"] = value
                                _elixir_cache["timestamp"] = current_time
                                return value
                        except ValueError:
                            continue
    
    for processed_img in processed_images:
        try:
            config = r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789'
            text = pytesseract.image_to_string(processed_img, config=config)
            digits_only = ''.join(filter(str.isdigit, text.strip()))
            if digits_only and len(digits_only) <= 2:
                value = int(digits_only)
                if 0 <= value <= 15:
                    _elixir_cache["value"] = value
                    _elixir_cache["timestamp"] = current_time
                    return value
        except:
            continue
    
    try:
        config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789'
        text = pytesseract.image_to_string(gray, config=config)
        digits_only = ''.join(filter(str.isdigit, text.strip()))
        if digits_only and len(digits_only) <= 2:
            value = int(digits_only)
            if 0 <= value <= 15:
                _elixir_cache["value"] = value
                _elixir_cache["timestamp"] = current_time
                return value
    except:
        pass
    
    # Return cached value if available, otherwise return 0 as fallback
    return _elixir_cache.get("value", 0)

# 🔹 ULTRA-OPTIMIZED deploy function
def deploy_units(screen, COMPO, elixir_amount):
    print("[DEPLOY] Starting optimized deploy...")

    if is_bench_empty(screen):
        cleanup_bench_units(screen, COMPO)
    else:
        logger.info("[DEPLOY] Bench is already empty, skipping cleanup.")    
    
    relevant_templates = []
    relevant_names = []
    
    # Only shop templates for composition units + cheap units
    for i, unit_file in enumerate(unit_files):
        unit_name = os.path.splitext(unit_file)[0]
        unit_cost = unit_costs.get(unit_name, 0)
        if unit_name in COMPO or unit_cost <= min(3, elixir_amount):  # More selective
            relevant_templates.append(unit_imgs[i])
            relevant_names.append(('shop', unit_name))
    
    # Always add field/bench for optimization
    relevant_templates.extend(field_imgs)
    relevant_templates.extend(bench_imgs)
    relevant_names.extend([('field', os.path.splitext(f)[0]) for f in field_files])
    relevant_names.extend([('bench', os.path.splitext(f)[0]) for f in bench_files])
    
    all_detections = find_units_on_screen(screen, relevant_templates, threshold=0.8, min_dist=30)
    
    field_units = []
    bench_units = []
    available_cards = []
    
    for i, center in all_detections:
        pos_name = get_unit_position(center)
        template_type, unit_name = relevant_names[i]
        
        if template_type == 'shop':
            cost = unit_costs.get(unit_name, 0)
            if cost <= elixir_amount:
                available_cards.append((unit_name, cost, center))
        elif template_type == 'field' and pos_name.startswith("camp"):
            field_units.append((i, center, unit_name, pos_name))
        elif template_type == 'bench' and pos_name.startswith("banquillo"):
            bench_units.append((i, center, unit_name, pos_name))
    
    print(f"[SUMMARY] Field:{len(field_units)} Bench:{len(bench_units)} Shop:{len(available_cards)} Elixir:{elixir_amount}")

    purchases_made = 0
    max_purchases = min(4, elixir_amount // 2)  # Reduced max purchases
    
    # Priority: composition cards first
    available_compo_cards = [card for card in available_cards if card[0] in COMPO]
    
    for _ in range(max_purchases):
        purchased = False
        
        # Buy composition cards
        if available_compo_cards:
            affordable_compo = [card for card in available_compo_cards if card[1] <= elixir_amount]
            if affordable_compo:
                most_expensive_compo = max(affordable_compo, key=lambda x: x[1])
                unit_name, cost, center = most_expensive_compo
                
                print(f"[BUY] {unit_name} (cost: {cost})")
                adb_tap(*center)
                purchases_made += 1
                elixir_amount -= cost
                available_compo_cards.remove(most_expensive_compo)
                purchased = True
                time.sleep(0.3)
                screen = adb_screenshot()
                # Always add field/bench for optimization
                relevant_templates.extend(field_imgs)
                relevant_templates.extend(bench_imgs)
                relevant_names.extend([('field', os.path.splitext(f)[0]) for f in field_files])
                relevant_names.extend([('bench', os.path.splitext(f)[0]) for f in bench_files])
                
                all_detections = find_units_on_screen(screen, relevant_templates, threshold=0.8, min_dist=30)
                
                field_units = []
                bench_units = []
                available_cards = []
                
                for i, center in all_detections:
                    pos_name = get_unit_position(center)
                    template_type, unit_name = relevant_names[i]
                    
                    if template_type == 'shop':
                        cost = unit_costs.get(unit_name, 0)
                        if cost <= elixir_amount:
                            available_cards.append((unit_name, cost, center))
                    elif template_type == 'field' and pos_name.startswith("camp"):
                        field_units.append((i, center, unit_name, pos_name))
                    elif template_type == 'bench' and pos_name.startswith("banquillo"):
                        bench_units.append((i, center, unit_name, pos_name))
                
                print(f"[SUMMARY] Field:{len(field_units)} Bench:{len(bench_units)} Shop:{len(available_cards)} Elixir:{elixir_amount}")
        
        # Buy any valuable card if high elixir
        elif elixir_amount >= 6:  # Only if we have plenty of elixir
            affordable_cards = [card for card in available_cards if card[1] <= elixir_amount]
            if affordable_cards:
                most_expensive = max(affordable_cards, key=lambda x: x[1])
                unit_name, cost, center = most_expensive
                
                print(f"[BUY] High elixir: {unit_name} (cost: {cost})")
                adb_tap(*center)
                purchases_made += 1
                elixir_amount -= cost
                purchased = True
                available_cards.remove(most_expensive)
                time.sleep(0.3)  # Reduced delay
        
        if not purchased:
            break
    
    if purchases_made > 0:
        time.sleep(0.5)  # Let units settle
        optimize_unit_positions(screen, COMPO)
    
    print(f"[SUCCESS] {purchases_made} purchases completed")
    return elixir_amount

# 🔹 SIMPLIFIED optimization function
def optimize_unit_positions(screen, COMPO):
    """Quick optimization - sell non-composition units if composition units on bench"""
    
    templates = field_imgs + bench_imgs
    names = [('field', os.path.splitext(f)[0]) for f in field_files] + [('bench', os.path.splitext(f)[0]) for f in bench_files]
    
    detections = find_units_on_screen(screen, templates, threshold=0.8, min_dist=30)
    
    field_units = []
    bench_units = []
    
    for i, center in detections:
        pos_name = get_unit_position(center)
        template_type, unit_name = names[i]
        
        if template_type == 'field' and pos_name.startswith("camp"):
            field_units.append((unit_name, center))
        elif template_type == 'bench' and pos_name.startswith("banquillo"):
            bench_units.append((unit_name, center))
    
    # Find composition units on bench and non-composition on field
    compo_bench = [unit for unit in bench_units if unit[0] in COMPO]
    non_compo_field = [unit for unit in field_units if unit[0] not in COMPO]
    
    if compo_bench and non_compo_field:
        # Sell cheapest non-composition field unit
        cheapest_field = min(non_compo_field, key=lambda x: unit_costs.get(x[0], 0))
        unit_name, center = cheapest_field
        
        print(f"[OPTIMIZE] Selling {unit_name}")
        adb_tap(*center)
        time.sleep(0.5)  # Minimal delay
        
        screen = adb_screenshot()
        sell_pos = find_template(screen, SELL_BUTTON)
        if sell_pos:
            adb_tap(*sell_pos)
            time.sleep(0.5)
            screen = adb_screenshot()
            return True
    
    return False

# 🔹 NOVA FUNCIO: Netejar unitats del banquillo que no són de la composició
def cleanup_bench_units(screen, COMPO):
    """Elimina unitats del banquillo que no són de la composició actual"""
    print("[CLEANUP] Checking bench for non-composition units...")
    
    # Detectar només unitats del banquillo
    bench_detections = find_units_on_screen(screen, bench_imgs, threshold=0.8, min_dist=30)
    
    bench_units = []
    for i, center in bench_detections:
        pos_name = get_unit_position(center)
        if pos_name.startswith("banquillo"):
            unit_name = os.path.splitext(bench_files[i])[0]
            bench_units.append((unit_name, center))
    
    # Trobar unitats que no són de la composició
    non_compo_bench = [unit for unit in bench_units if unit[0] not in COMPO]
    
    if not non_compo_bench:
        print("[CLEANUP] No non-composition units found on bench")
        return False
    
    print(f"[CLEANUP] Found {len(non_compo_bench)} non-composition units on bench: {[u[0] for u in non_compo_bench]}")
    
    # Vendre les unitats que no són de la composició
    units_sold = 0
    for unit_name, center in non_compo_bench:
        print(f"[CLEANUP] Selling {unit_name} from bench")
        adb_tap(*center)
        time.sleep(0.3)  # Esperar que aparegui el botó de venda
        
        # Buscar i clicar el botó de venda
        current_screen = adb_screenshot()
        sell_pos = find_template(current_screen, SELL_BUTTON)
        if sell_pos:
            adb_tap(*sell_pos)
            units_sold += 1
            time.sleep(0.3)  # Esperar que es completi la venda
        else:
            print(f"[CLEANUP] Could not find sell button for {unit_name}")
    
    if units_sold > 0:
        print(f"[CLEANUP] Successfully sold {units_sold} non-composition units")
        time.sleep(0.5)  # Esperar que es completi tot
    
    return units_sold > 0

def is_bench_empty(screen):
    """Detecta si el banquillo està completament buit"""
    if not os.path.exists(EMPTY_BENCH):
        return False  # Si no tenim template, assumim que no està buit
    
    # Agafar la regió del banquillo complet
    bench_region_x0 = min(cell["rect"][0] for cell in bench_cells)
    bench_region_y0 = min(cell["rect"][1] for cell in bench_cells)
    bench_region_x1 = max(cell["rect"][2] for cell in bench_cells)
    bench_region_y1 = max(cell["rect"][3] for cell in bench_cells)
    
    bench_roi = screen[bench_region_y0:bench_region_y1, bench_region_x0:bench_region_x1]
    
    # Comparar amb el template del banquillo buit
    empty_template = cv2.imread(EMPTY_BENCH)
    if empty_template is None:
        return False
    
    # Redimensionar template si cal
    if bench_roi.shape[:2] != empty_template.shape[:2]:
        empty_template = cv2.resize(empty_template, (bench_roi.shape[1], bench_roi.shape[0]))
    
    # Template matching
    res = cv2.matchTemplate(bench_roi, empty_template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(res)
    
    # Si la similitud és alta, el banquillo està buit
    return max_val >= 0.85

# 🔹 OPTIMIZED bot loop
def bot_loop():
    global bot_running
    COMPO = []
    elixir_amount = 0
    last_elixir_read = 0
    iteration_count = 0
    
    print("[BOT] Optimized bot loop started")
    
    while True:
        if bot_running:
            iteration_count += 1
            
            if not COMPO:
                if os.path.exists(COMPOSITION_FILE):
                    with open(COMPOSITION_FILE, "r") as f:
                        data = json.load(f)
                        COMPO = [os.path.splitext(u)[0] for u in data.get("units",[])]
                        print(f"[COMP] Loaded: {COMPO}")
                else:
                    print("[ERROR] No composition file")
                    bot_running = False
                    continue
            
            try:
                time.sleep(0.5)
                screen = adb_screenshot()
                current_time = time.time()
            except Exception as e:
                print(f"[ERROR] Screenshot: {e}")
                time.sleep(0.2)  # Reduced error delay
                continue

            reward_pos = find_template(screen, REWARD)
            if reward_pos:
                print("[ACTION] Reward")
                adb_tap(*reward_pos)
                time.sleep(0.2)  # Reduced delay
                continue
            
            init_pos = find_template(screen, INIT_BATTLE)
            if init_pos:
                print("[ACTION] Battle")
                adb_tap(*init_pos)
                time.sleep(0.1)  # Reduced delay
                continue

            play_again = find_template(screen, PLAY_AGAIN_BATTLE)
            if play_again:
                print("[ACTION] Play again")
                adb_tap(*play_again)
                time.sleep(0.1)  # Reduced delay
                continue

            quit_pos = find_template(screen, QUIT)
            if quit_pos:
                print("[ACTION] Quit")
                adb_tap(*quit_pos)
                time.sleep(0.1)  # Reduced delay
                continue

            deploy = find_template(screen, PHASE_DEPLOY)
            if deploy:
                print("[PHASE] Deploy")
                if current_time - last_elixir_read > 1.5:
                    elixir_value = read_elixir(screen)
                    if elixir_value is not None:
                        elixir_amount = elixir_value
                    last_elixir_read = current_time
                
                elixir_amount = deploy_units(screen, COMPO, elixir_amount)
                time.sleep(0.2)  # Reduced delay
                continue

            battle_phase = find_template(screen, PHASE_BATTLE)
            if battle_phase:
                print("[PHASE] Battle - waiting")
                time.sleep(0.5)  # Longer wait during battle
                continue

            time.sleep(0.1)
        else:
            time.sleep(0.1)

# 🔹 GUI OpenCV
IMG_SIZE = (100,100)
MARGIN = 10
COLS = 5

def draw_units():
    rows = (len(unit_imgs)-1)//COLS + 1
    canvas_h = rows*(IMG_SIZE[1]+MARGIN)+MARGIN + 70
    canvas_w = max(COLS*(IMG_SIZE[0]+MARGIN)+MARGIN, 370)
    canvas = np.ones((canvas_h, canvas_w,3), dtype=np.uint8)*255
    for idx, img in enumerate(unit_imgs):
        row = idx//COLS
        col = idx%COLS
        x = col*(IMG_SIZE[0]+MARGIN)+MARGIN
        y = row*(IMG_SIZE[1]+MARGIN)+MARGIN+70
        thumb = cv2.resize(img, IMG_SIZE)
        canvas[y:y+IMG_SIZE[1], x:x+IMG_SIZE[0]] = thumb
        if selected[idx]:
            cv2.rectangle(canvas, (x,y), (x+IMG_SIZE[0], y+IMG_SIZE[1]), (0,255,0),3)
        # Mostrar cost
        unit_name = os.path.splitext(unit_files[idx])[0]
        cost = unit_costs.get(unit_name, "?")
        cv2.putText(canvas, str(cost), (x+5, y+20), cv2.QT_FONT_NORMAL, 0.6, (0,0,0),2)
    # Botons
    for name, (x0,y0,x1,y1) in BUTTONS.items():
        color = (0,200,0) if (bot_running and name=="start") else (0,0,255) if (not bot_running and name=="stop") else (150,150,150)
        cv2.rectangle(canvas, (x0,y0), (x1,y1), color, -1)
        cv2.putText(canvas, name.capitalize(), (x0+5, y0+30), cv2.QT_FONT_NORMAL, 0.8, (255,255,255),2)
    return canvas

def click_event(event, x, y, flags, param):
    global bot_running
    if event != cv2.EVENT_LBUTTONDOWN:
        return
    # Miniatures
    for idx in range(len(unit_imgs)):
        row = idx//COLS
        col = idx%COLS
        x0 = col*(IMG_SIZE[0]+MARGIN)+MARGIN
        y0 = row*(IMG_SIZE[1]+MARGIN)+MARGIN+70
        x1 = x0+IMG_SIZE[0]
        y1 = y0+IMG_SIZE[1]
        if x0 <= x <= x1 and y0 <= y <= y1:
            selected[idx] = not selected[idx]
            return
    # Botons
    for name, (x0,y0,x1,y1) in BUTTONS.items():
        if x0 <= x <= x1 and y0 <= y <= y1:
            if name == "start":
                bot_running = True
                print("[BOT] Bot started - OPTIMIZED")
            elif name == "stop":
                bot_running = False
                print("[BOT] Bot stopped")
            elif name == "confirm":
                save_composition()

# 🔹 Inici
cv2.namedWindow("Unit Selector")
cv2.setMouseCallback("Unit Selector", click_event)
threading.Thread(target=bot_loop, daemon=True).start()

while True:
    canvas = draw_units()
    cv2.imshow("Unit Selector", canvas)
    key = cv2.waitKey(20) & 0xFF
    if key == 27:  # ESC surt
        break

cv2.destroyAllWindows()

