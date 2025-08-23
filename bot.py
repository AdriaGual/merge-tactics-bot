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
UNITS_DIR = "templates/units"       # cartes que es poden comprar
FIELDS_DIR = "templates/field"      # unitats al camp
GRID_FILE = "grid_positions.json"
COMPOSITION_FILE = "composition.json"
ELIXIR_FILE = "elixir.json"
ADB_PATH = "adb"
THRESHOLD = 0.7

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

# 🔹 Carregar unitats i costos
unit_files = [f for f in os.listdir(UNITS_DIR) if f.endswith(".png")]
unit_imgs = [cv2.imread(os.path.join(UNITS_DIR, f)) for f in unit_files]
selected = [False]*len(unit_imgs)

field_files = [f for f in os.listdir(FIELDS_DIR) if f.endswith(".png")]
field_imgs = [cv2.imread(os.path.join(FIELDS_DIR, f)) for f in field_files]

# Assigna el cost manualment aquí
unit_costs = {
    "archer_queen": 5,
    "archer": 2,
    "bandit": 4,
    "barbarian": 2,
    "bomber": 2,
    "dart_goblin": 3,
    "executioner": 3,
    "giant_skeleton": 3,
    "goblin_machine": 4,
    "goblin": 2,
    "golden_knight": 5,
    "knight": 2,
    "mega_knight": 4,
    "pekka": 3,
    "prince": 3,
    "princess": 4,
    "royal_ghost": 4,
    "skeleton_king": 5,
    "spear_goblin": 2,
    "valkyrie": 3,   
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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot_debug.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def profile_time(func_name):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            end_time = time.time()
            duration = end_time - start_time
            logger.info(f"[TIME] {func_name}: {duration:.3f}s")
            return result
        return wrapper
    return decorator

DEBUG_MODE = True
DEBUG_SAVE_IMAGES = True

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
    logger.info(f"[COMP] Composicio confirmada: {chosen_units}")
    return chosen_units

# 🔹 Detectar unitats a pantalla
def find_units_on_screen(screen, templates, threshold=THRESHOLD, min_dist=50):
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

# 🔹 Saber posició d’una unitat
def get_unit_position(center):
    x, y = center
    for cell in grid_cells:
        x0, y0, x1, y1 = cell["rect"]
        if x0 <= x <= x1 and y0 <= y <= y1:
            return cell["name"]
    for cell in bench_cells:
        x0, y0, x1, y1 = cell["rect"]
        if x0 <= x <= x1 and y0 <= y <= y1:
            return cell["name"]
    return "desconegut"

# 🔹 Llegir elixir amb template matching
_elixir_cache = {"value": None, "timestamp": 0}
ELIXIR_CACHE_DURATION = 0.5  # Cache elixir reading for 0.5 seconds

def load_digit_templates():
    """Load digit templates for template matching"""
    templates = {}
    templates_dir = "templates/digits"
    
    # Create templates directory if it doesn't exist
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
        logger.info(f"[SETUP] Created directory: {templates_dir}")
        logger.info("[INFO] Add digit templates to improve detection")
        logger.info("[INFO] Run: python create_digit_templates.py")
        return {}
    
    # Load single digit templates (0-9)
    for digit in range(10):
        template_path = os.path.join(templates_dir, f"{digit}.png")
        if os.path.exists(template_path):
            template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
            if template is not None:
                # Try multiple preprocessing methods for templates too
                _, template_thresh = cv2.threshold(template, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                if np.mean(template_thresh) < 127:
                    template_thresh = cv2.bitwise_not(template_thresh)
                templates[digit] = template_thresh
                logger.debug(f"[TEMPLATE] Loaded digit {digit} template: {template.shape}")
            else:
                logger.warning(f"[ERROR] Could not load template: {template_path}")
                templates[digit] = None
        else:
            templates[digit] = None
    
    # Load multi-digit number templates (10, 11, 12, etc.)
    for file in os.listdir(templates_dir):
        if file.endswith('.png'):
            number_str = file[:-4]  # Remove .png extension
            try:
                number = int(number_str)
                if number >= 10:  # Multi-digit numbers
                    template_path = os.path.join(templates_dir, file)
                    template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
                    if template is not None:
                        _, template_thresh = cv2.threshold(template, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                        if np.mean(template_thresh) < 127:
                            template_thresh = cv2.bitwise_not(template_thresh)
                        templates[number] = template_thresh
                        logger.debug(f"[TEMPLATE] Loaded multi-digit {number} template: {template.shape}")
                    else:
                        logger.warning(f"[ERROR] Could not load template: {template_path}")
            except ValueError:
                continue  # Skip non-numeric filenames
    
    loaded_count = sum(1 for t in templates.values() if t is not None)
    if loaded_count > 0:
        logger.info(f"[SUCCESS] Loaded {loaded_count} templates (single + multi-digit)")
        multi_digit_count = sum(1 for k, t in templates.items() if isinstance(k, int) and k >= 10 and t is not None)
        if multi_digit_count > 0:
            logger.info(f"[SUCCESS] Including {multi_digit_count} multi-digit templates")
    else:
        logger.warning("[WARNING] No digit templates found. Using OCR as primary method.")
        logger.info("[HELP] Run: python create_digit_templates.py")
    
    return templates

@profile_time("read_elixir")
def read_elixir(screen):
    current_time = time.time()
    
    if (_elixir_cache["value"] is not None and 
        current_time - _elixir_cache["timestamp"] < ELIXIR_CACHE_DURATION):
        logger.debug(f"[CACHE] Using cached elixir: {_elixir_cache['value']}")
        return _elixir_cache["value"]
    
    x0, y0, x1, y1 = elixir_rect
    roi = screen[y0:y1, x0:x1]
    
    if DEBUG_SAVE_IMAGES:
        debug_dir = "debug_images"
        if not os.path.exists(debug_dir):
            os.makedirs(debug_dir)
        cv2.imwrite(f"{debug_dir}/elixir_roi_original.png", roi)
        logger.info(f"[DEBUG] Saved original elixir ROI to debug_images/elixir_roi_original.png")
    
    # Try multiple preprocessing methods
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    logger.debug(f"[DEBUG] Elixir ROI size: {roi.shape}, mean brightness: {np.mean(gray):.1f}")
    
    # Method 1: Simple threshold
    _, thresh1 = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
    
    # Method 2: OTSU threshold
    _, thresh2 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Method 3: Adaptive threshold
    thresh3 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    
    # Method 4: Inverted OTSU (for dark text on light background)
    _, thresh4 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Method 5: Enhanced contrast + threshold
    enhanced = cv2.equalizeHist(gray)
    _, thresh5 = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    preprocessing_methods = [
        ("simple", thresh1),
        ("otsu", thresh2), 
        ("adaptive", thresh3),
        ("inverted_otsu", thresh4),
        ("enhanced", thresh5)
    ]
    
    if DEBUG_SAVE_IMAGES:
        for name, processed in preprocessing_methods:
            cv2.imwrite(f"{debug_dir}/elixir_{name}.png", processed)
        logger.info("[DEBUG] Saved all preprocessing methods to debug_images/")
    
    digit_templates = load_digit_templates()
    best_template_result = None
    best_confidence = 0
    
    if digit_templates and any(t is not None for t in digit_templates.values()):
        logger.debug("[TEMPLATE] Trying template matching with multiple preprocessing methods...")
        
        for method_name, processed_img in preprocessing_methods:
            logger.debug(f"[TEMPLATE] Testing method: {method_name}")
            
            # First try multi-digit templates (10, 11, 12, etc.)
            multi_digit_matches = []
            for number, template in digit_templates.items():
                if isinstance(number, int) and number >= 10 and template is not None:
                    res = cv2.matchTemplate(processed_img, template, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, max_loc = cv2.minMaxLoc(res)
                    
                    logger.debug(f"    Multi-digit {number}: max confidence = {max_val:.3f}")
                    
                    if max_val >= 0.7:  # Higher threshold for multi-digit
                        multi_digit_matches.append((number, max_val))
            
            # If we found a good multi-digit match, use it
            if multi_digit_matches:
                best_multi = max(multi_digit_matches, key=lambda x: x[1])
                number, confidence = best_multi
                if confidence > best_confidence:
                    best_template_result = number
                    best_confidence = confidence
                    logger.info(f"[TEMPLATE] Multi-digit match: {number} (method: {method_name}, conf: {confidence:.3f})")
                continue  # Skip individual digit detection for this method
            
            # If no multi-digit match, try individual digits
            detected_digits = []
            for digit, template in digit_templates.items():
                if isinstance(digit, int) and digit < 10 and template is not None:
                    res = cv2.matchTemplate(processed_img, template, cv2.TM_CCOEFF_NORMED)
                    locations = np.where(res >= 0.6)  # Lowered threshold from 0.75 to 0.6
                    max_val = np.max(res) if res.size > 0 else 0
                    
                    logger.debug(f"    Digit {digit}: max confidence = {max_val:.3f}")
                    
                    h, w = template.shape[:2]
                    for pt in zip(*locations[::-1]):
                        confidence = res[pt[1], pt[0]]
                        detected_digits.append((pt[0], pt[1], digit, confidence, w))
            
            if detected_digits:
                # Filter overlapping detections
                detected_digits.sort(key=lambda x: x[3], reverse=True)
                filtered_digits = []
                
                for current in detected_digits:
                    x, y, digit, conf, width = current
                    overlap = any(abs(x - ax) < width * 0.6 and abs(y - ay) < 8 
                                for ax, ay, _, _, _ in filtered_digits)
                    if not overlap:
                        filtered_digits.append(current)
                
                if filtered_digits:
                    filtered_digits.sort(key=lambda x: x[0])
                    elixir_str = ''.join([str(digit) for _, _, digit, _, _ in filtered_digits])
                    avg_confidence = sum(d[3] for d in filtered_digits) / len(filtered_digits)
                    
                    logger.debug(f"[TEMPLATE] Method {method_name}: '{elixir_str}' (avg conf: {avg_confidence:.3f})")
                    
                    if elixir_str and len(elixir_str) <= 3 and avg_confidence > best_confidence:
                        try:
                            value = int(elixir_str)
                            if 0 <= value <= 999:
                                best_template_result = value
                                best_confidence = avg_confidence
                                logger.info(f"[TEMPLATE] Best result so far: {value} (method: {method_name}, conf: {avg_confidence:.3f})")
                        except ValueError:
                            pass

    # Try OCR with each preprocessing method
    best_ocr_result = None
    best_ocr_confidence = 0
    
    logger.debug("[OCR] Trying OCR with multiple preprocessing methods...")
    ocr_configs = [
        ('basic', r'--oem 3 --psm 8 -c tessedit_char_whitelist=0123456789'),
        ('single_char', r'--oem 3 --psm 10 -c tessedit_char_whitelist=0123456789'),
        ('digits_only', r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789'),
    ]
    
    for method_name, processed_img in preprocessing_methods:
        for config_name, config in ocr_configs:
            try:
                text = pytesseract.image_to_string(processed_img, config=config)
                digits_only = ''.join(filter(str.isdigit, text.strip()))
                
                logger.debug(f"[OCR] {method_name}+{config_name}: '{text.strip()}' -> '{digits_only}'")
                
                if digits_only and len(digits_only) <= 3:
                    try:
                        value = int(digits_only)
                        if 0 <= value <= 999:
                            # Simple confidence based on text clarity
                            confidence = len(digits_only) / 3.0  # Prefer longer numbers
                            if confidence > best_ocr_confidence:
                                best_ocr_result = value
                                best_ocr_confidence = confidence
                                logger.info(f"[OCR] Best result so far: {value} ({method_name}+{config_name})")
                    except ValueError:
                        pass
            except Exception as e:
                logger.debug(f"[OCR] Error with {method_name}+{config_name}: {e}")
    
    # Determine final result
    final_result = None
    if best_template_result is not None and best_ocr_result is not None:
        if best_template_result == best_ocr_result:
            final_result = best_template_result
            logger.info(f"[SUCCESS] Both methods agree: {final_result}")
        elif best_confidence > THRESHOLD:  # High confidence template matching
            final_result = best_template_result
            logger.info(f"[SUCCESS] High confidence template: {final_result} (conf: {best_confidence:.3f})")
        else:
            final_result = best_template_result  # Still prefer template matching
            logger.warning(f"[CONFLICT] Template: {best_template_result} (conf: {best_confidence:.3f}), OCR: {best_ocr_result}, using template")
    elif best_template_result is not None:
        final_result = best_template_result
        logger.info(f"[SUCCESS] Template only: {final_result} (conf: {best_confidence:.3f})")
    elif best_ocr_result is not None:
        final_result = best_ocr_result
        logger.info(f"[SUCCESS] OCR only: {final_result}")
    else:
        logger.error("[ERROR] Both methods failed completely")
        logger.error("[HELP] Check debug_images/ folder to see what the elixir region looks like")
        logger.error("[HELP] Run: python create_digit_templates.py to create proper digit templates")
        final_result = _elixir_cache.get("value")  # Use cached value
        if final_result:
            logger.info(f"[CACHE] Using cached value: {final_result}")
    
    if final_result is not None:
        _elixir_cache["value"] = final_result
        _elixir_cache["timestamp"] = current_time
    
    return final_result

# 🔹 Funció intel·ligent de deploy (OPTIMITZADA I MÉS AGRESSIVA)
@profile_time("deploy_units")
def deploy_units(screen, COMPO, elixir_amount):
    logger.info("[DEPLOY] Starting deploy phase detection...")
    
    if DEBUG_SAVE_IMAGES:
        debug_dir = "debug_images"
        if not os.path.exists(debug_dir):
            os.makedirs(debug_dir)
        cv2.imwrite(f"{debug_dir}/deploy_screen.png", screen)
    
    # Detect all units on screen once (both field and available for purchase)
    start_time = time.time()
    all_detected_units = find_units_on_screen(screen, unit_imgs, threshold=THRESHOLD, min_dist=30)
    units_detection_time = time.time() - start_time
    logger.info(f"[TIME] Units detection: {units_detection_time:.3f}s")
    
    start_time = time.time()
    all_detected_fields = find_units_on_screen(screen, field_imgs, threshold=THRESHOLD, min_dist=30)
    fields_detection_time = time.time() - start_time
    logger.info(f"[TIME] Fields detection: {fields_detection_time:.3f}s")
    
    field_units = []
    bench_units = []
    available_cards = []
    
    for i, center in all_detected_units:
        pos_name = get_unit_position(center)
        unit_name = os.path.splitext(unit_files[i])[0]
        
        logger.debug(f"[UNIT] {unit_name} at {center} -> {pos_name}")
        
        if pos_name.startswith("camp"):
            field_units.append((i, center, unit_name, pos_name))
        elif pos_name.startswith("banquillo"):
            bench_units.append((i, center, unit_name, pos_name))
        elif pos_name == "desconegut":  # Available for purchase
            cost = unit_costs.get(unit_name, 0)
            if cost <= elixir_amount:
                available_cards.append((unit_name, cost, center))
                logger.debug(f"[SHOP] Available: {unit_name} (cost: {cost})")
    
    # Add field units detected with field templates
    for i, center in all_detected_fields:
        pos_name = get_unit_position(center)
        if pos_name.startswith("camp"):
            unit_name = os.path.splitext(field_files[i])[0]
            field_units.append((i, center, unit_name, pos_name))
            logger.debug(f"[FIELD] Field unit: {unit_name} at {pos_name}")
    
    logger.info(f"[SUMMARY] Detection summary:")
    logger.info(f"   [FIELD] Field units: {len(field_units)}")
    for field_unit in field_units:
        logger.info(f"  [FIELD] - {field_unit[2]} at {field_unit[3]}") 
    logger.info(f"   [BENCH] Bench units: {len(bench_units)}")
    logger.info(f"   [SHOP] Available cards: {len(available_cards)}")
    logger.info(f"   [ELIXIR] Current elixir: {elixir_amount}")

    available_compo_cards = [card for card in available_cards if card[0] in COMPO]
    available_non_compo_cards = [card for card in available_cards if card[0] not in COMPO]
    
    non_compo_field_units = [unit for unit in field_units if unit[2] not in COMPO]
    
    logger.info(f"[SHOP] Available composition cards: {[f'{name}({cost})' for name, cost, _ in available_compo_cards]}")
    logger.info(f"[SHOP] Available non-composition cards: {[f'{name}({cost})' for name, cost, _ in available_non_compo_cards]}")
    logger.info(f"[FIELD] Non-composition field units: {[f'{unit[2]}@{unit[3]}' for unit in non_compo_field_units]}")
    
    buy_start_time = time.time()
    purchases_made = 0
    
    while elixir_amount >= 2 and available_cards and purchases_made < 3:  # Max 3 purchases per cycle
        purchased = False
        
        # Priority 1: Buy composition cards (most expensive first)
        if available_compo_cards:
            affordable_compo = [card for card in available_compo_cards if card[1] <= elixir_amount]
            if affordable_compo:
                most_expensive_compo = max(affordable_compo, key=lambda x: x[1])
                unit_name, cost, center = most_expensive_compo
                
                should_replace_field = False
                field_unit_to_replace = None

                if unit_name:
                    logger.info(f"[BUY] Buying composition card: {unit_name} (cost: {cost})")
                    adb_tap(*center)
                    elixir_amount -= cost
                    purchases_made += 1
                    purchased = True
                    
                    available_compo_cards.remove(most_expensive_compo)
                    available_cards.remove(most_expensive_compo)
                    time.sleep(0.2)
                
                if non_compo_field_units and purchased:
                    cheapest_field = min(non_compo_field_units, key=lambda x: unit_costs.get(x[2], 0))
                    field_unit_cost = unit_costs.get(cheapest_field[2], 0)
                    
                    if cost >= field_unit_cost:
                        should_replace_field = True
                        field_unit_to_replace = cheapest_field
                        logger.info(f"[REPLACE] Will replace {cheapest_field[2]} (cost: {field_unit_cost}) with {unit_name} (cost: {cost})")
                
                if should_replace_field and field_unit_to_replace:
                    _, field_center, field_unit_name, field_pos = field_unit_to_replace
                    logger.info(f"[SELLING] Selling field unit {field_unit_name} at {field_pos} for replacement")
                    adb_tap(*field_center)
                    time.sleep(0.5)
                    
                    current_screen = adb_screenshot()
                    sell_pos = find_template(current_screen, SELL_BUTTON)
                    if sell_pos:
                        adb_tap(*sell_pos)
                        time.sleep(0.3)
                        elixir_refund = max(unit_costs.get(field_unit_name, 0) - 1, 0)
                        elixir_amount += elixir_refund
                        logger.info(f"[SUCCESS] Sold {field_unit_name}, got {elixir_refund} elixir, total: {elixir_amount}")
                        
                        field_units.remove(field_unit_to_replace)
                        non_compo_field_units.remove(field_unit_to_replace)
                    else:
                        logger.error(f"[ERROR] Sell button not found for {field_unit_name}")
                        should_replace_field = False  # Don't buy if we couldn't sell
            
        
        # Priority 2: If elixir is high (>6), buy any available unit
        if not purchased and elixir_amount > 6 and available_cards:
            affordable_cards = [card for card in available_cards if card[1] <= elixir_amount]
            if affordable_cards:
                most_expensive = max(affordable_cards, key=lambda x: x[1])
                unit_name, cost, center = most_expensive
                
                logger.info(f"[BUY] High elixir ({elixir_amount}), buying any unit: {unit_name} (cost: {cost})")
                adb_tap(*center)
                elixir_amount -= cost
                purchases_made += 1
                purchased = True
                
                available_cards.remove(most_expensive)
                if most_expensive in available_non_compo_cards:
                    available_non_compo_cards.remove(most_expensive)
                time.sleep(0.2)  # Reduced delay
        
        # Priority 3: If elixir is medium (4-6), buy composition or cheap units
        if not purchased and 4 <= elixir_amount <= 6 and available_cards:
            affordable_cards = [card for card in available_cards if card[1] <= elixir_amount]
            if affordable_cards:
                affordable_cards.sort(key=lambda x: (x[0] not in COMPO, -x[1]))
                best_card = affordable_cards[0]
                unit_name, cost, center = best_card
                
                logger.info(f"[BUY] Medium elixir ({elixir_amount}), buying: {unit_name} (cost: {cost})")
                adb_tap(*center)
                elixir_amount -= cost
                purchases_made += 1
                purchased = True
                
                available_cards.remove(best_card)
                if best_card in available_compo_cards:
                    available_compo_cards.remove(best_card)
                elif best_card in available_non_compo_cards:
                    available_non_compo_cards.remove(best_card)
                time.sleep(0.2)  # Reduced delay
        
        if not purchased:
            break  # No more affordable cards
    
    buy_time = time.time() - buy_start_time
    if purchases_made > 0:
        logger.info(f"[SUCCESS] Made {purchases_made} purchases in {buy_time:.3f}s")
    
    if elixir_amount > 8:  # Only sell if elixir is still very high
        units_to_sell = []
        for i, center, unit_name, pos_name in field_units + bench_units:
            if unit_name not in COMPO:
                potential_elixir = elixir_amount + max(unit_costs.get(unit_name,0)-1,0)
                can_buy_expensive = any(unit_costs.get(u,0) <= potential_elixir for u in COMPO if unit_costs.get(u,0) >= 3)
                if can_buy_expensive and len(units_to_sell) < 2:  # Max 2 sells per cycle
                    units_to_sell.append((center, unit_name, pos_name))
                    logger.info(f"[SELL] Will sell {unit_name} at {pos_name} (high elixir: {elixir_amount})")
        
        sell_start_time = time.time()
        for center, unit_name, pos_name in units_to_sell:
            logger.info(f"[SELLING] Selling {unit_name} at {pos_name}")
            adb_tap(*center)
            time.sleep(0.5)  # Reduced delay from 1s to 0.5s
            
            current_screen = adb_screenshot()
            sell_pos = find_template(current_screen, SELL_BUTTON)
            if sell_pos:
                adb_tap(*sell_pos)
                time.sleep(0.2)  # Reduced delay from 0.3s to 0.2s
                elixir_amount += unit_costs.get(unit_name,0)-1
                logger.info(f"[SUCCESS] Sold {unit_name}, elixir now: {elixir_amount}")
            else:
                logger.error(f"[ERROR] Sell button not found for {unit_name}")
        
        sell_time = time.time() - sell_start_time
        if units_to_sell:
            logger.info(f"[TIME] Selling phase: {sell_time:.3f}s")
    else:
        logger.info(f"[SKIP] Skipping sell phase, elixir manageable: {elixir_amount}")

    logger.info(f"[FINAL] Final elixir after deploy: {elixir_amount}")
    
    return elixir_amount

# 🔹 Thread principal del bot
@profile_time("bot_loop_iteration")
def bot_loop():
    global bot_running
    COMPO = []
    elixir_amount = 0
    last_screen_time = 0
    iteration_count = 0
    
    logger.info("[BOT] Bot loop started")
    
    while True:
        if bot_running:
            iteration_count += 1
            logger.debug(f"[LOOP] Bot iteration #{iteration_count}")
            
            if not COMPO:
                if os.path.exists(COMPOSITION_FILE):
                    with open(COMPOSITION_FILE, "r") as f:
                        data = json.load(f)
                        COMPO = [os.path.splitext(u)[0] for u in data.get("units",[])]
                        logger.info(f"[COMP] Loaded composition: {COMPO}")
                else:
                    logger.error("[ERROR] No composition file found")
                    bot_running = False
                    continue
            
            try:
                screen_start = time.time()
                screen = adb_screenshot()
                screen_time = time.time() - screen_start
                logger.debug(f"[SCREEN] Screenshot: {screen_time:.3f}s")
                current_time = time.time()
            except Exception as e:
                logger.error(f"[ERROR] Screenshot error: {e}")
                time.sleep(0.1)
                continue

            if current_time - last_screen_time > 0.25:
                elixir_value = read_elixir(screen)
                if elixir_value is not None:
                    elixir_amount = elixir_value
                last_screen_time = current_time

            template_start = time.time()
            
            reward_pos = find_template(screen, REWARD)
            if reward_pos:
                logger.info("[ACTION] Reward detected, clicking to collect")
                adb_tap(*reward_pos)
                time.sleep(0.3)
                continue
            
            init_pos = find_template(screen, INIT_BATTLE)
            if init_pos:
                logger.info("[ACTION] Initial screen detected, clicking Battle")
                adb_tap(*init_pos)
                time.sleep(0.1)
                continue

            play_again = find_template(screen, PLAY_AGAIN_BATTLE)
            if play_again:
                logger.info("[ACTION] Play again screen detected")
                adb_tap(*play_again)
                time.sleep(0.1)
                continue

            quit = find_template(screen, QUIT)
            if quit:
                logger.info("[ACTION] Quit screen detected")
                adb_tap(*quit)
                time.sleep(0.1)
                continue

            deploy = find_template(screen, PHASE_DEPLOY)
            if deploy:
                logger.info("[PHASE] Deploy phase detected")
                elixir_amount = deploy_units(screen, COMPO, elixir_amount)
                time.sleep(0.3)
                continue

            battle_phase = find_template(screen, PHASE_BATTLE)
            if battle_phase:
                logger.info("[PHASE] Battle phase detected, waiting...")
                time.sleep(0.3)
                continue

            template_time = time.time() - template_start
            logger.debug(f"[TIME] Template matching: {template_time:.3f}s")
            logger.debug("[STATUS] Screen not recognized")
            time.sleep(0.2)
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
                logger.info("[BOT] Bot arrancat")
            elif name == "stop":
                bot_running = False
                logger.info("[BOT] Bot aturat")
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
