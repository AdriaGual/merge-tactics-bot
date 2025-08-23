import cv2
import numpy as np
import os
import threading
import time
import subprocess
import json

# 🔧 Configuració
TEMPLATES_DIR = "templates/field"
GRID_FILE = "../grid_positions.json"
ADB_PATH = "adb"
THRESHOLD = 0.7

# Carreguem unitats disponibles
unit_files = [f for f in os.listdir(TEMPLATES_DIR) if f.endswith(".png")]
unit_imgs = [cv2.imread(os.path.join(TEMPLATES_DIR, f)) for f in unit_files]

bot_running = True  # Arrenca automàticament

# 🔹 Carregar coordenades de la graella
with open(GRID_FILE, "r") as f:
    grid_data = json.load(f)

# Separar caselles i banquillo
grid_cells = [item for item in grid_data if item["name"].startswith("camp")]
bench_cells = [item for item in grid_data if item["name"].startswith("banquillo")]

# 🔹 Funcions auxiliars
def adb_screenshot():
    result = subprocess.run([ADB_PATH, "exec-out", "screencap", "-p"], stdout=subprocess.PIPE)
    img = cv2.imdecode(np.frombuffer(result.stdout, np.uint8), cv2.IMREAD_COLOR)
    return img

def find_units_on_screen(screen, templates, threshold=0.8, min_dist=50):
    detected = []
    for i, template in enumerate(templates):
        res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
        loc = np.where(res >= threshold)
        h, w = template.shape[:2]
        centers = [(pt[0]+w//2, pt[1]+h//2) for pt in zip(*loc[::-1])]

        # Filtrar deteccions molt properes
        final_centers = []
        for c in centers:
            if all(np.hypot(c[0]-fc[0], c[1]-fc[1]) > min_dist for fc in final_centers):
                final_centers.append(c)

        detected.extend([(i, c) for c in final_centers])
    return detected

# 🔹 Funció per saber en quina casella està una unitat
def get_unit_position(center):
    x, y = center
    # Primer mirar la graella
    for cell in grid_cells:
        x0, y0, x1, y1 = cell["rect"]
        if x0 <= x <= x1 and y0 <= y <= y1:
            return cell["name"]
    # Després mirar banquillo
    for cell in bench_cells:
        x0, y0, x1, y1 = cell["rect"]
        if x0 <= x <= x1 and y0 <= y <= y1:
            return cell["name"]
    return "desconegut"

# 🔹 Thread de detecció
def bot_loop():
    global bot_running
    while bot_running:
        try:
            screen = adb_screenshot()
        except:
            print("❌ Error en capturar pantalla")
            time.sleep(1)
            continue

        # Detectar totes les unitats presents
        detected_units = find_units_on_screen(screen, unit_imgs, THRESHOLD)
        for i, center in detected_units:
            name = unit_files[i]
            pos = get_unit_position(center)
            print(f"🔎 {name} detectada a {pos}")

# 🔹 Inici del bot
threading.Thread(target=bot_loop, daemon=True).start()
print("Bot arrencat, CTRL+C per aturar")
while True:
    time.sleep(0.5)
