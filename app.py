# commented by claude
import os
import json
import tkinter as tk
from customtkinter import *
from tkinter import ttk, filedialog, messagebox, simpledialog
import webbrowser
import subprocess
import sys
import re
from threading import Thread
import os
import sys
import re
import winreg
import enum
import socket
import threading
import time
import pystray
from PIL import Image

#from trayEMenu4 import get_profiles, change_profile causa errore di importazione circolare quindi bisogna reimportare il modulo
import trayEMenu4
from faskyMain import FaskyApp

PRIMARY_COLOR = "#1f538d"

class ReadMode(enum.Enum):
    KEY = 1
    VALUE = 2

class AppFinder:

    def __init__(self, auto_scan=False):
        self.installed_apps = []
        if auto_scan:
            self.find_apps()

    def find_apps(self, callback=None):
        """
        Cerca le applicazioni installate nel sistema.
        
        Args:
            callback: Funzione da chiamare con il progresso della scansione (opzionale).
                     Viene chiamata con (numero_app_trovate, messaggio).
        
        Returns:
            list: Lista delle applicazioni trovate.
        """
        if sys.platform.startswith('win'):
            # cerca nelle cartelle tipiche e nel registro
            self.installed_apps = self._find_windows_apps(callback)
        elif sys.platform.startswith('darwin'):
            self.installed_apps = self._find_macos_apps(callback)
        elif sys.platform.startswith('linux'):
            self.installed_apps = self._find_linux_apps(callback)
        else:
            self.installed_apps = []
            
        if callback:
            callback(len(self.installed_apps), f"Trovate {len(self.installed_apps)} applicazioni")
            
        return self.installed_apps
    
    def _find_windows_apps(self, callback=None):
        """
        Trova applicazioni installate su Windows.
        
        Args:
            callback: Funzione da chiamare con il progresso della scansione.
        
        Returns:
            list: Lista delle applicazioni trovate.
        """
        apps = []
        
        # Luoghi comuni dove trovare i programmi in Windows
        common_locations = [
            os.path.join(os.environ.get('ProgramFiles', 'C:\\Program Files')),
            os.path.join(os.environ.get('ProgramFiles(x86)', 'C:\\Program Files (x86)')),
            os.path.join(os.environ.get('APPDATA', ''), '..', 'Local', 'Programs')
        ]
        
        # Cerca file .exe nelle cartelle
        for location in common_locations:
            if os.path.exists(location):
                for root, dirs, files in os.walk(location):
                    for file in files:
                        if file.endswith('.exe'):
                            full_path = os.path.join(root, file)
                            apps.append({
                                'name': file.replace('.exe', ''),
                                'path': full_path
                            })
                            # Notifica del progresso se richiesto
                            if callback and len(apps) % 20 == 0:
                                callback(len(apps), f"Scansione in corso: trovate {len(apps)} applicazioni")
                            # Limita la ricerca per non rallentare troppo
                            if len(apps) > 150:
                                break
                    if len(apps) > 150:
                        break
        
        # Aggiungi anche le applicazioni dal registro di sistema
        registry_apps = self._find_windows_registry_apps(callback)
        apps.extend(registry_apps)
        
        # Ordina per nome
        apps.sort(key=lambda x: x['name'].lower())
        return apps
    
    def _find_windows_registry_apps(self, callback=None):
        """
        Trova applicazioni installate su Windows tramite il registro di sistema.
        
        Args:
            callback: Funzione da chiamare con il progresso della scansione.
        
        Returns:
            list: Lista delle applicazioni trovate dal registro.
        """
        apps = []

        registry_sources = [
            [
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
            ],
            [
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            ],
            [
                winreg.HKEY_CURRENT_USER,
                r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
            ],
        ]

        app_count = 0
        for source in registry_sources:
            try:
                registry = winreg.ConnectRegistry(None, source[0])
                registry_key = winreg.OpenKey(registry, source[1])

                for sub_key_name in self._read_registry(registry_key, ReadMode.KEY):
                    try:
                        sub_key = winreg.OpenKey(registry, f"{source[1]}\\{sub_key_name}")
                        values = {}

                        for sub_key_value in self._read_registry(sub_key, ReadMode.VALUE):
                            values[sub_key_value[0]] = sub_key_value[1]

                        if "DisplayName" in values:
                            name = values["DisplayName"].strip()
                            version = values.get("DisplayVersion", "").strip()
                            
                            # Prova a ottenere un path più preciso
                            install_location = values.get('InstallLocation', '').strip()
                            executable_path = values.get('DisplayIcon') or values.get('UninstallString', '')
                            
                            # Normalizza ed estrae il path all'exe se possibile
                            exe_path = executable_path.strip().strip('"') if executable_path else install_location

                            app_info = {
                                'name': name,
                                'version': version,
                                'path': exe_path.replace(',0', ''),
                            }

                            if version:
                                app_info['display_name'] = f"{name} = {version}"
                            else:
                                app_info['display_name'] = name

                            apps.append(app_info)
                            app_count += 1
                            
                            # Notifica del progresso se richiesto
                            if callback and app_count % 10 == 0:
                                callback(app_count, f"Scansione registro: trovate {app_count} applicazioni")
                    except Exception:
                        continue
            except Exception:
                continue

        return apps
    
    def _read_registry(self, key, mode):
        """Legge le chiavi o i valori dal registro di sistema."""
        i = 0
        while True:
            try:
                if mode == ReadMode.KEY:
                    yield winreg.EnumKey(key, i)
                elif mode == ReadMode.VALUE:
                    yield winreg.EnumValue(key, i)
                i += 1
            except OSError:
                break
    
    def _find_macos_apps(self):
        """Trova applicazioni installate su macOS."""
        apps = []
        app_dirs = ['/Applications', os.path.expanduser('~/Applications')]
        
        for app_dir in app_dirs:
            if os.path.exists(app_dir):
                for item in os.listdir(app_dir):
                    if item.endswith('.app'):
                        full_path = os.path.join(app_dir, item)
                        apps.append({
                            'name': item.replace('.app', ''),
                            'path': full_path
                        })
        
        # Ordina per nome
        apps.sort(key=lambda x: x['name'].lower())
        return apps
    
    def _find_linux_apps(self):
        """Trova applicazioni installate su Linux."""
        apps = []
        # Cerca nei percorsi .desktop standard
        desktop_dirs = [
            '/usr/share/applications',
            '/usr/local/share/applications',
            os.path.expanduser('~/.local/share/applications')
        ]
        
        for desktop_dir in desktop_dirs:
            if os.path.exists(desktop_dir):
                for file in os.listdir(desktop_dir):
                    if file.endswith('.desktop'):
                        path = os.path.join(desktop_dir, file)
                        name = self._extract_name_from_desktop(path)
                        exec_path = self._extract_exec_from_desktop(path)
                        if name and exec_path:
                            apps.append({
                                'name': name,
                                'path': exec_path
                            })
        
        # Ordina per nome
        apps.sort(key=lambda x: x['name'].lower())
        return apps
    
    def _extract_name_from_desktop(self, desktop_file):
        """Estrae il nome da un file .desktop."""
        try:
            with open(desktop_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if line.startswith('Name='):
                        return line.split('=', 1)[1].strip()
        except:
            pass
        return None
    
    def _extract_exec_from_desktop(self, desktop_file):
        """Estrae il comando eseguibile da un file .desktop."""
        try:
            with open(desktop_file, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if line.startswith('Exec='):
                        # Rimuovi parametri come %f, %u, ecc.
                        cmd = line.split('=', 1)[1].strip()
                        cmd = re.sub(r'\s+%[fFuUdDnNickvm]', '', cmd)
                        return cmd
        except:
            pass
        return None

class ProfileManager:
    """
    Gestisce il salvataggio, caricamento ed esecuzione dei profili di automazione.
    """
    def __init__(self, profiles_file="profiles.json"):
        self.profiles_file = profiles_file
        self.profiles = self.load_profiles()
    
    def load_profiles(self):
        """
        Carica i profili dal file JSON.
        
        Returns:
            dict: Dizionario dei profili caricati.
        """
        if os.path.exists(self.profiles_file):
            try:
                with open(self.profiles_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except json.JSONDecodeError:
                print(f"Errore: Il file {self.profiles_file} è danneggiato.")
                return {}
        return {}
    
    def save_profiles(self):
        """
        Salva i profili nel file JSON.
        
        Returns:
            bool: True se il salvataggio è avvenuto con successo.
        """
        try:
            with open(self.profiles_file, 'w', encoding='utf-8') as f:
                json.dump(self.profiles, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Errore nel salvataggio dei profili: {str(e)}")
            return False
    
    def rename_profile(self, profile, new_profile):
        self.profiles[profile] = new_profile
        
    def get_profile(self, name):
        """
        Restituisce un profilo specifico.
        
        Args:
            name (str): Nome del profilo.
            
        Returns:
            list: Lista delle azioni del profilo o None se non esiste.
        """
        return self.profiles.get(name)
    
    def get_all_profiles(self):
        """
        Restituisce tutti i profili.
        
        Returns:
            dict: Dizionario dei profili.
        """
        return self.profiles
    
    def add_profile(self, name, actions):
        """
        Aggiunge un nuovo profilo.
        
        Args:
            name (str): Nome del profilo.
            actions (list): Lista delle azioni del profilo.
            
        Returns:
            bool: True se l'aggiunta è avvenuta con successo.
        """
        self.profiles[name] = actions
        return self.save_profiles()
    
    def update_profile(self, name, actions):
        """
        Aggiorna un profilo esistente.
        
        Args:
            name (str): Nome del profilo.
            actions (list): Lista delle azioni del profilo.
            
        Returns:
            bool: True se l'aggiornamento è avvenuto con successo, False altrimenti.
        """
        if name in self.profiles:
            self.profiles[name] = actions
            return self.save_profiles()
        return False
    
    def delete_profile(self, name):
        """
        Elimina un profilo.
        
        Args:
            name (str): Nome del profilo.
            
        Returns:
            bool: True se l'eliminazione è avvenuta con successo, False altrimenti.
        """
        if name in self.profiles:
            del self.profiles[name]
            return self.save_profiles()
        return False
    
    def execute_profile(self, name, error_callback=None):
        """
        Esegue le azioni di un profilo.
        
        Args:
            name (str): Nome del profilo.
            error_callback (function): Funzione da chiamare in caso di errore (opzionale).
                La funzione riceve come argomenti: tipo_azione, target, messaggio_errore
                
        Returns:
            bool: True se l'esecuzione è avvenuta con successo.
        """
        if name not in self.profiles:
            if error_callback:
                error_callback(None, None, f"Il profilo '{name}' non esiste.")
            return False
        
        actions = self.profiles[name]
        success = True
        
        for action in actions:
            action_type = action.get("type")
            target = action.get("target", "")
            
            if not target:
                continue
                
            try:
                if action_type == "app":
                    # Esegue un'applicazione
                    subprocess.Popen(target)
                elif action_type == "web":
                    # Apre un sito web
                    webbrowser.open(target)
                elif action_type == "folder":
                    # Apre una cartella
                    if sys.platform.startswith('win'):
                        os.startfile(target)
                    elif sys.platform.startswith('darwin'):
                        subprocess.Popen(['open', target])
                    else:
                        subprocess.Popen(['xdg-open', target])
                elif action_type == "command":
                    # Esegue un comando nel terminale
                    if sys.platform.startswith('win'):
                        # Su Windows usa cmd.exe
                        subprocess.Popen(target, shell=True)
                    else:
                        # Su Unix-like usa /bin/sh
                        subprocess.Popen(['/bin/sh', '-c', target])
                elif action_type == "desktoProfile":
                    trayEMenu4.switch_profile(target)
            except Exception as e:
                success = False
                if error_callback:
                    error_callback(action_type, target, str(e))
                else:
                    print(f"Errore nell'esecuzione di {action_type} '{target}': {str(e)}")
        
        return success

class ActionFrame(ttk.Frame):
    """
    Frame per la gestione di una singola azione all'interno di un profilo.
    """
    def __init__(self, parent, action_type="app", target="", on_delete=None, app_finder=None):
        super().__init__(parent)
        self.on_delete = on_delete
        self.app_finder = app_finder
        
        # Variabili
        self.action_type = tk.StringVar(value=action_type)
        self.target = tk.StringVar(value=target)
        
        # Layout
        self.create_widgets()
        
    def create_widgets(self):
        # Tipo di azione
        ttk.Label(self, text="Tipo:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        action_combo = ttk.Combobox(self, textvariable=self.action_type, 
                                   values=["app", "web", "folder", "command", "desktoProfile", "number"], width=8)
        action_combo.grid(row=0, column=1, padx=5, pady=5, sticky="w")
        action_combo.state(["readonly"])
        
        # Target dell'azione
        ttk.Label(self, text="Target:").grid(row=0, column=2, padx=5, pady=5, sticky="w")
        target_entry = ttk.Entry(self, textvariable=self.target, width=40)
        target_entry.grid(row=0, column=3, padx=5, pady=5, sticky="w")
        if self.action_type == "desktoProfile":
            target_entry.state(["readonly"])
        # Pulsante browse
        self.browse_btn = ttk.Button(self, text="...", width=3, command=self.browse_target)
        self.browse_btn.grid(row=0, column=4, padx=5, pady=5, sticky="w")
        
        # Pulsante elimina
        delete_btn = ttk.Button(self, text="X", width=3, command=self.delete_action)
        delete_btn.grid(row=0, column=5, padx=5, pady=5, sticky="w")
        
        # Binding per aggiornare il pulsante browse quando cambia il tipo di azione
        action_combo.bind("<<ComboboxSelected>>", lambda e: self.update_browse_state())
        
        # Inizializza lo stato del pulsante browse
        self.update_browse_state()
    
    def update_browse_state(self):
        """Aggiorna lo stato del pulsante browse in base al tipo di azione."""
        action_type = self.action_type.get()
        if action_type in ["web", "command"]:
            self.browse_btn.state(["disabled"])
        else:
            self.browse_btn.state(["!disabled"])
    
    def browse_target(self):
        """Apre un dialog per selezionare il target dell'azione."""
        action_type = self.action_type.get()
        
        if action_type == "app":
            # Se abbiamo un app finder e ci sono app rilevate, mostriamo la lista
            if self.app_finder and hasattr(self.app_finder, 'installed_apps') and self.app_finder.installed_apps:
                self.show_app_selection_dialog()
            else:
                # Fallback al metodo tradizionale
                file_path = filedialog.askopenfilename(
                    title="Seleziona un'applicazione",
                    filetypes=[("Eseguibili", "*.exe"), ("Tutti i file", "*.*")]
                )
                if file_path:
                    self.target.set(file_path)
        
        elif action_type == "folder":
            folder_path = filedialog.askdirectory(title="Seleziona una cartella")
            if folder_path:
                self.target.set(folder_path)
    
    def show_app_selection_dialog(self):
        """Mostra un dialog per selezionare un'app dalla lista di quelle rilevate."""
        app_selector = AppSelectorDialog(self, self.app_finder.installed_apps)
        if app_selector.result:
            self.target.set(app_selector.result)
    
    def delete_action(self):
        """Elimina questa azione."""
        if self.on_delete:
            self.on_delete(self)
    
    def get_action(self):
        """Restituisce i dati dell'azione."""
        return {
            "type": self.action_type.get(),
            "target": self.target.get()
        }


class AppSelectorDialog(tk.Toplevel):
    """
    Dialog per selezionare un'applicazione dalla lista delle app installate.
    """
    def __init__(self, parent, apps_list):
        super().__init__(parent)
        self.apps_list = apps_list
        self.result = None
        
        # Configurazione finestra
        self.title("Seleziona un'applicazione")
        self.geometry("600x400")
        self.resizable(True, True)
        self.minsize(500, 300)
        self.transient(parent)
        self.grab_set()
        
        # Crea widget
        self.create_widgets()
        
        # Aspetta che la finestra sia chiusa
        self.wait_window()
    
    def create_widgets(self):
        # Frame principale
        main_frame = ttk.Frame(self, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Campo di ricerca
        search_frame = ttk.Frame(main_frame)
        search_frame.pack(fill=tk.X, pady=5)
        
        ttk.Label(search_frame, text="Cerca:").pack(side=tk.LEFT, padx=5)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, width=40)
        search_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        search_entry.bind("<KeyRelease>", self.filter_apps)
        
        # Lista delle app
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.apps_listbox = tk.Listbox(
            list_frame, 
            width=70, 
            height=15, 
            yscrollcommand=scrollbar.set,
            font=('Arial', 10)
        )
        self.apps_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.apps_listbox.yview)
        
        # Popoliamo la lista
        self.app_paths = {}  # Mappa nome -> percorso
        for app in self.apps_list:
            name = app['name']
            path = app['path']
            self.apps_listbox.insert(tk.END, name)
            self.app_paths[name] = path
        
        # Doppio click per selezionare
        self.apps_listbox.bind("<Double-1>", self.on_select)
        
        # Pulsanti
        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=10)
        
        select_btn = ttk.Button(buttons_frame, text="Seleziona", command=self.on_select)
        select_btn.pack(side=tk.RIGHT, padx=5)
        
        cancel_btn = ttk.Button(buttons_frame, text="Annulla", command=self.destroy)
        cancel_btn.pack(side=tk.RIGHT, padx=5)
    
    def filter_apps(self, event=None):
        """Filtra la lista delle app in base al testo di ricerca."""
        search_text = self.search_var.get().lower()
        
        # Pulisci la lista
        self.apps_listbox.delete(0, tk.END)
        
        # Popola con i risultati filtrati
        for app in self.apps_list:
            name = app['name']
            if search_text in name.lower():
                self.apps_listbox.insert(tk.END, name)
    
    def on_select(self, event=None):
        """Gestisce la selezione di un'app dalla lista."""
        try:
            # Ottieni l'indice dell'elemento selezionato
            index = self.apps_listbox.curselection()[0]
            name = self.apps_listbox.get(index)
            
            # Cerca il percorso associato
            for app in self.apps_list:
                if app['name'] == name:
                    self.result = app['path']
                    break
                    
            self.destroy()
        except IndexError:
            # Nessuna selezione
            messagebox.showinfo("Informazione", "Seleziona un'applicazione dalla lista.")


class CommandDialog(simpledialog.Dialog):
    """
    Dialog per inserire un comando da terminale.
    """
    def __init__(self, parent, title, initial_value=""):
        self.initial_value = initial_value
        super().__init__(parent, title)
    
    def body(self, master):
        ttk.Label(master, text="Inserisci il comando da eseguire:").grid(row=0, column=0, sticky="w", pady=5)
        
        self.command_var = tk.StringVar(value=self.initial_value)
        self.command_entry = ttk.Entry(master, textvariable=self.command_var, width=60)
        self.command_entry.grid(row=1, column=0, padx=5, pady=5, sticky="we")
        
        return self.command_entry  # focus iniziale
    
    def apply(self):
        self.result = self.command_var.get()


class ProfileEditorWindow(tk.Toplevel):
    """
    Finestra per la creazione/modifica di un profilo.
    """
    def __init__(self, parent, profile_manager, profile_name=None, on_save=None, app_finder=None):
        super().__init__(parent)
        self.profile_manager = profile_manager
        self.profile_name = profile_name
        self.on_save = on_save
        self.action_frames = []
        self.app_finder = app_finder
        
        # Configurazione finestra
        self.title(f"{'Modifica' if profile_name else 'Nuovo'} Profilo")
        self.geometry("700x500")
        self.resizable(True, True)
        self.minsize(600, 300)
        
        # Stile
        style = ttk.Style()
        style.configure('TFrame', background='#f0f0f0')
        style.configure('TButton', background='#e0e0e0', font=('Arial', 10))
        style.configure('TLabel', background='#f0f0f0', font=('Arial', 10))
        style.configure('TEntry', font=('Arial', 10))
        
        # Layout
        self.create_widgets()
        
        # Carica i dati del profilo se stiamo modificando
        if profile_name and profile_name in self.profile_manager.profiles:
            self.load_profile(profile_name)
    
    def create_widgets(self):
        # Frame principale
        mainframe = ttk.Frame(self, padding="10")
        mainframe.pack(fill=tk.BOTH, expand=True)
        
        # Nome del profilo
        name_frame = ttk.Frame(mainframe)
        name_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(name_frame, text="Nome profilo:").pack(side=tk.LEFT, padx=5)
        self.name_var = tk.StringVar(value=self.profile_name or "")
        name_entry = None
        if self.profile_name != None:
            name_entry = ttk.Entry(name_frame, textvariable=self.name_var, width=30, state='disabled')
        else:
            name_entry = ttk.Entry(name_frame, textvariable=self.name_var, width=30)
        name_entry.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        # Titolo sezione azioni
        actions_label = ttk.Label(mainframe, text="Azioni del profilo:", font=('Arial', 11, 'bold'))
        actions_label.pack(anchor="w", pady=(10, 5))
        
        # Frame per le azioni
        self.actions_container = ttk.Frame(mainframe)
        self.actions_container.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Barra di scorrimento per le azioni
        actions_frame = ttk.Frame(mainframe)
        actions_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        self.canvas = tk.Canvas(actions_frame)
        scrollbar = ttk.Scrollbar(actions_frame, orient="vertical", command=self.canvas.yview)
        self.scrollable_frame = ttk.Frame(self.canvas)
        
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )
        
        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)
        
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Pulsanti aggiunta/salvataggio
        buttons_frame = ttk.Frame(mainframe)
        buttons_frame.pack(fill=tk.X, pady=10)
        
        add_action_menu = tk.Menu(self, tearoff=0)
        submenu_profiles = tk.Menu(add_action_menu, tearoff=0)


        def profileAction(i):
            def action():
                self.add_action("desktoProfile", i)
            return action
                
        for i in trayEMenu4.get_profiles():
            submenu_profiles.add_command(label=i, command=profileAction(i))

        add_action_menu.add_command(label="Applicazione", command=lambda: self.add_action("app", ""))
        add_action_menu.add_command(label="Sito Web", command=lambda: self.add_action("web", ""))
        add_action_menu.add_command(label="Cartella", command=lambda: self.add_action("folder", ""))
        add_action_menu.add_command(label="Comando Terminale", command=self.add_command_action)
        add_action_menu.add_command(label="number (0 - 4)", command=self.add_number_action)
        #add_action_menu.option_add(label="Profili", command=lambda: self.add_action("profili", ""))
        add_action_menu.add_cascade(label="Profili", menu=submenu_profiles)

        add_action_btn = ttk.Button(buttons_frame, text="Aggiungi Azione", command=lambda: self.add_action())
        add_action_btn.bind("<Button-1>", lambda e: add_action_menu.post(e.x_root, e.y_root))
        add_action_btn.pack(side=tk.LEFT, padx=5)
        
        save_btn = ttk.Button(buttons_frame, text="Salva Profilo", command=self.save_profile)
        save_btn.pack(side=tk.RIGHT, padx=5)
        
        cancel_btn = ttk.Button(buttons_frame, text="Annulla", command=self.destroy)
        cancel_btn.pack(side=tk.RIGHT, padx=5)
    
    def add_action(self, action_type="app", target=""):
        """Aggiunge un nuovo frame per un'azione."""
        action_frame = ActionFrame(
            self.scrollable_frame, 
            action_type=action_type, 
            target=target, 
            on_delete=self.remove_action,
            app_finder=self.app_finder
        )
        action_frame.pack(fill=tk.X, pady=2)
        self.action_frames.append(action_frame)

    def add_number_action(self):
        """Aggiunge un'azione di tipo comando terminale."""
        dialog = CommandDialog(self, "Inserisci numero (0 - 4)")
        if hasattr(dialog, 'result') and dialog.result:
            self.add_action("number", dialog.result)
    
    def add_command_action(self):
        """Aggiunge un'azione di tipo comando terminale."""
        dialog = CommandDialog(self, "Inserisci Comando")
        if hasattr(dialog, 'result') and dialog.result:
            self.add_action("command", dialog.result)
    
    def remove_action(self, action_frame):
        """Rimuove un'azione dalla lista."""
        if action_frame in self.action_frames:
            self.action_frames.remove(action_frame)
            action_frame.destroy()
    
    def load_profile(self, profile_name):
        """Carica i dati di un profilo esistente."""
        actions = self.profile_manager.profiles.get(profile_name, [])
        for action in actions:
            self.add_action(
                action_type=action.get("type", "app"),
                target=action.get("target", "")
            )
    
    def save_profile(self):
        """Salva il profilo."""
        profile_name = self.name_var.get().strip()
        
        if not profile_name:
            messagebox.showerror("Errore", "Il nome del profilo non può essere vuoto.")
            return
        
        # Raccoglie tutte le azioni
        actions = []
        for frame in self.action_frames:
            action = frame.get_action()
            if action["target"].strip():  # Include solo azioni con target non vuoto
                actions.append(action)
        
        # Salva il profilo
        if self.profile_name and self.profile_name != profile_name:
            # Se è cambiato il nome, elimina il vecchio profilo
            self.profile_manager.delete_profile(self.profile_name)
        
        # Aggiungi/aggiorna il profilo
        self.profile_manager.add_profile(profile_name, actions)
        
        # Notifica la finestra principale
        if self.on_save:
            self.on_save()
        
        self.destroy()


