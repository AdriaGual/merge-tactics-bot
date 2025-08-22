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
FIELDS_DIR = "templates/field"     # unitats al camp
GRID_FILE = "grid_positions.json"
COMPOSITION_FILE = "composition.json"
ELIXIR_FILE = "elixir.json"
ADB_PATH = "adb"
THRESHOLD = 0.8

# Carregar cartes i unitats camp
unit_files = [f for f in os.listdir(UNITS_DIR) if f.endswith(".png")]
unit_imgs = [cv2.imread(os.path.join(UNITS_DIR, f)) for f in unit_files]

field_files = [f for f in os.listdir(FIELDS_DIR) if f.endswith(".png")]
field_imgs = [cv2.imread(os.path.join(FIELDS_DIR, f)) for f in field_files]

selected = [False]*len(unit_imgs)

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
SELL_BUTTON = os.path.join(TEMPLATES_DIR_MAIN, "sell.png")

# 🔹 Funcions auxiliars
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

# 🔹 Carregar coordenades del camp i banquillo
with open(GRID_FILE, "r") as f:
    grid_data = json.load(f)

grid_cells = [item for item in grid_data if item["name"].startswith("camp")]
bench_cells = [item for item in grid_data if item["name"].startswith("banquillo")]

# 🔹 Carregar coordenades elixir
with open(ELIXIR_FILE, "r") as f:
    elixir_data = json.load(f)
elixir_rect = next(item["rect"] for item in elixir_data if item["name"]=="elixir")
print(elixir_rect)
# 🔹 Detecció unitats a pantalla
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

# 🔹 Llegir elixir
def read_elixir(screen):
    x0, y0, x1, y1 = elixir_rect
    roi = screen[y0:y1, x0:x1]
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 150, 255, cv2.THRESH_BINARY_INV)
    text = pytesseract.image_to_string(thresh, config='--psm 7 digits')
    try:
        value = int("".join(filter(str.isdigit, text)))
        return value
    except:
        return None

# 🔹 Thread principal del bot
def bot_loop():
    global bot_running
    COMPO = []
    while True:
        if bot_running:
            # Carregar composició
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
            elixir_amount = read_elixir(screen)
            if elixir_amount is not None:
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

            # Deploy phase
            deploy = find_template(screen, PHASE_DEPLOY)
            if deploy:
                print("🟢 Deploy phase")

                detected_fields = find_units_on_screen(screen, field_imgs)
                detected_bench = find_units_on_screen(screen, unit_imgs)

                vis_screen = cv2.resize(screen, (screen.shape[1]//2, screen.shape[0]//2))
                scale_x = screen.shape[1]/vis_screen.shape[1]
                scale_y = screen.shape[0]/vis_screen.shape[0]

                # Vendre unitats que no estiguin a la composició
                for i, center in detected_fields + detected_bench:
                    if (i < len(field_imgs)):
                        name_file = field_files[i]
                    else:
                        name_file = unit_files[i]
                    pos_name = get_unit_position(center)
                    cx, cy = int(center[0]/scale_x), int(center[1]/scale_y)

                    if os.path.splitext(name_file)[0] not in COMPO and pos_name != "desconegut":
                        print(f"💸 Venen {name_file} a {pos_name}")
                        adb_tap(*center)
                        time.sleep(2)
                        screen = adb_screenshot()
                        sell_pos = find_template(screen, SELL_BUTTON)
                        if sell_pos:
                            adb_tap(*sell_pos)
                            time.sleep(0.5)
                        else:
                            print("❌ No s'ha trobat botó Sell")


                # Comprar unitats que falten
                for u in COMPO:
                    template_path = os.path.join(UNITS_DIR, u+".png")
                    pos = find_template(screen, template_path)
                    if pos:
                        print(f"💰 Comprant {u}")
                        adb_tap(*pos)
                        time.sleep(2)
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
    # Miniatures
    for idx, img in enumerate(unit_imgs):
        row = idx//COLS
        col = idx%COLS
        x = col*(IMG_SIZE[0]+MARGIN)+MARGIN
        y = row*(IMG_SIZE[1]+MARGIN)+MARGIN+70
        thumb = cv2.resize(img, IMG_SIZE)
        canvas[y:y+IMG_SIZE[1], x:x+IMG_SIZE[0]] = thumb
        if selected[idx]:
            cv2.rectangle(canvas, (x,y), (x+IMG_SIZE[0], y+IMG_SIZE[1]), (0,255,0),3)
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
