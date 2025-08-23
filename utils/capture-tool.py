import cv2
import numpy as np
import subprocess
import os
import time

SAVE_DIR = "templates"
os.makedirs(SAVE_DIR, exist_ok=True)

SCALE = 0.5  # 👈 escala de la finestra (0.5 = 50%)

def check_adb_device():
    result = subprocess.run(["adb", "devices"], stdout=subprocess.PIPE, text=True)
    lines = result.stdout.strip().split("\n")[1:]
    devices = [line.split()[0] for line in lines if "device" in line]

    if not devices:
        print("❌ No hi ha cap dispositiu connectat.")
        exit(1)

    if len(devices) == 1:
        print(f"✔ Connectat a {devices[0]}")
        return devices[0]

    print("📱 Dispositius disponibles:")
    for i, dev in enumerate(devices):
        print(f"{i+1}. {dev}")

    idx = int(input("Tria el dispositiu: ")) - 1
    return devices[idx]

def get_screenshot(device):
    result = subprocess.run(["adb", "-s", device, "exec-out", "screencap", "-p"], stdout=subprocess.PIPE)
    img = cv2.imdecode(np.frombuffer(result.stdout, np.uint8), cv2.IMREAD_COLOR)
    return img

def save_crop(img, roi, name=None):
    x, y, w, h = roi
    crop = img[y:y+h, x:x+w]
    if name is None:
        name = f"capture_{int(time.time())}.png"
    path = os.path.join(SAVE_DIR, name)
    cv2.imwrite(path, crop)
    print(f"[✔] Guardat: {path}")

def main():
    device = check_adb_device()
    img = get_screenshot(device)
    clone = img.copy()

    # 🔍 reduïm mida només per mostrar
    display = cv2.resize(img, (int(img.shape[1]*SCALE), int(img.shape[0]*SCALE)))

    print("👉 Selecciona amb el ratolí la zona (ROI).")
    print("   ENTER/ESPAI = guardar, ESC = cancel·lar.")

    roi_scaled = cv2.selectROI("Capture Tool", display, showCrosshair=True, fromCenter=False)
    cv2.destroyAllWindows()

    if roi_scaled != (0, 0, 0, 0):
        # ↩️ tornem a escalar coordenades a la mida original
        roi = tuple(int(v / SCALE) for v in roi_scaled)
        name = input("Nom de la captura (ex: summon.png): ").strip()
        if not name.endswith(".png"):
            name += ".png"
        save_crop(clone, roi, name)

if __name__ == "__main__":
    main()
