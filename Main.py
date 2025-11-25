import tkinter as tk
from tkinter import ttk, messagebox
import configparser
import time
import sys
from ahk import AHK
import keyboard
import os
import cv2
import numpy as np
import pyautogui
import pytesseract
from difflib import SequenceMatcher
import platform

def resource_path(*parts):
    if getattr(sys, "frozen", False):
        base = getattr(sys, "_MEIPASS", None) or os.path.abspath(os.path.dirname(sys.executable))
    else:
        base = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base, *parts)

if getattr(sys, "frozen", False):
    if platform.system() == "Windows":
        base_persist = os.path.join(os.getenv("APPDATA") or os.path.expanduser("~"), "FallenSnipe")
    else:
        base_persist = os.path.join(os.path.expanduser("~"), ".fallensnipe")
else:
    base_persist = resource_path()

BASE_DIR = resource_path()
SETTINGS_DIR = os.path.join(base_persist, "settings")
SETTINGS_FILE = os.path.join(SETTINGS_DIR, "settings.ini")
os.makedirs(SETTINGS_DIR, exist_ok=True)

merchantfound = False
config = configparser.ConfigParser()

ahk = None
ahk_exe_candidate = resource_path("scripts", "AutoHotkey.exe")
try:
    if os.path.exists(ahk_exe_candidate):
        ahk = AHK(executable_path=ahk_exe_candidate)
    else:
        ahk = AHK()
except Exception:
    ahk = None

tess_env = os.environ.get("TESSERACT_CMD")
if tess_env:
    pytesseract.pytesseract.tesseract_cmd = tess_env
else:
    bundled_tesseract = resource_path("tesseract", "tesseract.exe")
    if os.path.exists(bundled_tesseract):
        pytesseract.pytesseract.tesseract_cmd = bundled_tesseract

orb = cv2.ORB_create(nfeatures=800)
bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)

def orb_similarity(img1, img2):
    try:
        g1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
        g2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
    except Exception:
        return 0
    kp1, des1 = orb.detectAndCompute(g1, None)
    kp2, des2 = orb.detectAndCompute(g2, None)
    if des1 is None or des2 is None:
        return 0
    matches = bf.match(des1, des2)
    good = [m for m in matches if m.distance < 60]
    return len(good)

def detectimage(filename, threshold=10, images_folder="images"):
    screenshot = pyautogui.screenshot()
    screenshot_np = cv2.cvtColor(np.array(screenshot), cv2.COLOR_BGR2RGB)
    image_path = resource_path(images_folder, filename)
    template = cv2.imread(image_path)
    if template is None:
        raise FileNotFoundError(f"Could not load template: {image_path}")
    score = orb_similarity(screenshot_np, template)
    print(f"[MATCH] {filename} → {score}")
    if score >= threshold:
        print(f"[FOUND] {filename} with score {score}")
        return True
    else:
        print("[NOT FOUND] No match")
        return False

def detecttext(target_text, threshold=0.7, region=None):
    if region:
        x1, y1, x2, y2 = region
        width = x2 - x1
        height = y2 - y1
        screenshot = pyautogui.screenshot(region=(x1, y1, width, height))
    else:
        screenshot = pyautogui.screenshot()
    screenshot_np = cv2.cvtColor(np.array(screenshot), cv2.COLOR_BGR2RGB)
    extracted_text = pytesseract.image_to_string(screenshot_np)
    print("[OCR OUTPUT]")
    print(extracted_text)
    extracted_lower = extracted_text.lower()
    target_lower = target_text.lower()
    if target_lower in extracted_lower:
        print(f"[FOUND] Exact match for '{target_text}'")
        return True
    ratio = SequenceMatcher(None, target_lower, extracted_lower).ratio()
    print(f"[SIMILARITY] {ratio:.2f}")
    if ratio >= threshold:
        print(f"[FOUND] Similar enough to '{target_text}'")
        return True
    print(f"[NOT FOUND] '{target_text}' not detected")
    return False

print("Macro Logs:")

def add_option(parent, section, text, max_value, bg_color):
    frame = tk.Frame(parent, bg=bg_color)
    frame.pack(anchor="w", pady=2)
    var = tk.IntVar()
    cb = tk.Checkbutton(frame, text=text, variable=var, bg=bg_color)
    cb.pack(side="left")
    entry = tk.Entry(frame, width=6)
    entry.insert(0, "Amount")
    entry.pack(side="left", padx=5)
    max_label = tk.Label(frame, text=f"Max {max_value}", bg=bg_color)
    max_label.pack(side="left")
    return {"section": section, "name": text, "var": var, "entry": entry}

