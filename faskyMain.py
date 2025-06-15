import customtkinter as ctk

import time
import threading
import ctypes
import string
import os
import subprocess
import base64
import json
from typing import Dict
from dataclasses import dataclass

import pyautogui as pya
import keyboard as kb
from pynput import keyboard
from pynput.keyboard import Controller

import pywinstyles
from win32api import GetKeyState
from win32con import VK_CAPITAL
import win32clipboard as cp

# Assume these are imported from your existing files
from norepsText import noreps
from hPyT import opacity

# translator
from translate2 import TranslatorApp
translator = None
translatorObj = TranslatorApp()

"""# searchEasy
from searchEasy_V2.mainGui import searchEasyApp
searchEasyAppV = None
searchEasy = None
"""
# clipoboardManagerslots copy
from clipoboardManager.slots2 import ClipboardManager
slots = ClipboardManager()

#
"""from bot import BotControl
bot = BotControl()
botThread = threading.Thread(target=bot.run, daemon=True)"""
#from profiles.trayEMenu4 import run

loader_window = None
# Constants
CONFIG_FILE = "./.fasky_config.json"
DEFAULT_THEME = "dark"
DEFAULT_OPACITY = 0.92
translatorThread = None
@dataclass
class AppState:
    """Class to store application state"""
    char_dict: Dict[str, str] = None
    noreps_process = None
    to_upper_lower: bool = False
    maiusc_thread = None
    concatenate_mode: bool = False
    concatenated_text: str = ""
    translatorThread = None 
    translator: bool = False

