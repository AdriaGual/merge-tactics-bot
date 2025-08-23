import cv2
import os
import json
from datetime import datetime

def view_debug_images():
    """Interactive debug image viewer"""
    debug_dir = "debug_images"
    
    if not os.path.exists(debug_dir):
        print("❌ No debug images directory found")
        return
    
    images = [f for f in os.listdir(debug_dir) if f.endswith(('.png', '.jpg'))]
    
    if not images:
        print("❌ No debug images found")
        return
    
    print(f"📸 Found {len(images)} debug images")
    current_idx = 0
    
    while True:
        if current_idx >= len(images):
            current_idx = 0
        
        img_path = os.path.join(debug_dir, images[current_idx])
        img = cv2.imread(img_path)
        
        if img is not None:
            # Resize if too large
            h, w = img.shape[:2]
            if w > 800 or h > 600:
                scale = min(800/w, 600/h)
                new_w, new_h = int(w*scale), int(h*scale)
                img = cv2.resize(img, (new_w, new_h))
            
            # Add filename to image
            cv2.putText(img, images[current_idx], (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            cv2.imshow("Debug Viewer", img)
            
            key = cv2.waitKey(0) & 0xFF
            if key == 27:  # ESC
                break
            elif key == ord('n') or key == ord(' '):  # Next
                current_idx += 1
            elif key == ord('p'):  # Previous
                current_idx = max(0, current_idx - 1)
            elif key == ord('d'):  # Delete
                os.remove(img_path)
                images.remove(images[current_idx])
                print(f"🗑️ Deleted {img_path}")
                if not images:
                    break
        else:
            current_idx += 1
    
    cv2.destroyAllWindows()

def analyze_log():
    """Analyze bot performance from log file"""
    log_file = "bot_debug.log"
    
    if not os.path.exists(log_file):
        print("❌ No log file found")
        return
    
    with open(log_file, 'r') as f:
        lines = f.readlines()
    
    # Extract timing information
    timings = {}
    elixir_readings = []
    errors = []
    
    for line in lines:
        if "⏱️" in line:
            parts = line.split("⏱️")[1].strip()
            if ":" in parts:
                func_name, time_str = parts.split(":", 1)
                time_val = float(time_str.strip().replace("s", ""))
                if func_name not in timings:
                    timings[func_name] = []
                timings[func_name].append(time_val)
        
        elif "⚡ Elixir" in line:
            elixir_readings.append(line.strip())
        
        elif "❌" in line or "ERROR" in line:
            errors.append(line.strip())
    
    print("\n📊 PERFORMANCE ANALYSIS")
    print("=" * 50)
    
    for func_name, times in timings.items():
        avg_time = sum(times) / len(times)
        max_time = max(times)
        min_time = min(times)
        print(f"{func_name}:")
        print(f"  Average: {avg_time:.3f}s")
        print(f"  Min: {min_time:.3f}s, Max: {max_time:.3f}s")
        print(f"  Calls: {len(times)}")
        print()
    
    print(f"📈 ELIXIR READINGS ({len(elixir_readings)} total)")
    print("=" * 50)
    for reading in elixir_readings[-10:]:  # Last 10 readings
        print(reading)
    
    if errors:
        print(f"\n❌ ERRORS ({len(errors)} total)")
        print("=" * 50)
        for error in errors[-5:]:  # Last 5 errors
            print(error)

if __name__ == "__main__":
    print("🔧 Debug Tools")
    print("1. View debug images (press 'n' for next, 'p' for previous, 'd' to delete, ESC to exit)")
    print("2. Analyze performance log")
    
    choice = input("Choose option (1/2): ")
    
    if choice == "1":
        view_debug_images()
    elif choice == "2":
        analyze_log()
    else:
        print("❌ Invalid choice")