def save_settings():
    for opt in all_options:
        section = opt["section"]
        if section not in config:
            config[section] = {}
        config[section][opt["name"]] = f"{opt['var'].get()}|{opt['entry'].get()}"
    if "OPTIONS" not in config:
        config["OPTIONS"] = {}
    config["OPTIONS"]["Mode"] = mode_var.get()
    config["OPTIONS"]["MerchantCheck"] = merchant_entry.get()
    config["OPTIONS"]["DetectionMode"] = detection_var.get()
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        config.write(f)
    print("Settings saved to", SETTINGS_FILE)

def load_settings():
    print("Loading Settings")
    if not os.path.exists(SETTINGS_FILE):
        return
    config.read(SETTINGS_FILE, encoding="utf-8")
    for opt in all_options:
        section = opt["section"]
        if section in config and opt["name"] in config[section]:
            val = config[section][opt["name"]]
            try:
                checked, amount = val.split("|", 1)
                opt["var"].set(int(checked))
                opt["entry"].delete(0, tk.END)
                opt["entry"].insert(0, amount)
            except ValueError:
                pass
    if "OPTIONS" in config:
        if "Mode" in config["OPTIONS"]:
            mode_var.set(config["OPTIONS"]["Mode"])
        if "MerchantCheck" in config["OPTIONS"]:
            merchant_entry.delete(0, tk.END)
            merchant_entry.insert(0, config["OPTIONS"]["MerchantCheck"])
        if "DetectionMode" in config["OPTIONS"]:
            detection_var.set(config["OPTIONS"]["DetectionMode"])
    print("Settings loaded from", SETTINGS_FILE)

# --- UI ---
ui = tk.Tk()
ui.title("FallenSnipe Prerelease 1")
ui.geometry("500x700")

notebook = ttk.Notebook(ui)
notebook.pack(fill="both", expand=True)

all_options = []

# --- Mari Tab ---
tab1 = tk.Frame(notebook, bg="yellow")
notebook.add(tab1, text="Mari")
tk.Label(tab1, text="MARI SETTINGS:", font=("Arial", 14, "bold"), bg="yellow").pack(pady=10)
mari_frame = tk.Frame(tab1, bg="yellow")
mari_frame.pack(padx=20, pady=10)

mari_options = [
    ("Buy Lucky Potions", 25),
    ("Buy Lucky Potion L", 10),
    ("Buy Lucky Potions XL", 5),
    ("Buy Speed Potions", 25),
    ("Buy Speed Potion L", 10),
    ("Buy Speed Potion XL", 5),
    ("Buy Mixed Potions", 25),
    ("Buy Fortune Spoid I", 4),
    ("Buy Fortune Spoid II", 4),
    ("Buy Fortune Spoid III", 1),
    ("Buy Gear A", 1),
    ("Buy Gear B", 1),
    ("Buy Lucky Penny", 1),
    ("Buy Void Coin", 2),
]
for text, max_val in mari_options:
    all_options.append(add_option(mari_frame, "MARI", text, max_val, "yellow"))

# --- Jester Tab ---
tab2 = tk.Frame(notebook, bg="purple")
notebook.add(tab2, text="Jester")
tk.Label(tab2, text="JESTER SETTINGS:", font=("Arial", 14, "bold"), bg="purple", fg="white").pack(pady=10)
jester_frame = tk.Frame(tab2, bg="purple")
jester_frame.pack(padx=20, pady=10)

jester_options = [
    ("Buy Lucky Potions", 45),
    ("Buy Speed Potions", 45),
    ("Buy Random Potion Sack", 10),
    ("Buy Stella's Star", 1),
    ("Buy Rune of Wind", 1),
    ("Buy Rune of Frost", 1),
    ("Buy Rune of Rainstorm", 1),
    ("Buy Rune of Hell", 1),
    ("Buy Rune of Galaxy", 1),
    ("Buy Rune of Corruption", 1),
    ("Buy Rune of Nothing", 1),
    ("Buy Rune of Everything", 1),
    ("Buy Strange Potion I", 25),
    ("Buy Strange Potion II", 25),
    ("Buy Stella's Candle", 5),
    ("Buy Oblivion Potion", 1),
    ("Buy Potion of Bound", 1),
    ("Buy Heavenly Potion", 1),
]
for text, max_val in jester_options:
    all_options.append(add_option(jester_frame, "JESTER", text, max_val, "purple"))

tab3 = tk.Frame(notebook, bg="lightgray")
notebook.add(tab3, text="Options")
tk.Label(tab3, text="OPTIONS:", font=("Arial", 14, "bold"), bg="lightgray").pack(pady=10)

options_frame = tk.Frame(tab3, bg="lightgray")
options_frame.pack(padx=20, pady=10, anchor="w")