class LoadingDialog(tk.Toplevel):
    """
    Dialog che mostra un indicatore di caricamento.
    """
    def __init__(self, parent, message="Caricamento in corso..."):
        super().__init__(parent)
        self.title("Attendere")
        self.geometry("300x100")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        
        # Configurazione
        self.configure(background='#f0f0f0')
        
        # Message label
        message_label = ttk.Label(
            self, 
            text=message, 
            font=('Arial', 10),
            background='#f0f0f0'
        )
        message_label.pack(pady=(20, 10))
        
        # Progress bar
        self.progress = ttk.Progressbar(
            self, 
            mode='indeterminate', 
            length=250
        )
        self.progress.pack(pady=10)
        self.progress.start(10)
    
    def close(self):
        """Chiude il dialog."""
        self.progress.stop()
        self.destroy()


class App(tk.Toplevel):
    """
    Applicazione principale per la gestione dei profili.
    """
    def __init__(self):
        super().__init__()
        
        # Configurazione finestra
        self.title("Gestore Profili di Automazione")
        self.geometry("800x600")
        self.minsize(600, 400)
        
        # Gestore profili e cercatore di app
        self.profile_manager = ProfileManager()
        self.app_finder = AppFinder()
        self.fasky = FaskyApp()
        trayEMenu4.setfasky(self.fasky)
        
        # Layout
        self.create_widgets()
        
        # Carica le app in background
        self.load_apps_in_background()

    def create_widgets(self):
        # Frame principale
        self.mainframe = ttk.Frame(self, padding="10")
        self.mainframe.pack(fill=tk.BOTH, expand=True)
        
        # Frame per il titolo e i controlli
        header_frame = ttk.Frame(self.mainframe)
        header_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(header_frame, text="I tuoi profili di automazione", 
                 font=('Arial', 14, 'bold')).pack(side=tk.LEFT)
        
        # Frame per i pulsanti di controllo
        controls_frame = ttk.Frame(self.mainframe)
        controls_frame.pack(fill=tk.X, pady=5)
        
        new_profile_btn = ttk.Button(controls_frame, text="Nuovo Profilo", 
                                    command=self.create_profile)
        new_profile_btn.pack(side=tk.LEFT, padx=5)
        
        refresh_apps_btn = ttk.Button(controls_frame, text="Aggiorna Lista App", 
                                     command=self.refresh_app_list)
        refresh_apps_btn.pack(side=tk.LEFT, padx=5)
        
        # Indicatore di stato scansione app
        self.scan_status_var = tk.StringVar(value="Scansione delle applicazioni...")
        status_label = ttk.Label(controls_frame, textvariable=self.scan_status_var,
                                font=('Arial', 9, 'italic'))
        status_label.pack(side=tk.RIGHT, padx=5)
        
        # Frame per la lista dei profili
        profiles_frame = ttk.LabelFrame(self.mainframe, text="Profili disponibili")
        profiles_frame.pack(fill=tk.BOTH, expand=True, pady=10)
        
        # Lista profili con scrollbar
        self.profiles_canvas = tk.Canvas(profiles_frame)
        scrollbar = ttk.Scrollbar(profiles_frame, orient="vertical", 
                                 command=self.profiles_canvas.yview)
        
        self.profiles_container = ttk.Frame(self.profiles_canvas)
        self.profiles_container.bind(
            "<Configure>",
            lambda e: self.profiles_canvas.configure(scrollregion=self.profiles_canvas.bbox("all"))
        )
        
        self.profiles_canvas.create_window((0, 0), window=self.profiles_container, anchor="nw")
        self.profiles_canvas.configure(yscrollcommand=scrollbar.set)
        
        self.profiles_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Informazioni a piè di pagina
        footer_frame = ttk.Frame(self.mainframe)
        footer_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(footer_frame, text="Gestore Profili di Automazione v1.1", 
                 font=('Arial', 8)).pack(side=tk.LEFT)
        
        # Aggiorna la lista dei profili
        self.update_profiles_list()
    
    def load_apps_in_background(self):
        """Carica le applicazioni in background per non bloccare l'interfaccia."""
        # Mostra stato iniziale
        self.scan_status_var.set("Scansione delle applicazioni in corso...")
        
        # Crea un thread per la scansione
        def scan_apps():
            try:
                installed_apps = self.app_finder.find_apps()
                self.app_finder.installed_apps = installed_apps
                
                # Aggiorna l'interfaccia nel thread principale
                self.after(0, lambda: self.scan_status_var.set(
                    f"Trovate {len(installed_apps)} applicazioni"
                ))
            except Exception as e:
                self.after(0, lambda: self.scan_status_var.set(
                    f"Errore nella scansione: {str(e)}"
                ))
        
        Thread(target=scan_apps).start()
    
    def refresh_app_list(self):
        """Aggiorna manualmente la lista delle applicazioni."""
        # Mostra dialog di caricamento
        loading = LoadingDialog(self, "Ricerca delle applicazioni installate...")
        
        # Crea un thread per la scansione
        def scan_apps():
            try:
                installed_apps = self.app_finder.find_apps()
                self.app_finder.installed_apps = installed_apps
                
                # Aggiorna l'interfaccia nel thread principale
                self.after(0, lambda: self.scan_status_var.set(
                    f"Trovate {len(installed_apps)} applicazioni"
                ))
                self.after(0, loading.close)
            except Exception as e:
                self.after(0, lambda: self.scan_status_var.set(
                    f"Errore nella scansione: {str(e)}"
                ))
                self.after(0, loading.close)
        
        Thread(target=scan_apps).start()
    
    def update_profiles_list(self):
        """Aggiorna la lista dei profili visualizzati."""
        # Pulisci il contenitore
        for widget in self.profiles_container.winfo_children():
            widget.destroy()
        
        # Aggiungi i profili
        if not self.profile_manager.profiles:
            no_profiles_label = ttk.Label(
                self.profiles_container, 
                text="Nessun profilo disponibile. Crea un nuovo profilo per iniziare.",
                font=('Arial', 10, 'italic'),
                padding=20
            )
            no_profiles_label.pack(fill=tk.X, pady=10)
            return
        
        # Aggiungi un frame per ogni profilo
        for i, (name, actions) in enumerate(self.profile_manager.profiles.items()):
            profile_frame = ttk.Frame(self.profiles_container, padding=5)
            profile_frame.pack(fill=tk.X, pady=5)
            
            # Alterna i colori di sfondo per migliorare la leggibilità
            if i % 2 == 0:
                profile_frame.configure(style='EvenRow.TFrame')
            else:
                profile_frame.configure(style='OddRow.TFrame')
            
            # Nome del profilo
            name_label = ttk.Label(profile_frame, text=name, font=('Arial', 11, 'bold'))
            name_label.grid(row=0, column=0, sticky="w", padx=5)
            
            # Numero di azioni
            actions_count = len(actions)
            actions_label = ttk.Label(
                profile_frame, 
                text=f"{actions_count} {'azione' if actions_count == 1 else 'azioni'}"
            )
            actions_label.grid(row=0, column=1, sticky="w", padx=20)
            
            # Pulsanti
            run_btn = ttk.Button(
                profile_frame, 
                text="Avvia", 
                command=lambda n=name: self.execute_profile(n)
            )
            run_btn.grid(row=0, column=2, padx=5)
            
            edit_btn = ttk.Button(
                profile_frame, 
                text="Modifica", 
                command=lambda n=name: self.edit_profile(n)
            )
            edit_btn.grid(row=0, column=3, padx=5)
            
            delete_btn = ttk.Button(
                profile_frame, 
                text="Elimina", 
                command=lambda n=name: self.delete_profile(n)
            )
            delete_btn.grid(row=0, column=4, padx=5)
            
            # Dettagli sulle azioni (opzionale)
            if actions:
                details_frame = ttk.Frame(profile_frame)
                details_frame.grid(row=1, column=0, columnspan=5, sticky="w", padx=20, pady=5)
                
                # Mostra solo le prime 3 azioni per non appesantire troppo l'interfaccia
                for j, action in enumerate(actions[:3]):
                    action_type = action.get("type", "")
                    target = action.get("target", "")
                    
                    # Icone per il tipo di azione
                    if action_type == "app":
                        icon = "🖥️"
                    elif action_type == "web":
                        icon = "🌐"
                    elif action_type == "folder":
                        icon = "📁"
                    elif action_type == "command":
                        icon = "🔧"
                    else:
                        icon = "📌"
                    
                    # Visualizza il nome del file per app/cartelle, altrimenti l'intero percorso
                    display_text = target
                    if action_type in ['app', 'folder']:
                        display_text = os.path.basename(target)
                    elif action_type == 'command' and len(target) > 40:
                        display_text = target[:37] + "..."
                    
                    action_label = ttk.Label(
                        details_frame, 
                        text=f"{icon} {display_text}"
                    )
                    action_label.pack(anchor="w")
                
                # Se ci sono più di 3 azioni, mostra un indicatore
                if len(actions) > 3:
                    more_label = ttk.Label(
                        details_frame, 
                        text=f"... e altre {len(actions) - 3} azioni", 
                        font=('Arial', 8, 'italic')
                    )
                    more_label.pack(anchor="w")
    
    def create_profile(self):
        """Apre la finestra per creare un nuovo profilo."""
        ProfileEditorWindow(
            self, 
            self.profile_manager, 
            on_save=self.update_profiles_list,
            app_finder=self.app_finder
        )
    
    def edit_profile(self, profile_name):
        """Apre la finestra per modificare un profilo esistente."""
        ProfileEditorWindow(
            self, 
            self.profile_manager, 
            profile_name=profile_name, 
            on_save=self.update_profiles_list,
            app_finder=self.app_finder
        )
    
    def delete_profile(self, profile_name):
        """Elimina un profilo dopo conferma."""
        if messagebox.askyesno("Conferma", f"Sei sicuro di voler eliminare il profilo '{profile_name}'?"):
            self.profile_manager.delete_profile(profile_name)
            self.update_profiles_list()
    
    def execute_profile(self, profile_name):
        """Esegue un profilo."""
        if self.profile_manager.execute_profile(profile_name):
            messagebox.showinfo("Successo", f"Profilo '{profile_name}' avviato con successo!")

