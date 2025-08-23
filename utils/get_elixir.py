import cv2
import subprocess
import numpy as np
import json

# 🔹 Screenshot amb ADB
def adb_screenshot():
    result = subprocess.run(["adb", "exec-out", "screencap", "-p"], stdout=subprocess.PIPE)
    img = cv2.imdecode(np.frombuffer(result.stdout, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Error al capturar pantalla amb ADB")
    return img

# 🔹 Variables globals
drawing = False
ix, iy = -1, -1
rect = None
coords = []
scale = 1.0

def draw_rectangle(event, x, y, flags, param):
    global drawing, ix, iy, rect, coords
    img, name = param["img"], param["name"]
    scale = param["scale"]
    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        ix, iy = int(x/scale), int(y/scale)
    elif event == cv2.EVENT_MOUSEMOVE:
        if drawing:
            x0, y0 = ix, iy
            x1, y1 = int(x/scale), int(y/scale)
            rect = (x0, y0, x1, y1)
    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        x0, y0 = ix, iy
        x1, y1 = int(x/scale), int(y/scale)
        rect = (x0, y0, x1, y1)
        coords.append({"name": name, "rect": rect})
        print(f"✅ {name} marcada: {rect}")
        cv2.destroyWindow("Marca casella")

# 🔹 Funció per demanar cada posició
def ask_rectangle(name, img):
    cv2.namedWindow("Marca casella")
    cv2.setMouseCallback("Marca casella", draw_rectangle, {"img": img, "name": name, "scale": scale})
    print(f"\nDibuixa un rectangle per '{name}' amb el ratolí (clic esquerre + arrossega)")
    while True:
        disp_img = cv2.resize(img, (int(img.shape[1]*scale), int(img.shape[0]*scale)))
        temp_img = disp_img.copy()
        if rect:
            x0, y0, x1, y1 = [int(c*scale) for c in rect]
            cv2.rectangle(temp_img, (x0, y0), (x1, y1), (0,255,0), 2)
        cv2.imshow("Marca casella", temp_img)
        key = cv2.waitKey(20) & 0xFF
        if len(coords) > 0 and coords[-1]["name"] == name:
            break
        if key == 27:
            print("Sortint sense acabar")
            exit()

# 🔹 Captura la imatge del joc
screen = adb_screenshot()
h, w = screen.shape[:2]
max_h, max_w = 800, 1200
scale = min(max_w/w, max_h/h, 1.0)


ask_rectangle('elixir', screen)

# 🔹 Guardar coordenades
with open("../elixir.json", "w") as f:
    json.dump(coords, f, indent=4)

print("\n✅ Totes les coordenades guardades a 'elixir.json'")
