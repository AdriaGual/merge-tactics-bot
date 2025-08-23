import cv2
import numpy as np
import subprocess
import json
import os

def adb_screenshot():
    """Capture screenshot using ADB"""
    try:
        result = subprocess.run(["adb", "exec-out", "screencap", "-p"], stdout=subprocess.PIPE, timeout=10)
        if result.returncode != 0:
            raise ValueError("ADB command failed")
        img = cv2.imdecode(np.frombuffer(result.stdout, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Error al capturar pantalla amb ADB")
        return img
    except subprocess.TimeoutExpired:
        raise ValueError("ADB timeout - assegura't que el dispositiu està connectat")
    except FileNotFoundError:
        raise ValueError("ADB no trobat - assegura't que ADB està instal·lat i al PATH")

def create_digit_templates():
    """Interactive tool to create digit templates from game screenshots"""
    
    try:
        result = subprocess.run(["adb", "devices"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        if b"device" not in result.stdout:
            print("❌ Cap dispositiu ADB connectat. Connecta el dispositiu i activa la depuració USB.")
            return
    except:
        print("❌ ADB no disponible. Instal·la ADB i afegeix-lo al PATH.")
        return
    
    # Create templates directory
    templates_dir = "templates/digits"
    if not os.path.exists(templates_dir):
        os.makedirs(templates_dir)
    
    # Load elixir coordinates
    try:
        with open("elixir.json", "r") as f:
            elixir_data = json.load(f)
        elixir_rect = next(item["rect"] for item in elixir_data if item["name"]=="elixir")
    except:
        print("❌ Error llegint elixir.json")
        return
    
    captured_digits = set()
    
    # Check existing templates
    for digit in range(10):
        template_path = os.path.join(templates_dir, f"{digit}.png")
        if os.path.exists(template_path):
            captured_digits.add(digit)
    
    print("🎯 Eina per crear plantilles de dígits")
    print("📱 Assegura't que el joc mostri diferents valors d'elixir")
    print("⌨️ Controls:")
    print("   ESPAI - Capturar pantalla")
    print("   ENTER - Confirmar selecció")
    print("   ESC - Sortir")
    
    if captured_digits:
        print(f"✅ Dígits ja capturats: {sorted(captured_digits)}")
    
    missing_digits = set(range(10)) - captured_digits
    if missing_digits:
        print(f"❌ Dígits pendents: {sorted(missing_digits)}")
    else:
        print("🎉 Tots els dígits ja estan capturats!")
    
    try:
        while True:
            print(f"\n📊 Estat actual:")
            print(f"   ✅ Capturats: {sorted(captured_digits) if captured_digits else 'Cap'}")
            print(f"   ❌ Pendents: {sorted(missing_digits) if missing_digits else 'Cap'}")
            
            if not missing_digits:
                print("🎉 Tots els dígits completats!")
                break
            
            print(f"\n🔢 Quin dígit vols capturar? ({', '.join(map(str, sorted(missing_digits)))})")
            print("   Escriu el número del dígit o 'q' per sortir:")
            
            user_input = input(">>> ").strip().lower()
            
            if user_input == 'q':
                print("❌ Sortint...")
                break
            
            try:
                digit = int(user_input)
                if digit not in range(10):
                    print("❌ El dígit ha de ser entre 0 i 9")
                    continue
                if digit in captured_digits:
                    overwrite = input(f"⚠️ El dígit {digit} ja existeix. Vols sobreescriure'l? (s/n): ").strip().lower()
                    if overwrite != 's':
                        continue
            except ValueError:
                print("❌ Entrada no vàlida")
                continue
            
            print(f"\n📱 Ara captura una pantalla que mostri el dígit {digit}")
            print("Prem ESPAI per capturar la pantalla...")
            
            # Wait for capture
            cv2.namedWindow("Controls", cv2.WINDOW_NORMAL)
            cv2.resizeWindow("Controls", 300, 100)
            control_img = np.zeros((100, 300, 3), dtype=np.uint8)
            cv2.putText(control_img, f"Capturant digit {digit}", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
            cv2.putText(control_img, "Prem ESPAI", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)
            cv2.imshow("Controls", control_img)
            
            while True:
                key = cv2.waitKey(30) & 0xFF
                if key == ord(' '):
                    break
                elif key == 27:
                    print("❌ Cancel·lant captura...")
                    cv2.destroyAllWindows()
                    continue
            
            # Capture screenshot
            screen = adb_screenshot()
            x0, y0, x1, y1 = elixir_rect
            roi = screen[y0:y1, x0:x1]
            
            # Preprocess the same way as in the main function
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            kernel = np.ones((2,2), np.uint8)
            gray = cv2.morphologyEx(gray, cv2.MORPH_CLOSE, kernel)
            _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            
            if np.mean(thresh) < 127:
                thresh = cv2.bitwise_not(thresh)
            
            scale_factor = 4
            display_img = cv2.resize(thresh, (thresh.shape[1] * scale_factor, thresh.shape[0] * scale_factor), interpolation=cv2.INTER_NEAREST)
            
            cv2.destroyWindow("Controls")
            
            print(f"\n🔢 Selecciona el dígit {digit} a la imatge")
            
            # Variables for selection
            selecting = False
            start_point = None
            end_point = None
            
            def mouse_callback(event, x, y, flags, param):
                nonlocal selecting, start_point, end_point
                
                if event == cv2.EVENT_LBUTTONDOWN:
                    selecting = True
                    start_point = (x, y)
                    end_point = None
                    
                elif event == cv2.EVENT_MOUSEMOVE and selecting:
                    end_point = (x, y)
                    
                elif event == cv2.EVENT_LBUTTONUP:
                    selecting = False
                    if start_point and end_point:
                        end_point = (x, y)
            
            window_name = f"Selecciona dígit {digit} - ENTER per confirmar, ESC per cancel·lar"
            cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
            cv2.setMouseCallback(window_name, mouse_callback)
            
            while True:
                display_copy = display_img.copy()
                
                # Draw current selection
                if start_point and end_point:
                    cv2.rectangle(display_copy, start_point, end_point, (0, 255, 0), 2)
                
                cv2.imshow(window_name, display_copy)
                
                key = cv2.waitKey(30) & 0xFF
                if key == ord('\r') or key == ord('\n'):  # Enter
                    if start_point and end_point:
                        orig_x1 = min(start_point[0], end_point[0]) // scale_factor
                        orig_y1 = min(start_point[1], end_point[1]) // scale_factor
                        orig_x2 = max(start_point[0], end_point[0]) // scale_factor
                        orig_y2 = max(start_point[1], end_point[1]) // scale_factor
                        
                        if orig_x2 > orig_x1 and orig_y2 > orig_y1:
                            digit_template = thresh[orig_y1:orig_y2, orig_x1:orig_x2]
                            
                            # Save template
                            template_path = os.path.join(templates_dir, f"{digit}.png")
                            cv2.imwrite(template_path, digit_template)
                            print(f"✅ Dígit {digit} guardat: {template_path}")
                            captured_digits.add(digit)
                            missing_digits.discard(digit)
                            break
                        else:
                            print("❌ Selecció massa petita")
                    else:
                        print("❌ No hi ha selecció")
                        
                elif key == 27:  # ESC
                    print(f"❌ Cancel·lant captura del dígit {digit}")
                    break
            
            cv2.destroyWindow(window_name)
        
        print("🎉 Procés completat!")
        print("🔄 Les plantilles estan a templates/digits/")
        
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        cv2.destroyAllWindows()

if __name__ == "__main__":
    create_digit_templates()
