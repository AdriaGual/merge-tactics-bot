import cv2
import numpy as np
import subprocess
import json
import os

def adb_screenshot():
    """Captura screenshot via ADB"""
    result = subprocess.run(["adb", "exec-out", "screencap", "-p"], stdout=subprocess.PIPE, timeout=10)
    if result.returncode != 0:
        raise ValueError("ADB command failed")
    img = cv2.imdecode(np.frombuffer(result.stdout, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Error al capturar pantalla amb ADB")
    return img

def create_elixir_templates():
    """Captura i guarda les plantilles d'elixir sense processament"""

    # Comprova dispositiu
    try:
        result = subprocess.run(["adb", "devices"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        if b"device" not in result.stdout:
            print("❌ Cap dispositiu ADB connectat")
            return
    except:
        print("❌ ADB no disponible")
        return

    # Crea carpeta si no existeix
    templates_dir = "../templates/digits"
    os.makedirs(templates_dir, exist_ok=True)

    # Llegeix coordenades del ROI de l’elixir
    try:
        with open("../elixir.json", "r") as f:
            elixir_data = json.load(f)
        elixir_rect = next(item["rect"] for item in elixir_data if item["name"] == "elixir")
    except:
        print("❌ Error llegint elixir.json")
        return

    print("🎯 Eina per capturar plantilles d’elixir (tal qual)")
    print("📱 Mostra al joc el número d’elixir que vols guardar")
    print("⌨️ Controls: ESPAI = Capturar, ESC = Sortir")

    number = 0
    while True:
        print(f"\n🔢 Quin número vols capturar? (0-15 o més, q per sortir)")
        user_input = input(">>> ").strip().lower()

        if user_input == 'q':
            print("❌ Sortint...")
            break

        try:
            number = int(user_input)
        except ValueError:
            print("❌ Entrada no vàlida")
            continue

        print(f"📸 Preparat per capturar {number} elixir (prem ESPAI)...")

        # Mostra finestra de control
        cv2.namedWindow("Controls", cv2.WINDOW_NORMAL)
        control_img = np.zeros((100, 300, 3), dtype=np.uint8)
        cv2.putText(control_img, f"Capturant {number} elixir", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        cv2.imshow("Controls", control_img)

        while True:
            key = cv2.waitKey(30) & 0xFF
            if key == ord(' '):  # ESPAI
                break
            elif key == 27:  # ESC
                print("❌ Cancel·lant captura...")
                cv2.destroyWindow("Controls")
                continue

        # Captura i retalla ROI
        screen = adb_screenshot()
        x0, y0, x1, y1 = elixir_rect
        roi = screen[y0:y1, x0:x1]  # sense processament

        # Desa directament
        template_path = os.path.join(templates_dir, f"{number}.png")
        cv2.imwrite(template_path, roi)
        print(f"✅ Plantilla guardada: {template_path}")

        cv2.destroyWindow("Controls")

    cv2.destroyAllWindows()
    print("🎉 Procés completat!")

if __name__ == "__main__":
    create_elixir_templates()