def find_installed_apps(callback=None):
    """
    Funzione di utilità per trovare le applicazioni installate.
    
    Args:
        callback (function): Funzione da chiamare durante la scansione per aggiornare
                           l'interfaccia utente o mostrare il progresso.
    
    Returns:
        list: Lista delle applicazioni trovate.
    """
    app_finder = AppFinder()
    return app_finder.find_apps(callback)

def load_profile_manager(profiles_file="profiles.json"):
    """
    Funzione di utilità per caricare il gestore dei profili.
    
    Args:
        profiles_file (str): Percorso del file dei profili.
    
    Returns:
        ProfileManager: Istanza del gestore dei profili.
    """
    return ProfileManager(profiles_file)
"""
def execute_profile_by_number(number):
   
    with open("profiles.json", "r") as f:
        data = json.load(f)
    listProfiles = get_profiles_by_number(data, number)
    for i in listProfiles:
        execute_profile(i)

    

    if number == 5:
        def select_switch():
            app.fasky.maiusc_rep_switch.select()
            app.fasky.toggle_maiusc_gestor()
        app.after(0, select_switch)  # Schedule on main thread
    elif number == 15:
        def select_switch():
            app.fasky.maiusc_rep_switch.deselect()
            app.fasky.toggle_maiusc_gestor()
        app.after(0, select_switch)  # Schedule on main thread


    if number == 6 and hasattr(app.fasky, "botSwitch"):
        print("esecuzione 6")
        def select_switch():
            app.fasky.botSwitch.select()
            app.fasky.toggle_bot()
        app.after(0, select_switch)  # Schedule on main thread
    elif number == 16 and hasattr(app.fasky, "botSwitch"):
        print("esecuzione 16")
        def select_switch():
            app.fasky.botSwitch.deselect()
            app.fasky.toggle_bot()
        app.after(0, select_switch)  # Schedule on main thread
    print(number)
"""

