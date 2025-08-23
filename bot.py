import cv2
import numpy as np
import os
import json
import threading
import time
import subprocess
import pytesseract

# 🔧 Configuració
UNITS_DIR = "templates/units"       # cartes que es poden comprar
FIELDS_DIR = "templates/field"      # unitats al camp
GRID_FILE = "grid_positions.json"
COMPOSITION_FILE = "composition.json"
ELIXIR_FILE = "elixir.json"
ADB_PATH = "adb"
THRESHOLD = 0.8

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

# 🔹 Carregar unitats i costos
unit_files = [f for f in os.listdir(UNITS_DIR) if f.endswith(".png")]
unit_imgs = [cv2.imread(os.path.join(UNITS_DIR, f)) for f in unit_files]
selected = [False]*len(unit_imgs)

field_files = [f for f in os.listdir(FIELDS_DIR) if f.endswith(".png")]
field_imgs = [cv2.imread(os.path.join(FIELDS_DIR, f)) for f in field_files]

# Assigna el cost manualment aquí
unit_costs = {
    "barbarian": 2,
    "archer": 3,
    "knight": 2,
    "archer_queen": 5,
    "bandit": 4,
    "bomber": 2,
    "dart_goblin": 3,
    "executioner": 3,
    "giant_skeleton": 3,
    "goblin": 2,
    "goblin_machine": 4,
    "golden_knight": 5,
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
    print(f"📦 Composició confirmada: {chosen_units}")
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
def read_elixir(screen):
    x0, y0, x1, y1 = elixir_rect
    
    # Retallar la ROI
    roi = screen[y0:y1, x0:x1]
    
    # Convert to grayscale
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    
    # Apply morphological operations to clean up the image
    kernel = np.ones((2,2), np.uint8)
    gray = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
    
    # Use Otsu's thresholding for better binarization
    _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Invert if background is darker than text
    if np.mean(thresh) < 127:
        thresh = cv2.bitwise_not(thresh)
    
    detected_digits = []
    digit_templates = load_digit_templates()
    
    if digit_templates:
        # Find all digit matches with higher threshold for better accuracy
        for digit, template in digit_templates.items():
            if template is not None:
                res = cv2.matchTemplate(thresh, template, cv2.TM_CCOEFF_NORMED)
                locations = np.where(res >= 0.8)  # Higher threshold for better accuracy
                
                h, w = template.shape[:2]
                for pt in zip(*locations[::-1]):
                    # Store position, digit, and confidence
                    confidence = res[pt[1], pt[0]]
                    detected_digits.append((pt[0], pt[1], digit, confidence, w))
        
        if detected_digits:
            # Remove overlapping detections (keep highest confidence)
            filtered_digits = []
            detected_digits.sort(key=lambda x: x[3], reverse=True)  # Sort by confidence
            
            for current in detected_digits:
                x, y, digit, conf, width = current
                # Check if this detection overlaps with any already accepted detection
                overlap = False
                for accepted in filtered_digits:
                    ax, ay, _, _, awidth = accepted
                    # Check for significant overlap
                    if (abs(x - ax) < max(width, awidth) * 0.7 and abs(y - ay) < 10):
                        overlap = True
                        break
                
                if not overlap:
                    filtered_digits.append(current)
            
            # Sort remaining digits by x-coordinate (left to right)
            filtered_digits.sort(key=lambda x: x[0])
            
            # Build the number string
            elixir_str = ''.join([str(digit) for _, _, digit, _, _ in filtered_digits])
            
            # Validate the result (elixir should be reasonable)
            if elixir_str and len(elixir_str) <= 3:  # Max 3 digits (up to 999)
                try:
                    value = int(elixir_str)
                    if 0 <= value <= 999:  # Reasonable elixir range
                        print(f"⚡ Elixir detectat (template): {value}")
                        return value
                except ValueError:
                    pass
    
    # Apply additional noise reduction for OCR
    kernel_large = np.ones((3,3), np.uint8)
    thresh_clean = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_large)
    thresh_clean = cv2.morphologyEx(thresh_clean, cv2.MORPH_CLOSE, kernel_large)
    
    # Enhanced OCR configuration for multi-digit numbers
    custom_config = r'--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789'
    text = pytesseract.image_to_string(thresh_clean, config=custom_config)
    
    # Clean and extract digits
    digits_only = ''.join(filter(str.isdigit, text.strip()))
    
    if digits_only and len(digits_only) <= 3:
        try:
            value = int(digits_only)
            if 0 <= value <= 999:  # Reasonable elixir range
                print(f"⚡ Elixir (OCR fallback): {value}")
                return value
        except ValueError:
            pass
    
    print("❌ No s'ha pogut llegir l'elixir")
    return None

