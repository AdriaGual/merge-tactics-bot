import cv2
import numpy as np
import json
import subprocess
import os

def adb_screenshot():
    result = subprocess.run(["adb", "exec-out", "screencap", "-p"], stdout=subprocess.PIPE)
    img = cv2.imdecode(np.frombuffer(result.stdout, np.uint8), cv2.IMREAD_COLOR)
    return img

def main():
    print("🔧 Elixir Debug Tool")
    print("This tool helps you debug elixir detection issues")
    print()
    
    # Load elixir coordinates
    if not os.path.exists("../elixir.json"):
        print("❌ elixir.json not found!")
        return
    
    with open("../elixir.json", "r") as f:
        elixir_data = json.load(f)
    elixir_rect = next(item["rect"] for item in elixir_data if item["name"]=="elixir")
    
    print("📱 Taking screenshot...")
    screen = adb_screenshot()
    
    if screen is None:
        print("❌ Could not take screenshot. Make sure ADB is connected.")
        return
    
    # Extract elixir region
    x0, y0, x1, y1 = elixir_rect
    roi = screen[y0:y1, x0:x1]
    
    # Create debug directory
    debug_dir = "elixir_debug"
    if not os.path.exists(debug_dir):
        os.makedirs(debug_dir)
    
    # Save original ROI
    cv2.imwrite(f"{debug_dir}/original_roi.png", roi)
    
    # Apply different preprocessing methods
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    
    # Resize for better visibility
    scale_factor = 5
    roi_large = cv2.resize(roi, (roi.shape[1] * scale_factor, roi.shape[0] * scale_factor), interpolation=cv2.INTER_NEAREST)
    gray_large = cv2.resize(gray, (gray.shape[1] * scale_factor, gray.shape[0] * scale_factor), interpolation=cv2.INTER_NEAREST)
    
    # Different thresholding methods
    _, thresh1 = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)
    _, thresh2 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    thresh3 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    _, thresh4 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    # Enhanced contrast
    enhanced = cv2.equalizeHist(gray)
    _, thresh5 = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    # Save all versions
    methods = [
        ("original", roi_large),
        ("grayscale", gray_large),
        ("simple_thresh", cv2.resize(thresh1, (thresh1.shape[1] * scale_factor, thresh1.shape[0] * scale_factor), interpolation=cv2.INTER_NEAREST)),
        ("otsu_thresh", cv2.resize(thresh2, (thresh2.shape[1] * scale_factor, thresh2.shape[0] * scale_factor), interpolation=cv2.INTER_NEAREST)),
        ("adaptive_thresh", cv2.resize(thresh3, (thresh3.shape[1] * scale_factor, thresh3.shape[0] * scale_factor), interpolation=cv2.INTER_NEAREST)),
        ("inverted_otsu", cv2.resize(thresh4, (thresh4.shape[1] * scale_factor, thresh4.shape[0] * scale_factor), interpolation=cv2.INTER_NEAREST)),
        ("enhanced", cv2.resize(thresh5, (thresh5.shape[1] * scale_factor, thresh5.shape[0] * scale_factor), interpolation=cv2.INTER_NEAREST)),
    ]
    
    for name, img in methods:
        cv2.imwrite(f"{debug_dir}/{name}.png", img)
    
    print(f"✅ Debug images saved to {debug_dir}/")
    print(f"📊 ROI info:")
    print(f"   Size: {roi.shape}")
    print(f"   Position: ({x0}, {y0}) to ({x1}, {y1})")
    print(f"   Mean brightness: {np.mean(gray):.1f}")
    print()
    print("🔍 Check the debug images to see:")
    print("   1. If the elixir region is correctly positioned")
    print("   2. Which preprocessing method shows the digits most clearly")
    print("   3. If the digits are white on dark background or vice versa")
    print()
    print("💡 Tips:")
    print("   - If digits are barely visible, the elixir region might be wrong")
    print("   - If preprocessing looks good but detection fails, create digit templates")
    print("   - Run create_digit_templates.py to create templates from your game")

if __name__ == "__main__":
    main()
