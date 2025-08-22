import cv2
import numpy as np
import subprocess
import time
import os

# 🔧 Ruta a adb.exe (canvia si cal)
ADB_PATH = "adb"

# 🔹 Templates
TEMPLATES_DIR = "templates"
INIT_BATTLE = os.path.join(TEMPLATES_DIR, "battle.png")          # Pantalla inicial
PHASE_DEPLOY = os.path.join(TEMPLATES_DIR, "deploy_phase.png")   # Deploy phase
PHASE_BATTLE = os.path.join(TEMPLATES_DIR, "battle_phase.png")   # Battle phase
UNITS = [
    os.path.join(TEMPLATES_DIR, "dart_goblin.png"),
    os.path.join(TEMPLATES_DIR, "goblin.png"),
    os.path.join(TEMPLATES_DIR, "knight.png"),
    os.path.join(TEMPLATES_DIR, "spear_goblin.png"),
    os.path.join(TEMPLATES_DIR, "barbarian.png"),
    os.path.join(TEMPLATES_DIR, "executioner.png"),
    os.path.join(TEMPLATES_DIR, "giant_skeleton.png"),
    os.path.join(TEMPLATES_DIR, "golden_knight.png"),
    os.path.join(TEMPLATES_DIR, "pekka.png"),
    os.path.join(TEMPLATES_DIR, "princess.png"),
    os.path.join(TEMPLATES_DIR, "royal_ghost.png")
]

THRESHOLD = 0.8  # Confiança mínima per detectar plantilles

# 🔹 Funcions auxiliars
def adb_screenshot():
    """Captura pantalla de l'emulador/mòbil"""
    result = subprocess.run([ADB_PATH, "exec-out", "screencap", "-p"], stdout=subprocess.PIPE)
    img = cv2.imdecode(np.frombuffer(result.stdout, np.uint8), cv2.IMREAD_COLOR)
    return img

def adb_tap(x, y):
    """Simula tap via ADB"""
    subprocess.run([ADB_PATH, "shell", "input", "tap", str(x), str(y)])

def find_template(screen, template_path, threshold=THRESHOLD):
    """Busca plantilla a la pantalla i retorna coordenades del centre"""
    if not os.path.exists(template_path):
        print(f"❌ No existeix la plantilla {template_path}")
        return None

    template = cv2.imread(template_path, cv2.IMREAD_COLOR)
    res = cv2.matchTemplate(screen, template, cv2.TM_CCOEFF_NORMED)
    min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res)

    if max_val >= threshold:
        h, w = template.shape[:2]
        return max_loc[0] + w//2, max_loc[1] + h//2
    return None

# 🔹 Loop principal
def main_loop():
    print("🤖 Bot iniciat, Ctrl+C per parar")
    while True:
        screen = adb_screenshot()

        # Detectem pantalla inicial
        init_pos = find_template(screen, INIT_BATTLE)
        if init_pos:
            print("🏁 Pantalla inicial detectada, pitjant Battle")
            adb_tap(*init_pos)
            time.sleep(2)
            continue

        # Detectem fase deploy
        deploy = find_template(screen, PHASE_DEPLOY)
        if deploy:
            print("🟢 Deploy phase detectada")
            # Busquem unitats a comprar
            for unit in UNITS:
                pos = find_template(screen, unit)
                if pos:
                    print(f"💰 Comprant unitat {os.path.basename(unit)}")
                    adb_tap(*pos)
                    time.sleep(0.5)
            time.sleep(1)
            continue

        # Detectem fase battle
        battle_phase = find_template(screen, PHASE_BATTLE)
        if battle_phase:
            print("🔴 Battle phase, esperant...")
            time.sleep(3)
            continue

        # Si no detecta res
        print("… Pantalla no reconeguda, intentant de nou")
        time.sleep(1)

if __name__ == "__main__":
    main_loop()