def load_digit_templates():
    """Load digit templates for template matching"""
    templates = {}
    templates_dir = "templates/digits"
    
    # Create templates directory if it doesn't exist
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
        print(f"📁 Directori creat: {templates_dir}")
        print("💡 Afegeix plantilles de dígits (0.png, 1.png, ..., 9.png) per millorar la detecció")
        return {}
    
    # Load digit templates (0-9)
    for digit in range(10):
        template_path = os.path.join(templates_dir, f"{digit}.png")
        if os.path.exists(template_path):
            template = cv2.imread(template_path, cv2.IMREAD_GRAYSCALE)
            if template is not None:
                # Apply same preprocessing as ROI
                _, template = cv2.threshold(template, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
                if np.mean(template) < 127:
                    template = cv2.bitwise_not(template)
                templates[digit] = template
            else:
                print(f"⚠️ No s'ha pogut carregar la plantilla: {template_path}")
        else:
            templates[digit] = None
    
    loaded_count = sum(1 for t in templates.values() if t is not None)
    if loaded_count > 0:
        print(f"✅ Carregades {loaded_count} plantilles de dígits")
    else:
        print("⚠️ No s'han trobat plantilles de dígits. Usant OCR com a mètode principal.")
    
    return templates

# 🔹 Funció intel·ligent de deploy
def deploy_units(screen, COMPO, elixir_amount):
    detected_fields = find_units_on_screen(screen, field_imgs)
    detected_bench = find_units_on_screen(screen, unit_imgs)

    # 💸 Vendre unitats innecessàries
    for i, center in detected_fields + detected_bench:
        name_file = field_files[i] if i < len(field_imgs) else unit_files[i]
        unit_name = os.path.splitext(name_file)[0]
        pos_name = get_unit_position(center)
        
        if unit_name not in COMPO and pos_name != "desconegut":
            potential_elixir = elixir_amount + max(unit_costs.get(unit_name,0)-1,0)
            can_buy = any(unit_costs.get(u,0) <= potential_elixir for u in COMPO)
            if can_buy:
                print(f"💸 Venen {unit_name} a {pos_name}")
                adb_tap(*center)
                time.sleep(2)
                screen = adb_screenshot()
                sell_pos = find_template(screen, SELL_BUTTON)
                if sell_pos:
                    adb_tap(*sell_pos)
                    time.sleep(0.5)
                    elixir_amount += unit_costs.get(unit_name,0)-1
                else:
                    print("❌ No s'ha trobat botó Sell")

    # 💰 Comprar unitats
    print(elixir_amount)
    affordable_units = [u for u in COMPO if unit_costs.get(u,0) <= elixir_amount]
    print(affordable_units)
    if affordable_units:
        u_to_buy = max(affordable_units, key=lambda u: unit_costs[u])
        template_path = os.path.join(UNITS_DIR, u_to_buy+".png")
        pos = find_template(screen, template_path)
        if pos:
            print(f"💰 Comprant {u_to_buy}")
            adb_tap(*pos)
            elixir_amount -= unit_costs[u_to_buy]
            time.sleep(2)
    return elixir_amount

# 🔹 Thread principal del bot
def bot_loop():
    global bot_running
    COMPO = []
    elixir_amount = 0
    while True:
        if bot_running:
            if not COMPO:
                if os.path.exists(COMPOSITION_FILE):
                    with open(COMPOSITION_FILE, "r") as f:
                        data = json.load(f)
                        COMPO = [os.path.splitext(u)[0] for u in data.get("units",[])]
                        print(f"Bot amb composició: {COMPO}")
                else:
                    print("❌ No hi ha cap composició")
                    bot_running = False
                    continue
            try:
                screen = adb_screenshot()
            except:
                print("❌ Error en capturar pantalla")
                time.sleep(0.25)
                continue

            # Llegir elixir
            elixir_value = read_elixir(screen)
            if elixir_value is not None:
                elixir_amount = elixir_value
                print(f"⚡ Elixir actual: {elixir_amount}")

            # Pantalla inicial
            init_pos = find_template(screen, INIT_BATTLE)
            if init_pos:
                print("🏁 Pantalla inicial, pitjant Battle")
                adb_tap(*init_pos)
                time.sleep(0.25)
                continue

            # Tornar a jugar
            play_again = find_template(screen, PLAY_AGAIN_BATTLE)
            if play_again:
                print("🏁 Tornar a jugar")
                adb_tap(*play_again)
                time.sleep(0.25)
                continue

            # Tornar a jugar
            quit = find_template(screen, QUIT)
            if quit:
                print("Sortir")
                adb_tap(*quit)
                time.sleep(0.25)
                continue


            # Deploy phase
            deploy = find_template(screen, PHASE_DEPLOY)
            if deploy:
                print("🟢 Deploy phase")
                elixir_amount = deploy_units(screen, COMPO, elixir_amount)
                time.sleep(0.5)
                continue

            # Battle phase
            battle_phase = find_template(screen, PHASE_BATTLE)
            if battle_phase:
                print("🔴 Battle phase, esperant...")
                time.sleep(0.5)
                continue

            print("… Pantalla no reconeguda")
            time.sleep(0.5)
        else:
            time.sleep(0.5)

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
                print("▶️ Bot arrancat")
            elif name == "stop":
                bot_running = False
                print("⏹ Bot aturat")
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