class FaskyApp:
    def __init__(self):
        self.state = AppState()
        self.state.char_dict = {}
        self.kb_controller = Controller()
        self.tempo_ultimo_tasto = {}
        self.pressed_keys = {}
        self.tasti_premuti = set()
        self.keyboard_listener = None
        
        # Settings
        self.intervallo_minimo = 0.1  # Minimum interval between pressing the same key
        self.threshold = 0.3  # Time threshold for conversion to uppercase
        
        # Initialize the application
        self.init_resources()
        self.setup_ui()
        self.load_config()
        
    def init_resources(self):
        """Initialize required resources and files"""
        # Create noreps.exe if it doesn't exist
        exe_path = "noreps.exe"
        if not os.path.isfile(exe_path):
            with open(exe_path, "wb") as exe_file:
                exe_file.write(base64.b64decode(noreps))
        
        # Create default config if it doesn't exist
        if not os.path.exists(CONFIG_FILE):
            self.create_default_config()
            self.show_warning_message()
    
    def create_default_config(self):
        """Create a default configuration file"""
        config = {
            "theme": DEFAULT_THEME,
            "opacity": DEFAULT_OPACITY,
            "keyboard_mapping": {}
        }
        
        # Create default letter mappings
        for i in string.ascii_lowercase:
            config["keyboard_mapping"][i] = i.upper()
        
        # Add default number-to-symbol mappings
        symbol_map = {
            '0': '0',
            '1': '←',
            '2': '↑',
            '3': '↓',
            '4': '→',
            '5': 'Ω',
            '6': '≤',
            '7': '≥',
            '8': '♫',
            '9': '·',
        }
        
        for key, value in symbol_map.items():
            config["keyboard_mapping"][key] = value
        
        # Save the configuration
        with open(CONFIG_FILE, "w", encoding='utf-8') as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
        
        self.state.char_dict = config["keyboard_mapping"]
    
    def load_config(self):
        """Load configuration from file"""
        try:
            with open(CONFIG_FILE, "r", encoding='utf-8') as f:
                config = json.load(f)
                
            # Load theme and opacity
            ctk.set_appearance_mode(config.get("theme", DEFAULT_THEME))
            opacity_value = config.get("opacity", DEFAULT_OPACITY)
            opacity.set(self.window, opacity_value)
            
            # Load keyboard mappings
            self.state.char_dict = config.get("keyboard_mapping", {})
            
        except Exception as e:
            print(f"Error loading configuration: {e}")
            self.create_default_config()
    
    def save_config(self):
        """Save current configuration to file"""
        config = {
            "theme": ctk.get_appearance_mode().lower(),
            "opacity": self.opacity_slider.get(),
            "keyboard_mapping": self.state.char_dict
        }
        
        try:
            with open(CONFIG_FILE, "w", encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving configuration: {e}")
    
    def show_warning_message(self):
        """Show a warning message about usage with games"""
        ctypes.windll.user32.MessageBoxW(
            0, 
            "IMPORTANT\nUsing this program with games or software that prohibit virtual keyboards or macros may result in bans. "
            "The developer assumes no responsibility for any consequences. Stop the program when using such software.", 
            "WARNING", 
            48
        )
    
    def setup_ui(self):
        """Set up the user interface"""
        self.window = ctk.CTk()
        self.window.title("Fasky 2.0")
        self.window.protocol("WM_DELETE_WINDOW", self.on_close)
        
        # Set window style
        opacity.set(self.window, DEFAULT_OPACITY)
        ctk.set_appearance_mode(DEFAULT_THEME)
        pywinstyles.change_header_color(self.window, "black")
        pywinstyles.change_border_color(self.window, "black")
        
        # Try to load icon
        try:
            self.window.iconbitmap("./icon.ico")
        except:
            print("Icon file not found")
        
        # Create tab view
        self.tab_view = ctk.CTkTabview(self.window)
        self.tab_view.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Create tabs
        self.main_tab = self.tab_view.add("Main")
        self.settings_tab = self.tab_view.add("Settings")
        self.keyboard_tab = self.tab_view.add("Keyboard Map")
        self.about_tab = self.tab_view.add("About")
        
        # Setup main tab
        self.setup_main_tab()
        
        # Setup settings tab
        self.setup_settings_tab()
        
        # Setup keyboard mapping tab
        self.setup_keyboard_tab()
        
        # Setup about tab
        self.setup_about_tab()
    
    def setup_main_tab(self):
        """Set up the main tab with core functionality"""
        # Create frame for features
        features_frame = ctk.CTkFrame(self.main_tab)
        features_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title
        title_label = ctk.CTkLabel(
            features_frame, 
            text="Fasky Keyboard Utility", 
            font=ctk.CTkFont(size=20, weight="bold")
        )
        title_label.pack(pady=(15, 25))
        
        # Feature Switches
        # 1. Hold for Uppercase
        self.maiusc_rep_switch = ctk.CTkSwitch(
            features_frame, 
            text="QuickShift (press and hold)",
            command=self.toggle_maiusc_gestor
        )
        self.maiusc_rep_switch.pack(pady=10, padx=20, anchor="w")
        
        # Help text
        hold_help = ctk.CTkLabel(
            features_frame, 
            text="Hold any key to type its mapped character",
            font=("Segoe UI", 10),
            text_color="gray70"
        )
        hold_help.pack(pady=(0, 15), padx=40, anchor="w")
        
        # 2. Caps+Shift text conversion
        self.maiusc_switch = ctk.CTkSwitch(
            features_frame, 
            text="Case Converter (Caps Lock + Shift)",
            command=self.toggle_case_converter
        )
        self.maiusc_switch.pack(pady=10, padx=20, anchor="w")
        
        # Help text
        case_help = ctk.CTkLabel(
            features_frame, 
            text="Select text, press Caps Lock + Shift to change case",
            font=("Segoe UI", 10),
            text_color="gray70"
        )
        case_help.pack(pady=(0, 15), padx=40, anchor="w")
        
        # 3. Text concatenator
        self.concat_switch = ctk.CTkSwitch(
            features_frame, 
            text="Text Concatenator (Ctrl + Shift + C)",
            command=self.toggle_concatenator
        )
        self.concat_switch.pack(pady=10, padx=20, anchor="w")
        
        # Help text
        concat_help = ctk.CTkLabel(
            features_frame, 
            text="Combine multiple copied texts into one\nCtrl+Shift+C to start/stop, Ctrl+Esc+C to reset",
            font=("Segoe UI", 10),
            text_color="gray70"
        )
        concat_help.pack(pady=(0, 15), padx=40, anchor="w")
        
        # 4. Translator
        self.translator_switch = ctk.CTkSwitch(
            features_frame, 
            text="Translator (ctrl + f8)",
            command=self.toggle_translator
        )
        self.translator_switch.pack(pady=10, padx=20, anchor="w")
        
        # Help text
        translator_help = ctk.CTkLabel(
            features_frame, 
            text="Translate the selected text (EN⇄IT), Ctrl+F8 to translate",
            font=("Segoe UI", 10),
            text_color="gray70"
        )
        translator_help.pack(pady=(0, 15), padx=40, anchor="w")

        """# 5. searchSwitch
        self.searchSwitch = ctk.CTkSwitch(
            features_frame, 
            text="Search (Ctrl + Shift + S)",
            command=self.toggle_searchEasy
        )
        self.searchSwitch.pack(pady=10, padx=20, anchor="w")
        
        # Help text
        search_help = ctk.CTkLabel(
            features_frame, 
            text="Search easy and fast, Ctrl + Shift + S to start search",
            font=("Segoe UI", 10),
            text_color="gray70"
        )
        search_help.pack(pady=(0, 15), padx=40, anchor="w")"""

        # 6. solts copy
        self.slotsSwitch = ctk.CTkSwitch(
            features_frame, 
            text="Clipoboard Manager",
            command=self.toggle_clipoboardManager
        )
        self.slotsSwitch.pack(pady=10, padx=20, anchor="w")
        
        # Help text
        slots_help = ctk.CTkLabel(
            features_frame, 
            text="get more slots for copy and paste,\n ctrl+shift+<n> to copy, ctrl + <n> to paste",
            font=("Segoe UI", 10),
            text_color="gray70"
        )
        slots_help.pack(pady=(0, 15), padx=40, anchor="w")


        """# 7. bot
        self.bot = ctk.CTkSwitch(
            features_frame, 
            text="Control Bot",
            command=self.toggle_bot
        )
        self.bot.pack(pady=10, padx=20, anchor="w")
        
        # Help text
        bot_help = ctk.CTkLabel(
            features_frame, 
            text="telegram bot that allows you to send messages\nto your computer for easy access to your files and system",
            font=("Segoe UI", 10),
            text_color="gray70"
        )
        bot_help.pack(pady=(0, 15), padx=40, anchor="w")"""
        """# Status indicators
        status_frame = ctk.CTkFrame(features_frame)
        status_frame.pack(fill="x", padx=20, pady=(20, 10))
        
        self.status_label = ctk.CTkLabel(
            status_frame, 
            text="All features inactive", 
            font=("Segoe UI", 11),
            text_color="#ffa500"
        )
        self.status_label.pack(pady=10)"""
        
        # Quick access button to keyboard mapping
        map_button = ctk.CTkButton(
            features_frame, 
            text="Modify Key Mappings", 
            command=lambda: self.tab_view.set("Keyboard Map"),
            height=35
        )
        map_button.pack(pady=20)
    
    def setup_settings_tab(self):
        """Set up the settings tab"""
        settings_frame = ctk.CTkFrame(self.settings_tab)
        settings_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Theme setting
        theme_label = ctk.CTkLabel(
            settings_frame, 
            text="Theme:", 
            font=("Segoe UI", 12, "bold")
        )
        theme_label.pack(anchor="w", padx=20, pady=(20, 10))
        
        theme_var = ctk.StringVar(value=DEFAULT_THEME)
        
        theme_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        theme_frame.pack(fill="x", padx=20, pady=5)
        
        light_button = ctk.CTkRadioButton(
            theme_frame, 
            text="Light", 
            variable=theme_var, 
            value="light", 
            command=lambda: self.change_theme("light")
        )
        light_button.pack(side="left", padx=(0, 15))
        
        dark_button = ctk.CTkRadioButton(
            theme_frame, 
            text="Dark", 
            variable=theme_var, 
            value="dark", 
            command=lambda: self.change_theme("dark")
        )
        dark_button.pack(side="left", padx=(0, 15))
        
        system_button = ctk.CTkRadioButton(
            theme_frame, 
            text="System", 
            variable=theme_var, 
            value="system", 
            command=lambda: self.change_theme("system")
        )
        system_button.pack(side="left")
        
        # Window opacity
        opacity_label = ctk.CTkLabel(
            settings_frame, 
            text="Window Opacity:", 
            font=("Segoe UI", 12, "bold")
        )
        opacity_label.pack(anchor="w", padx=20, pady=(20, 10))
        
        self.opacity_slider = ctk.CTkSlider(
            settings_frame, 
            from_=0.5, 
            to=1.0, 
            number_of_steps=10,
            command=self.change_opacity
        )
        self.opacity_slider.set(DEFAULT_OPACITY)
        self.opacity_slider.pack(fill="x", padx=20, pady=5)
        
        opacity_value_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        opacity_value_frame.pack(fill="x", padx=20, pady=(0, 15))
        
        ctk.CTkLabel(opacity_value_frame, text="50%").pack(side="left")
        ctk.CTkLabel(opacity_value_frame, text="100%").pack(side="right")
        
        # Keyboard settings
        keyboard_label = ctk.CTkLabel(
            settings_frame, 
            text="Keyboard Settings:", 
            font=("Segoe UI", 12, "bold")
        )
        keyboard_label.pack(anchor="w", padx=20, pady=(20, 10))
        
        # Hold duration threshold
        threshold_frame = ctk.CTkFrame(settings_frame, fg_color="transparent")
        threshold_frame.pack(fill="x", padx=20, pady=5)
        
        threshold_label = ctk.CTkLabel(threshold_frame, text="Hold duration (sec):")
        threshold_label.pack(side="left")
        
        self.threshold_value = ctk.CTkLabel(threshold_frame, text=f"{self.threshold:.1f}")
        self.threshold_value.pack(side="right")
        
        self.threshold_slider = ctk.CTkSlider(
            settings_frame, 
            from_=0.1, 
            to=1.0, 
            number_of_steps=18,
            command=self.change_threshold
        )
        self.threshold_slider.set(self.threshold)
        self.threshold_slider.pack(fill="x", padx=20, pady=5)
        
        # Save settings button
        save_button = ctk.CTkButton(
            settings_frame, 
            text="Save Settings", 
            command=self.save_config,
            height=35
        )
        save_button.pack(pady=20)
        
        # Reset to defaults button
        reset_button = ctk.CTkButton(
            settings_frame, 
            text="Reset to Defaults", 
            command=self.reset_to_defaults,
            fg_color="gray30",
            height=35
        )
        reset_button.pack(pady=(0, 20))
    
    def setup_keyboard_tab(self):
        """Set up the keyboard mapping tab"""
        keyboard_frame = ctk.CTkFrame(self.keyboard_tab)
        keyboard_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Title and instructions
        title_label = ctk.CTkLabel(
            keyboard_frame, 
            text="Keyboard Mapping", 
            font=ctk.CTkFont(size=18, weight="bold")
        )
        title_label.pack(pady=(15, 5))
        
        instructions_label = ctk.CTkLabel(
            keyboard_frame, 
            text="Click on any key to change its mapping",
            font=("Segoe UI", 11),
            text_color="gray70"
        )
        instructions_label.pack(pady=(0, 15))
        
        # Scrollable frame for key mappings
        scroll_frame = ctk.CTkScrollableFrame(keyboard_frame, height=300)
        scroll_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Create a grid of buttons for key mappings
        self.mapping_buttons = {}
        row, col = 0, 0
        
        # Create buttons for letter mappings
        for char in string.ascii_lowercase:
            mapped_value = self.state.char_dict.get(char, char.upper())
            btn = ctk.CTkButton(
                scroll_frame, 
                text=f"{char} → {mapped_value}", 
                width=100,
                height=35,
                command=lambda k=char: self.open_key_mapping_dialog(k)
            )
            btn.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            self.mapping_buttons[char] = btn
            
            col += 1
            if col >= 3:
                col = 0
                row += 1
        
        # Create buttons for number mappings
        for num in string.digits:
            mapped_value = self.state.char_dict.get(num, num)
            btn = ctk.CTkButton(
                scroll_frame, 
                text=f"{num} → {mapped_value}", 
                width=100,
                height=35,
                command=lambda k=num: self.open_key_mapping_dialog(k)
            )
            btn.grid(row=row, column=col, padx=5, pady=5, sticky="nsew")
            self.mapping_buttons[num] = btn
            
            col += 1
            if col >= 3:
                col = 0
                row += 1
        
        # Configure the grid
        for i in range(3):
            scroll_frame.grid_columnconfigure(i, weight=1)
        
        # Bottom buttons
        buttons_frame = ctk.CTkFrame(keyboard_frame, fg_color="transparent")
        buttons_frame.pack(fill="x", pady=20)
        
        reset_keys_button = ctk.CTkButton(
            buttons_frame, 
            text="Reset All Keys", 
            command=self.reset_all_key_mappings,
            fg_color="gray30",
            height=35
        )
        reset_keys_button.pack(side="left", padx=20, fill="x", expand=True)
        
        save_mappings_button = ctk.CTkButton(
            buttons_frame, 
            text="Save Mappings", 
            command=self.save_config,
            height=35
        )
        save_mappings_button.pack(side="right", padx=20, fill="x", expand=True)
    
    def setup_about_tab(self):
        """Set up the about tab"""
        about_frame = ctk.CTkFrame(self.about_tab)
        about_frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        # App name and version
        title_label = ctk.CTkLabel(
            about_frame, 
            text="Fasky 2.0", 
            font=ctk.CTkFont(size=24, weight="bold")
        )
        title_label.pack(pady=(25, 5))
        
        version_label = ctk.CTkLabel(
            about_frame, 
            text="Advanced Keyboard Utility", 
            font=("Segoe UI", 14)
        )
        version_label.pack(pady=(0, 25))
        
        # Features list
        features_label = ctk.CTkLabel(
            about_frame, 
            text="Features:", 
            font=("Segoe UI", 14, "bold"),
            anchor="w"
        )
        features_label.pack(anchor="w", padx=25, pady=(10, 5))
        
        features_text = """• Hold keys to transform them to custom characters
        • Change text case with Caps Lock + Shift
• Concatenate clipboard content
• Customize key mappings
• Modern, customizable interface"""
        
        features_content = ctk.CTkLabel(
            about_frame, 
            text=features_text, 
            font=("Segoe UI", 12),
            anchor="w",
            justify="left"
        )
        features_content.pack(anchor="w", padx=25, pady=(0, 15))
        
        # Instructions
        instructions_label = ctk.CTkLabel(
            about_frame, 
            text="Usage:", 
            font=("Segoe UI", 14, "bold"),
            anchor="w"
        )
        instructions_label.pack(anchor="w", padx=25, pady=(10, 5))
        
        instructions_text = """1. Enable desired features in the Main tab
2. Customize key mappings in the Keyboard Map tab
3. Adjust application settings in the Settings tab

Note: Do not use with applications that prohibit keyboard macros"""
        
        instructions_content = ctk.CTkLabel(
            about_frame, 
            text=instructions_text, 
            font=("Segoe UI", 12),
            anchor="w",
            justify="left"
        )
        instructions_content.pack(anchor="w", padx=25, pady=(0, 15))
        
        # Copyright
        copyright_label = ctk.CTkLabel(
            about_frame, 
            text="© 2025 Fasky", 
            font=("Segoe UI", 10),
            text_color="gray70"
        )
        copyright_label.pack(side="bottom", pady=15)
    
    def open_key_mapping_dialog(self, key):
        """Open dialog to modify a key mapping"""
        dialog = ctk.CTkToplevel(self.window)
        dialog.title(f"Modify Key: {key}")
        dialog.attributes('-topmost', 'true')
        dialog.geometry("300x200")
        dialog.resizable(False, False)
        
        # Try to set the icon
        try:
            dialog.after(200, lambda: dialog.iconbitmap("./icon.ico"))
        except:
            pass
        
        # Current mapping
        current_value = self.state.char_dict.get(key, key.upper())
        
        # Dialog content
        frame = ctk.CTkFrame(dialog)
        frame.pack(fill="both", expand=True, padx=20, pady=20)
        
        title_label = ctk.CTkLabel(
            frame, 
            text=f"Modify mapping for key: {key}", 
            font=("Segoe UI", 14, "bold")
        )
        title_label.pack(pady=(0, 15))
        
        input_frame = ctk.CTkFrame(frame, fg_color="transparent")
        input_frame.pack(fill="x", pady=10)
        
        input_label = ctk.CTkLabel(input_frame, text="New value:")
        input_label.pack(side="left", padx=(0, 10))
        
        input_entry = ctk.CTkEntry(input_frame, width=150)
        input_entry.insert(0, current_value)
        input_entry.pack(side="right")
        
        # Buttons
        buttons_frame = ctk.CTkFrame(frame, fg_color="transparent")
        buttons_frame.pack(fill="x", pady=(20, 0))
        
        cancel_button = ctk.CTkButton(
            buttons_frame, 
            text="Cancel", 
            command=dialog.destroy,
            fg_color="gray30",
            width=80
        )
        cancel_button.pack(side="left", padx=(0, 10))
        
        save_button = ctk.CTkButton(
            buttons_frame, 
            text="Save", 
            command=lambda: self.save_key_mapping(key, input_entry.get(), dialog),
            width=80
        )
        save_button.pack(side="right")
    
    def save_key_mapping(self, key, value, dialog):
        """Save a key mapping and update the UI"""
        if value:  # Only save if not empty
            self.state.char_dict[key] = value
            
            # Update the button text
            if key in self.mapping_buttons:
                self.mapping_buttons[key].configure(text=f"{key} → {value}")
            
            dialog.destroy()
            self.save_config()
    
    def reset_all_key_mappings(self):
        """Reset all key mappings to defaults"""
        # Create default key mappings
        for i in string.ascii_lowercase:
            self.state.char_dict[i] = i.upper()
        
        # Add default number-to-symbol mappings
        symbol_map = {
            '0': '0',
            '1': '←',
            '2': '↑',
            '3': '↓',
            '4': '→',
            '5': 'Ω',
            '6': '≤',
            '7': '≥',
            '8': '♫',
            '9': '·',
        }
        
        for key, value in symbol_map.items():
            self.state.char_dict[key] = value
        
        # Update UI
        for key, btn in self.mapping_buttons.items():
            mapped_value = self.state.char_dict.get(key, key.upper())
            btn.configure(text=f"{key} → {mapped_value}")
        
        self.save_config()
    
    def change_theme(self, theme):
        """Change the application theme"""
        ctk.set_appearance_mode(theme)
        self.save_config()
    
    def change_opacity(self, value):
        """Change the window opacity"""
        opacity.set(self.window, value)
        self.save_config()
    
    def change_threshold(self, value):
        """Change the hold threshold duration"""
        self.threshold = value
        self.threshold_value.configure(text=f"{value:.1f}")
        self.save_config()
    
    def reset_to_defaults(self):
        """Reset all settings to default values"""
        # Reset theme and opacity
        ctk.set_appearance_mode(DEFAULT_THEME)
        opacity.set(self.window, DEFAULT_OPACITY)
        self.opacity_slider.set(DEFAULT_OPACITY)
        
        # Reset threshold
        self.threshold = 0.3
        self.threshold_slider.set(0.3)
        self.threshold_value.configure(text="0.3")
        
        # Reset key mappings
        self.reset_all_key_mappings()
        
        # Save the configuration
        self.save_config()
    
    def toggle_maiusc_gestor(self):
        """Toggle the hold-to-transform feature"""
        if self.maiusc_rep_switch.get():
            self.start_listener()
            #self.update_status("Hold-to-transform active")
        else:
            self.stop_listener()
            #self.update_status()
    
    def toggle_case_converter(self):
        """Toggle the case converter feature"""
        if self.maiusc_switch.get():
            self.state.to_upper_lower = True
            self.state.maiusc_thread = threading.Thread(
                target=self.maiusc_func, 
                daemon=True
            )
            self.state.maiusc_thread.start()
            #self.update_status("Case converter active")
        else:
            self.state.to_upper_lower = False
            #self.update_status()
    
    def toggle_concatenator(self):
        """Toggle the text concatenator feature"""
        if self.concat_switch.get():
            self.state.concatenate_mode = True
            concatenate_thread = threading.Thread(
                target=self.concatenate_text_func, 
                daemon=True
            )
            concatenate_thread.start()
            #self.update_status("Text concatenator active")
        else:
            self.state.concatenate_mode = False
            #self.update_status()

    def toggle_translator(self):
        global translatorThread, translatorObj
        if self.translator_switch.get():
            self.state.translator = True
            """translatorThread = threading.Thread(
                target=translatorObj.start,
                daemon=True
            )"""
            #translatorThread.start()
            translatorObj = None
            translatorObj = TranslatorApp()
            translatorObj.start()
            #self.update_status("Transaltor active")
        else:
            translatorObj.stop()
            translatorThread = None
            self.state.translator = False            
            #self.update_status()

    """def toggle_searchEasy(self):
        global searchEasyAppV
        if self.searchSwitch.get():
            self.show_loader()
            from searchEasy_V2.mainGui import initialize
            initialize()
            self.state.searchEasy = True
            self.searchEasyAppV = searchEasyApp()
            #self.searchEasyAppV.show_loader()
            self.hide_loader()
            self.searchEasyAppV.start()
            #self.searchEasyAppV.hide_loader()
            #self.update_status("SearchEasy active")
        
        else:
            print("Stopping searchEasy")
            self.state.searchEasy = False
            self.searchEasyAppV.stop()
            searchEasyAppV = None
            #self.update_status()"""
        
    def toggle_clipoboardManager(self):
        global slots
        if self.slotsSwitch.get():
            t = threading.Thread(
                target=slots.start, 
                daemon=True
            )
            self.show_loader()
            t.start()
            self.state.slots = True
            self.hide_loader()
            #self.update_status("Slots Copy active")
        
        else:
            print("Stopping Slots Copy")
            self.state.slots = False
            slots.stop()
            #self.update_status()

    """def toggle_bot(self):
        global bot, botThread

        if self.bot.get():
            self.show_loader()
            try:
                if not botThread.is_alive():
                    print("Avvio del bot...")
                    botThread.start()
                    self.state.bot = True
                else:
                    print("Bot già attivo.")
            except Exception as e:
                print(f"Errore durante l'avvio del bot: {e}")
            finally:
                self.hide_loader()

        else:
            print("Arresto del bot...")
            try:
                self.state.bot = False
                if hasattr(bot, "stop"):
                    bot.stop()  # Fermare polling o cleanup
                if botThread.is_alive():
                    botThread.join(timeout=5)  # Aspetta la chiusura del thread
            except Exception as e:
                print(f"Errore durante l'arresto del bot: {e}")
            
            # Reinizializza il bot e il thread per un riavvio pulito
            bot = BotControl()
            botThread = threading.Thread(
                target=bot.run,
                daemon=True
            )
        """
    """
    def update_status(self, message=None):
        "Update the status label with active features"
        active_features = []
        
        if self.maiusc_rep_switch.get():
            active_features.append("Hold-to-transform")
        
        if self.maiusc_switch.get():
            active_features.append("Case converter")
        
        if self.concat_switch.get():
            active_features.append("Text concatenator")
        
        if message:
            self.status_label.configure(text=message, text_color="#4CAF50")
        elif active_features:
            self.status_label.configure(
                text=f"Active features: {', '.join(active_features)}", 
                text_color="#4CAF50"
            )
        else:
            self.status_label.configure(
                text="All features inactive", 
                text_color="#ffa500"
            )
    """
    
    def start_listener(self):
        """Start the keyboard listener for the hold-to-transform feature"""
        if self.state.noreps_process is None:
            # Start noreps.exe
            self.state.noreps_process = subprocess.Popen(
                ["noreps.exe"], 
                creationflags=subprocess.CREATE_NO_WINDOW
            )
            
            # Start keyboard listener
            self.keyboard_listener = keyboard.Listener(
                on_press=self.on_press,
                on_release=self.on_release
            )
            self.keyboard_listener.daemon = True
            self.keyboard_listener.start()
    
    def stop_listener(self):
        """Stop the keyboard listener"""
        if self.state.noreps_process is not None:
            self.state.noreps_process.terminate()
            self.state.noreps_process.wait()
            self.state.noreps_process = None
        
        if self.keyboard_listener is not None:
            self.keyboard_listener.stop()
            self.keyboard_listener = None
    
    def on_press(self, key):
        """Handle key press events"""
        try:
            if hasattr(key, 'char') and key.char:
                char = key.char
                current_time = time.time()

                # Check if the key is alphanumeric
                if char.isalnum():
                    # If the key wasn't pressed recently
                    if (char not in self.tempo_ultimo_tasto or
                            (current_time - self.tempo_ultimo_tasto[char]) > self.intervallo_minimo):
                        if char not in self.tasti_premuti:
                            # Record the press time
                            self.pressed_keys[key] = current_time
                            self.tasti_premuti.add(char)
                            self.tempo_ultimo_tasto[char] = current_time
        except AttributeError:
            pass
    
    def on_release(self, key):
        """Handle key release events"""
        try:
            if key in self.pressed_keys:
                press_duration = time.time() - self.pressed_keys[key]

                if hasattr(key, 'char') and key.char:
                    char = key.char
                    # If press duration is long enough, convert to mapped character
                    if press_duration >= self.threshold:
                        self.kb_controller.type('\b')  # Delete the original character
                        try:
                            # Type the mapped character
                            self.kb_controller.type(self.state.char_dict[char])
                        except:
                            # Fall back to uppercase if no mapping exists
                            self.kb_controller.type(char.upper())
                
                # Clean up key tracking
                del self.pressed_keys[key]
                if hasattr(key, 'char') and key.char:
                    self.tasti_premuti.discard(char)
                    if char in self.tempo_ultimo_tasto:
                        del self.tempo_ultimo_tasto[char]
        except AttributeError:
            pass
    
    def maiusc_func(self):
        """Function to convert text case when Caps Lock + Shift is pressed"""
        allowed_keys = {'bloc maius', 'maiusc'}
        
        while self.state.to_upper_lower:
            try:
                # Check if the key combination is pressed
                current_keys = set(str(kb.get_hotkey_name()).split('+'))
                if allowed_keys == current_keys:
                    print("Key combination found!")
                    # Wait for keys to be released
                    while self.state.to_upper_lower and allowed_keys == set(str(kb.get_hotkey_name()).split('+')):
                        time.sleep(0.01)
                    
                    # Perform text case conversion
                    print("Executing conversion")
                    pya.hotkey("ctrl", "c")
                    time.sleep(0.03)
                    
                    cp.OpenClipboard()
                    try:
                        data = cp.GetClipboardData()
                        if data:
                            # Convert based on Caps Lock state
                            output_text = data.upper() if GetKeyState(VK_CAPITAL) == 1 else data.lower()
                            cp.EmptyClipboard()
                            cp.SetClipboardData(cp.CF_UNICODETEXT, output_text)
                    except Exception as e:
                        print(f"Clipboard error: {e}")
                    finally:
                        cp.CloseClipboard()
                    
                    pya.hotkey("ctrl", "v")
                    time.sleep(0.1)  # Small pause to prevent repetitions
            except Exception as e: 
                print(f"General error: {e}")
            
            # Short sleep to reduce CPU usage
            time.sleep(0.05)
    
    def concatenate_text_func(self):
        """Function to concatenate copied text when Ctrl+Shift+C is pressed"""
        is_concatenating = False
        
        while self.state.concatenate_mode:
            try:
                # Start concatenating when Ctrl+Shift+C is first pressed
                if kb.is_pressed('ctrl+shift+c') and not is_concatenating:
                    is_concatenating = True
                    cp.OpenClipboard()
                    cp.EmptyClipboard()
                    cp.CloseClipboard()
                    self.state.concatenated_text = ""
                    print("Starting text concatenation.")
                    time.sleep(1)  # Prevent immediate triggering
                
                # If concatenation is active
                if is_concatenating:
                    # Get text from clipboard
                    cp.OpenClipboard()
                    try:
                        data = cp.GetClipboardData()
                        # Add current text to concatenated text if it's not already there
                        if data and data != self.state.concatenated_text:
                            self.state.concatenated_text += data + " "  # Add space to separate text
                            cp.EmptyClipboard()
                            cp.SetClipboardData(cp.CF_UNICODETEXT, self.state.concatenated_text)
                            print(f"Concatenated text: {self.state.concatenated_text}")
                    except Exception as e:
                        print(f"Clipboard error: {e}")
                    finally:
                        cp.CloseClipboard()
                
                # Stop concatenating when Ctrl+Shift+C is pressed again
                if kb.is_pressed('ctrl+shift+c') and is_concatenating:
                    print("Stopped text concatenation.")
                    is_concatenating = False
                    time.sleep(1)  # Pause to prevent continuous triggers
                
                # Reset concatenation when Ctrl+Esc+C is pressed
                if kb.is_pressed('ctrl+esc+c'):
                    self.state.concatenated_text = ""
                    is_concatenating = False
                    print("Concatenation reset.")
                    time.sleep(1)  # Pause to prevent continuous triggers
            
            except Exception as e:
                print(f"General error: {e}")
            
            time.sleep(0.05)  # Short sleep to reduce CPU usage
    
    def on_close(self):
        """Handle window close event"""
        # Stop all active features
        self.state.to_upper_lower = False
        self.state.concatenate_mode = False
        self.state.translator = False
        self.stop_listener()
        
        # Save config
        self.save_config()
        
        # Destroy the window
        self.window.destroy()
    
    def run(self):
        """Run the application"""
        self.window.mainloop()

    def show_loader(self):
        global loader_window
        if loader_window is not None:
            return

        loader_window = ctk.CTkToplevel()
        loader_window.overrideredirect(True)
        loader_window.attributes("-topmost", True)
        loader_window.geometry("60x60+10+10")
        loader_window.configure(bg="black")

        spinner_label = ctk.CTkLabel(loader_window, text="⠋", text_color="white", font=("Segoe UI", 30))
        spinner_label.pack(expand=True)

        def animate():
            dots = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
            i = 0
            while loader_window:
                spinner_label.configure(text=dots[i])
                i = (i + 1) % len(dots)
                time.sleep(0.1)

        threading.Thread(target=animate, daemon=True).start()

    def hide_loader(self):
        global loader_window
        if loader_window:
            loader_window.destroy()
            loader_window = None
# Entry point
if __name__ == "__main__":
    app = FaskyApp()
    app.run()