def execute_profile(profile_name, profiles_file="profiles.json", error_callback=None):
    """
    Funzione di utilità per eseguire un profilo.

    Args:
        profile_name (str): Nome del profilo da eseguire.
        profiles_file (str): Percorso del file dei profili.
        error_callback (function): Funzione da chiamare in caso di errore (opzionale).
    
    Returns:
        bool: True se l'esecuzione è avvenuta con successo.
    """
    manager = ProfileManager(profiles_file)
    return manager.execute_profile(profile_name, error_callback)
"""
BROADCAST_PORT = 5005
TCP_PORT = 12345
BROADCAST_MESSAGE = f"SERVER:{TCP_PORT}"
BROADCAST_INTERVAL = 2  # secondi

# Invia periodicamente messaggi UDP broadcast
def broadcast_loop():
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        while True:
            sock.sendto(BROADCAST_MESSAGE.encode(), ("255.255.255.255", BROADCAST_PORT))
            #print(f"[UDP] Broadcast inviato: {BROADCAST_MESSAGE}")
            time.sleep(BROADCAST_INTERVAL)

# Server TCP che accetta connessioni dall'ESP32
def tcp_server_loop():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('0.0.0.0', TCP_PORT))
        s.listen()
        print(f"[TCP] In ascolto su porta {TCP_PORT}...")

        while True:
            try: 
                conn, addr = s.accept()
                with conn:
                    print(f"[TCP] Connessione da {addr}")
                    data = conn.recv(1024)
                    if data:
                        data = data.decode().strip()
                        print(f"[TCP] Messaggio ricevuto: {data}")
                        
                        # Verifica se il messaggio è un numero tra 1 e 5
                        try:
                            number = int(data)
                            if 1 <= number%10 <= 6:
                                print(f"[TCP] Esecuzione profilo numero {number}")
                                success = execute_profile_by_number(number)
                                response = "OK" if success else "FAIL"
                            else:
                                response = "INVALID_NUMBER"
                        except ValueError:
                            response = "NOT_A_NUMBER"
                        
                        # Invia risposta
                        conn.sendall(response.encode())
            except Exception as e:
                print(e)
                pass"""

def get_profiles_by_number(data, target_number):
    matching_profiles = []
    for profile_name, entries in data.items():
        for entry in entries:
            if entry.get("type") == "number" and entry.get("target") == str(target_number):
                matching_profiles.append(profile_name)
                break  # Basta trovare un numero corrispondente per aggiungere il profilo
    return matching_profiles

if __name__ == "__main__":
    global app
    #fasky = FaskyApp()
    #threading.Thread(target=fasky.run, daemon=True).start()
#  threading.Thread(target=broadcast_loop, daemon=True).start()
    #threading.Thread(target=tcp_server_loop, daemon=True).start()
    
    # Configurazione dello stile dell'applicazione
    app = App()
    trayEMenu4.setAuto(app)
    
    #fasky_tray_thread = threading.Thread(target=run_fasky_tray, daemon=True)
    #fasky_tray_thread.start()
    # Configura stili aggiuntivi
    style = ttk.Style()
    style.configure('OddRow.TFrame', background='#f5f5f5')
    style.configure('EvenRow.TFrame', background='#e9e9e9')
    app.protocol("WM_DELETE_WINDOW", app.withdraw)
    # Avvia l'applicazione
    app.withdraw()
    app.mainloop()