mode_var = tk.StringVar(value="Autobuy")
tk.Label(options_frame, text="Mode:", bg="lightgray").grid(row=0, column=0, sticky="w")
mode_dropdown = ttk.Combobox(options_frame, textvariable=mode_var, values=["Autobuy", "Notify"], state="readonly", width=10)
mode_dropdown.grid(row=0, column=1, padx=5)
tk.Button(options_frame, text="?", command=lambda: messagebox.showinfo("Mode Help", "Autobuy: The macro will do things such as anti-afk and using merchant teleporters \nNotify: Toasts a window notification if a merchant is detected.")).grid(row=0, column=2)

tk.Label(options_frame, text="Merchant Check every (seconds):", bg="lightgray").grid(row=1, column=0, sticky="w")
merchant_entry = tk.Entry(options_frame, width=10)
merchant_entry.grid(row=1, column=1, padx=5)

detection_var = tk.StringVar(value="Teleport")
tk.Label(options_frame, text="Detection Mode:", bg="lightgray").grid(row=2, column=0, sticky="w")
detection_dropdown = ttk.Combobox(options_frame, textvariable=detection_var, values=["Teleport", "Tracker"], state="readonly", width=10)
detection_dropdown.grid(row=2, column=1, padx=5)
tk.Button(options_frame, text="?", command=lambda: messagebox.showinfo("Detection Mode Help", "Teleport: Constantly use Merchant Teleporter and hope for a merchant to spawn (NOT COMPATIBLE WITH NOTIFY MACRO MODE)\nTracker: Detect merchants using Merchant Tracker item (In Autobuy mode, it will then teleport and buy items, in notify mode, it will toast a windows notification).")).grid(row=2, column=2)

load_settings()

# --- ALL CODING IS AFTER HERE ---
def useitem(item):
    print("Searching for item: ", item)
    if ahk is None:
        return
    ahk.mouse_move(22, 509, speed=5, relative=False)
    time.sleep(0.1)
    ahk.click()
    time.sleep(0.1)
    ahk.mouse_move(1276, 338, speed=5, relative=False)
    time.sleep(0.1)
    ahk.click()
    time.sleep(0.1)
    ahk.mouse_move(834, 367, speed=5, relative=False)
    time.sleep(0.1)
    ahk.click()
    time.sleep(0.3)
    keyboard.write(item)
    time.sleep(0.3)
    ahk.mouse_move(1701, 827, speed=5, relative=False)
    time.sleep(0.1)
    ahk.click()
    time.sleep(0.3)
    ahk.mouse_move(854, 477, speed=5, relative=False)
    time.sleep(0.1)
    ahk.click()
    time.sleep(0.1)
    ahk.mouse_move(684, 580, speed=5, relative=False)
    time.sleep(0.1)
    ahk.click()
    time.sleep(0.4)

def enabletracker():
    useitem("Merchant Tracker")
    time.sleep(1)
    found = detecttext("Enobled", threshold=0.56, region=(1699, 805, 1851, 858))
    if ahk:
        ahk.mouse_move(22, 509, speed=10, relative=False)
        time.sleep(0.1)
        ahk.click()
    if found:
        print("Merchant Tracker Enabled")
    else:
        print("Merchant Tracker wasnt enabled — retrying")
        enabletracker()

def exit(event=None):
    ui.destroy()

def press(key):
    if ahk:
        ahk.send(key)

def Checkformerchants():
    mode = detection_var.get()
    macromode = mode_var.get()
    timebetweenchecks = merchant_entry.get()
    try:
        time.sleep(max(1, int(timebetweenchecks)))
    except Exception:
        time.sleep(1)
    if macromode == "Autobuy" and mode == "Teleport":
        useitem("Merchant Teleporter")
        time.sleep(2)
        for i in range(5):
            press("o")
            time.sleep(0.08)
        time.sleep(0.1)
        press("e")
        time.sleep(4)
        textdetection = detecttext("Mori", threshold=0.66)
        imagedetection = detectimage("mariimage.png", threshold=7)
        textdetection2 = detecttext("Jester", threshold=0.65)
        imagedetection2 = detectimage("jesterimage.png", threshold=6)
        global merchantfound
        if (textdetection and imagedetection) or (textdetection2 and imagedetection2):
            merchantfound = True
        if merchantfound:
            opentextfound = detecttext("Open", threshold=0.8, region=(509, 908, 1104, 968))
            if opentextfound:
                print("Merchant Found")

def OnStart(event=None):
    save_settings()
    print("Macro Started")
    print("Sleeping 2 seconds")
    mode = detection_var.get()
    time.sleep(2)
    print("slept")
    if mode == "Tracker":
        print("Tracker mode enabled: Enabling Merchant Tracker")
        enabletracker()
    Checkformerchants()

def on_close():
    save_settings()
    ui.destroy()

ui.protocol("WM_DELETE_WINDOW", on_close)
ui.bind_all("<F1>", OnStart)
ui.bind_all("<F2>", exit)
ui.mainloop()
