import os
import customtkinter as ctk
from tkinter import messagebox, filedialog, ttk
import winreg
import shutil as sht
import subprocess
import pywinstyles
from hPyT import opacity  # hPyT==1.4.0 # opacity.set(windows, 0.9)
from PIL import Image, ImageTk
import time
import threading
import pystray  
import sys
import tkinter as tk
from app import (
    AppFinder, 
    ProfileManager, 
    ProfileEditorWindow, 
    LoadingDialog,
    execute_profile,
    App
)
from prvUseAuto2 import create_profile, execute_profile, profile_manager, aggiorna
from faskyMain import FaskyApp
root = None
_app = None
auto = None
def setfasky(f):
    global _app
    _app = f
    _app.window.protocol("WM_DELETE_WINDOW", _app.window.withdraw)
def setAuto(app):
    global auto
    auto = app

# Imposta la cartella base per i profili
user = os.getlogin()
basePath = f"C:/Users/{user}/DesktopProfiles"
profileFile = f"{basePath}/active_profile.txt"
tempMarkerFile = f"{basePath}/.temp_active"  # Nuovo file per tracciare lo stato temporaneo
defaultDesktop = f"C:/Users/{user}/Desktop"

# Assicurati che la cartella delle risorse esista
resourcesPath = f"{basePath}/resources"
os.makedirs(resourcesPath, exist_ok=True)

# Costanti di colore
PRIMARY_COLOR = "#1f538d"
ACCENT_COLOR = "#3a7ebf"
DANGER_COLOR = "#e63946"
SUCCESS_COLOR = "#2a9d8f"
TEMP_COLOR = "#f4a261"

def apply_theme(theme_path):
    """Applies a Windows theme using PowerShell and closes the settings app.

    Args:
        theme_path: The full path to the .theme file.
    """
    # Controlla se il file esiste
    if not os.path.exists(theme_path):
        print(f"Il tema {theme_path} non esiste.")
        return False
        
    # Metodo migliorato per applicare il tema senza aprire l'app Impostazioni
    try:
        # Imposta direttamente nel registro Windows il tema corrente
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Themes"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_WRITE) as key:
            winreg.SetValueEx(key, "CurrentTheme", 0, winreg.REG_SZ, theme_path)
            
        # Notifica al sistema del cambio tema senza riavviare explorer
        command = f'''$signature = @"
[DllImport("uxtheme.dll", CharSet = CharSet.Auto)]
public static extern int SetSystemVisualStyle(string pszFilename, string pszColor, string pszSize, int dwReserved);
"@

$uxtheme = Add-Type -MemberDefinition $signature -Name SysTheme -Namespace Win32Functions -PassThru
$uxtheme::SetSystemVisualStyle("{theme_path}", $null, $null, 0)'''
        
        result = subprocess.run(["powershell", "-Command", command], capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"Tema '{theme_path}' applicato con successo.")
            return True
        else:
            print(f"Errore nell'applicazione del tema: {result.stderr}")
            
            # Fallback al metodo precedente
            command = f'start-process -filepath "{theme_path}"; timeout /t 02; taskkill /im systemsettings.exe /f'
            subprocess.run(["powershell", "-Command", command], check=True)
            return True
            
    except Exception as e:
        print(f"Errore nell'applicazione del tema: {e}")
        
        # Fallback al metodo originale
        try:
            command = f'start-process -filepath "{theme_path}"; timeout /t 02; taskkill /im systemsettings.exe /f'
            subprocess.run(["powershell", "-Command", command], check=True)
            return True
        except Exception as e2:
            print(f"Anche il fallback ha fallito: {e2}")
            return False

def get_current_theme_path():
    try:
        # Apri la chiave del registro in modalità di sola lettura
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Themes", 0, winreg.KEY_READ)
        # Leggi il valore "CurrentTheme"
        current_theme, _ = winreg.QueryValueEx(key, "CurrentTheme")
        winreg.CloseKey(key)
        return current_theme
    except Exception as e:
        print("Errore nella lettura del registro:", e)
        return None

os.makedirs(basePath, exist_ok=True)

# Funzioni per la gestione dei profili
def get_profiles():
    """Ottiene la lista dei profili disponibili."""
    return [f.replace(".reg", "") for f in os.listdir(basePath) if f.endswith(".reg")]

def get_active_profile():
    """Legge il profilo attivo dal file, se esiste."""
    # Controlla se c'è un profilo temporaneo attivo
    if os.path.exists(tempMarkerFile):
        return "temp"
        
    if os.path.exists(profileFile):
        with open(profileFile, "r") as f:
            return f.readline().strip()
    return "default"  # Se non esiste, usa default

def set_active_profile(profile):
    """Imposta un nuovo profilo attivo e lo salva nel file."""
    # Se il profilo è "temp", crea un file marker
    if profile == "temp":
        with open(tempMarkerFile, "w") as f:
            f.write("temporary desktop active")
    elif os.path.exists(tempMarkerFile):
        # Se stiamo passando da temp a un altro profilo, rimuovi il marker
        os.remove(tempMarkerFile)
    
    # Salva sempre il profilo attivo (anche temp, per retrocompatibilità)
    with open(profileFile, "w") as f:
        f.write(profile)

def create_toast_notification(message, duration=3):
    """Crea una notifica toast temporanea."""
    toast = ctk.CTkToplevel()
    toast.attributes("-topmost", True)
    toast.overrideredirect(True)
    toast.configure(fg_color=ACCENT_COLOR)
    
    # Calcola la posizione
    width = 300
    height = 50
    screen_width = toast.winfo_screenwidth()
    screen_height = toast.winfo_screenheight()
    x = screen_width - width - 20
    y = screen_height - height - 60
    
    toast.geometry(f"{width}x{height}+{x}+{y}")
    
    ctk.CTkLabel(toast, text=message, font=ctk.CTkFont(size=14), text_color="white").pack(expand=True)
    
    def close_toast():
        time.sleep(duration)
        toast.destroy()
    
    threading.Thread(target=close_toast, daemon=True).start()
    return toast

def salva_disposizione(profile=""):
    """Salva la disposizione delle icone per il profilo selezionato."""
    # Non salvare la disposizione per il profilo temporaneo
    if profile == "temp":
        print("Non salvare la disposizione per il profilo temporaneo")
        return
        
    ####### SFONDO #######
    try:
        activeThemePath = get_current_theme_path()
        if activeThemePath is None:
            activeThemePath = r"C:\WINDOWS\resources\Themes\themeD.theme"
        sht.copy(activeThemePath, fr"{basePath}/{profile}.theme")

        lines = []
        
        profileConfigurationFilePath = ""

        if profile != "default":
            profileConfigurationFilePath = f"{basePath}/{profile}_desktop.txt"
            if os.path.exists(profileConfigurationFilePath):
                with open(profileConfigurationFilePath, "r") as f:
                    lines = f.readlines() 
        else:
            profileConfigurationFilePath = f"{basePath}/desktop.txt"
            if not os.path.exists(profileConfigurationFilePath):
                with open(profileConfigurationFilePath, "w") as f:
                    f.write(defaultDesktop)
            with open(profileConfigurationFilePath, "r") as f:
                lines = f.readlines()

        with open(profileConfigurationFilePath, "w") as f:
            f.writelines(lines)
        print(lines)    
        print(profileConfigurationFilePath)

    except Exception as e:
        print(f"Errore nel salvataggio del tema: {e}")

    ########################
    if profile == "":
        profile = profile_var.get()
    file_path = f'{basePath}/{profile}.reg'
    print("Salvataggio del registro...")
    comando = f'reg export "HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\Shell\\Bags\\1\\Desktop" "{file_path}" /y'
    os.system(comando)
    create_toast_notification(f"Disposizione salvata per {profile}")

def update_desktop_registry(new_desktop):
    """Aggiorna il valore Desktop nel registro senza chiedere conferma."""
    key_path = r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_SET_VALUE) as key:
            winreg.SetValueEx(key, "Desktop", 0, winreg.REG_EXPAND_SZ, new_desktop.replace('/', "\\"))
            print("Registro aggiornato con successo senza prompt.")
            return True
    except Exception as e:
        print(f"Errore nell'aggiornamento del registro: {e}")
        return False

def ripristina_disposizione():
    """Ripristina la disposizione delle icone per il profilo selezionato."""
    profile = profile_var.get()
    file_path = f'{basePath}/{profile}.reg'
    desktop_path_file = f"{basePath}/{profile}_desktop.txt"
    print(desktop_path_file)
    
    if os.path.exists(file_path):
        print("Importazione del registro...")
        os.system(f'reg import "{file_path}"')
        
        if os.path.exists(desktop_path_file):
            with open(desktop_path_file, "r") as f:
                new_desktop = f.readline().strip()
        else:
            new_desktop = defaultDesktop   
            
        if update_desktop_registry(new_desktop):
            restart_explorer()
            create_toast_notification(f"Disposizione ripristinata per {profile}")
        else:
            messagebox.showwarning("Errore", "Impossibile aggiornare il registro di sistema.")
    else:
        messagebox.showwarning("Errore", f"Nessuna disposizione salvata per {profile}")

def restart_explorer():
    """Riavvia explorer.exe in modo più elegante."""
    if 'status_label' in globals():
        status_label.configure(text="Riavvio di Explorer in corso...")
        root.update()
    
    os.system("taskkill /f /im explorer.exe")
    time.sleep(1)
    os.system("start explorer.exe")
    
    if 'status_label' in globals():
        status_label.configure(text="Explorer riavviato con successo")
        root.after(3000, lambda: status_label.configure(text=""))

def crea_profilo():
    
    """Crea un nuovo profilo e permette di selezionare una cartella Desktop personalizzata."""
    nuovo_profilo = profile_entry.get().strip()
    if not nuovo_profilo:
        messagebox.showwarning("Errore", "Inserisci un nome per il profilo")
        return
        
    if nuovo_profilo == "temp":
        messagebox.showwarning("Nome riservato", "'temp' è un nome riservato per il profilo temporaneo. Scegli un altro nome.")
        return
        
    if nuovo_profilo in get_profiles():
        result = messagebox.askyesno("Profilo esistente", f"Il profilo '{nuovo_profilo}' esiste già. Vuoi sovrascriverlo?")
        if not result:
            return
    
    desktop_path = filedialog.askdirectory(title="Seleziona la cartella Desktop per questo profilo") or defaultDesktop

    with open(f"{basePath}/{nuovo_profilo}.reg", "w") as f:
        f.write("")  # Crea un file vuoto
    
    with open(f"{basePath}/{nuovo_profilo}_desktop.txt", "w") as f:
        f.write(desktop_path)  # Salva il percorso del Desktop
        
    currentTheme = get_current_theme_path()
    if currentTheme is None:
        currentTheme = r"C:\WINDOWS\resources\Themes\themeD.theme"
    sht.copy(currentTheme, fr"{basePath}/{nuovo_profilo}.theme")

    aggiorna_profili()
    profile_var.set(nuovo_profilo)
    change_profile(nuovo_profilo)
    create_toast_notification(f"Profilo '{nuovo_profilo}' creato con successo!")
    profile_entry.delete(0, 'end')  # Pulisci il campo di input
    aggiornaTrayIcon()
    create_profile(root, nuovo_profilo)



def create_profile_ui(duration=30):
    create_profile_w = ctk.CTkToplevel()
    create_profile_w.attributes("-topmost", True)
    create_profile_w.overrideredirect(True)
    create_profile_w.configure(fg_color=ACCENT_COLOR)

    # Dimensioni
    width = 300
    height = 100
    screen_width = create_profile_w.winfo_screenwidth()
    screen_height = create_profile_w.winfo_screenheight()
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    create_profile_w.geometry(f"{width}x{height}+{x}+{y}")

    # Canvas per disegnare la X nel cerchio
    canvas = tk.Canvas(create_profile_w, width=24, height=24, highlightthickness=0, bg=ACCENT_COLOR, bd=0)
    canvas.place(x=width - 30, y=6)

    # Disegna cerchio con bordo bianco e interno trasparente
    canvas.create_oval(2, 2, 22, 22, outline="white", width=1.5, fill=ACCENT_COLOR)

    # Disegna la X in bianco
    line_width = 1.5
    canvas.create_line(8, 8, 16, 16, fill="white", width=line_width, capstyle=tk.ROUND)
    canvas.create_line(16, 8, 8, 16, fill="white", width=line_width, capstyle=tk.ROUND)

    def close_create_profile_w(event=None):
        create_profile_w.destroy()
        quit()

    # Bind clic su tutto il canvas
    canvas.bind("<Button-1>", close_create_profile_w)

    # Effetto hover per il pulsante di chiusura
    def on_enter(event):
        canvas.delete("all")
        canvas.create_oval(2, 2, 22, 22, outline="white", width=1.5)#, fill="#ff3333")
        canvas.create_line(8, 8, 16, 16, fill="white", width=line_width, capstyle=tk.ROUND)
        canvas.create_line(16, 8, 8, 16, fill="white", width=line_width, capstyle=tk.ROUND)
    
    def on_leave(event):
        canvas.delete("all")
        canvas.create_oval(2, 2, 22, 22, outline="white", width=1.5, fill=ACCENT_COLOR)
        canvas.create_line(8, 8, 16, 16, fill="white", width=line_width, capstyle=tk.ROUND)
        canvas.create_line(16, 8, 8, 16, fill="white", width=line_width, capstyle=tk.ROUND)

    # Bind per hover
    canvas.bind("<Enter>", on_enter)
    canvas.bind("<Leave>", on_leave)

    # Contenuto originale
    ctk.CTkLabel(create_profile_w, text="crea profilo", font=ctk.CTkFont(size=14), text_color="white").pack(expand=True)
    profileName = tk.Entry(create_profile_w, bg="#6aa2d3", border=0)
    profileName.pack(expand=True)
    ctk.CTkButton(
        create_profile_w,
        text="create profile",
        border_color="white",
        border_width=2,
        fg_color=ACCENT_COLOR,
        command=lambda: crea_profilo2(profileName.get().strip(), create_profile_w)
    ).pack(expand=True)
    
    # Chiusura automatica dopo X secondi
    def auto_close():
        time.sleep(duration)
        if create_profile_w.winfo_exists():
            create_profile_w.destroy()
    
    threading.Thread(target=auto_close, daemon=True).start()
    create_profile_w.mainloop()

def crea_profilo2(profileName, ui):
    ui.destroy()
    """Crea un nuovo profilo e permette di selezionare una cartella Desktop personalizzata."""
    nuovo_profilo = profileName
    if not nuovo_profilo:
        messagebox.showwarning("Errore", "Inserisci un nome per il profilo")
        return
        
    if nuovo_profilo == "temp":
        messagebox.showwarning("Nome riservato", "'temp' è un nome riservato per il profilo temporaneo. Scegli un altro nome.")
        return
        
    if nuovo_profilo in get_profiles():
        result = messagebox.askyesno("Profilo esistente", f"Il profilo '{nuovo_profilo}' esiste già. Vuoi sovrascriverlo?")
        if not result:
            return
    
    desktop_path = filedialog.askdirectory(title="Seleziona la cartella Desktop per questo profilo") or defaultDesktop

    with open(f"{basePath}/{nuovo_profilo}.reg", "w") as f:
        f.write("")  # Crea un file vuoto
    
    with open(f"{basePath}/{nuovo_profilo}_desktop.txt", "w") as f:
        f.write(desktop_path)  # Salva il percorso del Desktop
        
    currentTheme = get_current_theme_path()
    if currentTheme is None:
        currentTheme = r"C:\WINDOWS\resources\Themes\themeD.theme"
    sht.copy(currentTheme, fr"{basePath}/{nuovo_profilo}.theme")

    aggiorna_profili()
    #profile_var.set(nuovo_profilo)
    change_profile(nuovo_profilo)
    create_toast_notification(f"Profilo '{nuovo_profilo}' creato con successo!")
    #profile_entry.delete(0, 'end')  # Pulisci il campo di input
    # qua deviamo anche caricare il profilo appena creato e aggiungerlo nel menu del tray
    aggiornaTrayIcon()

def aggiornaTrayIcon():
    try:
        tray_icon.menu = create_tray_menu()
    except Exception as e:
        print(f"Errore nell'aggiornamento dell'icona del tray: {e}")

def carica_profilo():
    """Carica il profilo selezionato, applicando disposizione icone e cartella Desktop."""
    active_profile = get_active_profile()
    profile = profile_var.get()  # prendo il profilo selezionato dall'utente
    
    # Se stiamo passando da un profilo normale a un altro, salva la disposizione
    if active_profile != "temp" and active_profile != profile:
        salva_disposizione(active_profile)
    
    # Se il profilo corrente è temporaneo, eliminalo
    if active_profile == "temp":
        clean_temp_profile()
    
    set_active_profile(profile)
    ripristina_disposizione()

    themePath = fr"{basePath}/{profile}.theme"
    if not os.path.exists(themePath):
        themePath = get_current_theme_path()
    if themePath and os.path.exists(themePath):
        apply_theme(themePath)
    
    status_label.configure(text=f"Profilo '{profile}' caricato correttamente!")
    root.after(3000, lambda: status_label.configure(text=""))
    aggiornaTrayIcon()
    execute_profile(profile)


def elimina_profilo():
    """Elimina un profilo, se non è quello attuale o 'default'."""
    profilo_da_eliminare = profile_var.get()
    if profilo_da_eliminare == "default":
        messagebox.showwarning("Errore", "Non puoi eliminare il profilo predefinito!")
        return
        
    if profilo_da_eliminare == "temp":
        messagebox.showwarning("Errore", "Non puoi eliminare il profilo temporaneo!")
        return
    
    if profilo_da_eliminare == get_active_profile():
        result = messagebox.askyesno("Attenzione", "Stai per eliminare il profilo attivo. Continuare?")
        if not result:
            return
    
    result = messagebox.askyesno("Conferma", f"Sei sicuro di voler eliminare il profilo '{profilo_da_eliminare}'?")
    if not result:
        return

    try:
        os.remove(f"{basePath}/{profilo_da_eliminare}.reg")
        os.remove(f"{basePath}/{profilo_da_eliminare}_desktop.txt")
        if os.path.exists(f"{basePath}/{profilo_da_eliminare}.theme"):
            os.remove(f"{basePath}/{profilo_da_eliminare}.theme")
    except FileNotFoundError as e:
        print(f"File non trovato durante l'eliminazione: {e}")
    
    # Se il profilo eliminato era quello attivo, passa a default
    if profilo_da_eliminare == get_active_profile():
        set_active_profile("default")
    
    aggiorna_profili()
    create_toast_notification(f"Profilo '{profilo_da_eliminare}' eliminato!")
    aggiornaTrayIcon()

def rinomina_profilo(profile, newName, ui):
    ui.destroy()
    try:
        os.rename(f"{basePath}/{profile}.reg", f"{basePath}/{newName.replace(" ", "_")}.reg")
        os.rename(f"{basePath}/{profile}_desktop.txt", f"{basePath}/{newName.replace(" ", "_")}_desktop.txt")
        os.rename(f"{basePath}/{profile}.theme", f"{basePath}/{newName.replace(" ", "_")}.theme")
    except Exception as e:
        print(e)
    aggiornaTrayIcon()

    import json

    with open("profiles.json", "r") as f:
        data = json.load(f)

    # Rinomina la chiave "profile" in "newName"
    if profile in data:
        data[newName] = data[profile]  # Copia il contenuto con il nuovo nome
        del data[profile]              # Elimina la vecchia chiave
    else:
        print(f"Profilo '{profile}' non trovato.")

    # Salva di nuovo il JSON
    with open("profiles.json", "w") as f:
        json.dump(data, f, indent=2)
    aggiorna()
    #profile_manager.rename_profile(profile=profile, new_profile=newName)

def rinomina_profilo_ui(duration=30, profile=""):
    if profile == "":
        try:
            profile = profile_var.get()
            print(profile)
        except:
            return
    create_profile_w = ctk.CTkToplevel()
    create_profile_w.attributes("-topmost", True)
    create_profile_w.overrideredirect(True)
    create_profile_w.configure(fg_color=ACCENT_COLOR)

    # Dimensioni
    width = 300
    height = 100
    screen_width = create_profile_w.winfo_screenwidth()
    screen_height = create_profile_w.winfo_screenheight()
    x = (screen_width - width) // 2
    y = (screen_height - height) // 2
    create_profile_w.geometry(f"{width}x{height}+{x}+{y}")

    # Canvas per disegnare la X nel cerchio
    canvas = tk.Canvas(create_profile_w, width=24, height=24, highlightthickness=0, bg=ACCENT_COLOR, bd=0)
    canvas.place(x=width - 30, y=6)

    # Disegna cerchio con bordo bianco e interno trasparente
    canvas.create_oval(2, 2, 22, 22, outline="white", width=1.5, fill=ACCENT_COLOR)

    # Disegna la X in bianco
    line_width = 1.5
    canvas.create_line(8, 8, 16, 16, fill="white", width=line_width, capstyle=tk.ROUND)
    canvas.create_line(16, 8, 8, 16, fill="white", width=line_width, capstyle=tk.ROUND)

    def close_create_profile_w(event=None):
        create_profile_w.destroy()

    # Bind clic su tutto il canvas
    canvas.bind("<Button-1>", close_create_profile_w)

    # Effetto hover per il pulsante di chiusura
    def on_enter(event):
        canvas.delete("all")
        canvas.create_oval(2, 2, 22, 22, outline="white", width=1.5)#, fill="#ff3333")
        canvas.create_line(8, 8, 16, 16, fill="white", width=line_width, capstyle=tk.ROUND)
        canvas.create_line(16, 8, 8, 16, fill="white", width=line_width, capstyle=tk.ROUND)
    
    def on_leave(event):
        canvas.delete("all")
        canvas.create_oval(2, 2, 22, 22, outline="white", width=1.5, fill=ACCENT_COLOR)
        canvas.create_line(8, 8, 16, 16, fill="white", width=line_width, capstyle=tk.ROUND)
        canvas.create_line(16, 8, 8, 16, fill="white", width=line_width, capstyle=tk.ROUND)

    # Bind per hover
    canvas.bind("<Enter>", on_enter)
    canvas.bind("<Leave>", on_leave)

    # Contenuto originale
    ctk.CTkLabel(create_profile_w, text=f"rinomina profilo {profile}", font=ctk.CTkFont(size=14), text_color="white").pack(expand=True)
    profileName = tk.Entry(create_profile_w, bg="#6aa2d3", border=0)
    profileName.pack(expand=True)
    ctk.CTkButton(
        create_profile_w,
        text="rinomina profilo",
        border_color="white",
        border_width=2,
        fg_color=ACCENT_COLOR,
        command=lambda: rinomina_profilo(profile, profileName.get().strip(), create_profile_w)
    ).pack(expand=True)
    
    # Chiusura automatica dopo X secondi
    def auto_close():
        time.sleep(duration)
        if create_profile_w.winfo_exists():
            create_profile_w.destroy()
    
    threading.Thread(target=auto_close, daemon=True).start()
    create_profile_w.mainloop()


def elimina_profilo_specifico(profile):
    """Elimina un profilo, se non è quello attuale o 'default'."""
    profilo_da_eliminare = profile
    if profilo_da_eliminare == "default":
        messagebox.showwarning("Errore", "Non puoi eliminare il profilo predefinito!")
        return
        
    if profilo_da_eliminare == "temp":
        messagebox.showwarning("Errore", "Non puoi eliminare il profilo temporaneo!")
        return
    
    if profilo_da_eliminare == get_active_profile():
        result = messagebox.askyesno("Attenzione", "Stai per eliminare il profilo attivo. Continuare?")
        if not result:
            return
    
    result = messagebox.askyesno("Conferma", f"Sei sicuro di voler eliminare il profilo '{profilo_da_eliminare}'?")
    if not result:
        return

    try:
        os.remove(f"{basePath}/{profilo_da_eliminare}.reg")
        os.remove(f"{basePath}/{profilo_da_eliminare}_desktop.txt")
        if os.path.exists(f"{basePath}/{profilo_da_eliminare}.theme"):
            os.remove(f"{basePath}/{profilo_da_eliminare}.theme")
    except FileNotFoundError as e:
        print(f"File non trovato durante l'eliminazione: {e}")
    
    # Se il profilo eliminato era quello attivo, passa a default
    if profilo_da_eliminare == get_active_profile():
        set_active_profile("default")
    
    aggiorna_profili()
    create_toast_notification(f"Profilo '{profilo_da_eliminare}' eliminato!")
    aggiornaTrayIcon()


def aggiorna_profili():
    """Aggiorna la lista dei profili disponibili."""
    profili = get_profiles()
    if "default" not in profili:
        profili.append("default")

    # Ordina i profili mettendo default all'inizio se esiste
    if "default" in profili:
        profili.remove("default")
        profili = ["default"] + profili
    
    # Aggiungi il profilo temporaneo solo se è attivo
    active = get_active_profile()
    if active == "temp" and "temp" not in profili:
        profili = ["temp"] + profili
    elif "temp" in profili and active != "temp":
        profili.remove("temp")  # Rimuovi il profilo temp se non è attivo

    # Aggiorna la frame dei profili
    for widget in profiles_frame.winfo_children():
        widget.destroy()
    
    for profile in profili:
        is_active = profile == active
        
        # Colore speciale per profilo temporaneo
        if profile == "temp":
            fg_color = TEMP_COLOR if is_active else "transparent"
            hover_color = "#e76f51"
        else:
            fg_color = PRIMARY_COLOR if is_active else "transparent"
            hover_color = ACCENT_COLOR
        
        profile_btn = ctk.CTkButton(
            profiles_frame, 
            text=profile, 
            fg_color=fg_color,
            hover_color=hover_color,
            command=lambda p=profile: change_profile(p)
        )
        profile_btn.pack(side="left", padx=5, pady=5)
    
    # Aggiorna le informazioni
    profile_var.set(active)
    change_profile(active)

def change_profile(profile):
    """Aggiorna l'interfaccia quando si seleziona un profilo."""
    profile_var.set(profile)
    
    # Aggiorna l'etichetta del profilo
    profile_label.configure(text=f"Profilo: {profile}")
    
    # Carica le informazioni del profilo
    try:
        # Carica il percorso del desktop
        desktop_path = defaultDesktop
        if profile != "default":
            desktop_path_file = f"{basePath}/{profile}_desktop.txt"
            if os.path.exists(desktop_path_file):
                with open(desktop_path_file, "r") as f:
                    desktop_path = f.readline().strip()
        
        info_label.configure(text=f"Cartella Desktop: {desktop_path}")
        
        # Disabilita il pulsante di eliminazione per default o temp
        if profile in ["default", "temp"]:
            delete_button.configure(state="disabled")
        else:
            delete_button.configure(state="normal")
            
        # Aggiorna l'etichetta per il profilo temporaneo
        if profile == "temp":
            temp_label.configure(text="Profilo temporaneo attivo")
            temp_label.pack(before=info_label, pady=5)
        else:
            temp_label.pack_forget()
            
    except Exception as e:
        print(f"Errore nel caricamento delle informazioni del profilo: {e}")
        info_label.configure(text="Impossibile caricare le informazioni del profilo")
    aggiornaTrayIcon()

def apri_desktop_temporaneo(folder_path=None):
    """Apre una cartella come desktop in modalità temporanea."""
    # Salva la disposizione attuale solo se non stiamo già usando un desktop temporaneo
    active_profile = get_active_profile()
    if active_profile != "temp":
        salva_disposizione(active_profile)
    
    # Se non è fornito un percorso, chiedi all'utente di selezionare una cartella
    if folder_path is None:
        desktop_path = filedialog.askdirectory(title="Seleziona la cartella da usare come Desktop temporaneo")
        if not desktop_path:
            return  # L'utente ha annullato
    else:
        desktop_path = folder_path
    
    # Salva il percorso del Desktop temporaneo
    with open(f"{basePath}/temp_desktop.txt", "w") as f:
        f.write(desktop_path)  # Salva il percorso del Desktop
    
    # Imposta il profilo temporaneo come attivo
    set_active_profile("temp")
    
    # Aggiorna il registro
    if update_desktop_registry(desktop_path):
        restart_explorer()
        create_toast_notification(f"Desktop temporaneo attivato: {os.path.basename(desktop_path)}")
        
        # Aggiorna l'interfaccia
        if 'root' in globals():
            aggiorna_profili()
            change_profile("temp")
    else:
        if 'messagebox' in globals():
            messagebox.showerror("Errore", "Impossibile aggiornare il registro di sistema")
        else:
            print("Errore: Impossibile aggiornare il registro di sistema")

def ripristina_desktop_default():
    """Ripristina il desktop predefinito."""
    # Salva la disposizione attuale se non stiamo usando il profilo temporaneo
    active_profile = get_active_profile()
    if active_profile != "temp":
        salva_disposizione(active_profile)
    
    # Imposta il profilo default come attivo
    set_active_profile("default")
    
    # Aggiorna il registro
    if update_desktop_registry(defaultDesktop):
        restart_explorer()
        create_toast_notification("Desktop predefinito ripristinato")
        
        # Aggiorna l'interfaccia
        aggiorna_profili()
        change_profile("default")
    else:
        messagebox.showerror("Errore", "Impossibile aggiornare il registro di sistema")

def check_temp_profile():
    """Controlla se il profilo temporaneo è attivo all'avvio."""
    if os.path.exists(tempMarkerFile):
        result = messagebox.askyesno(
            "Profilo temporaneo rilevato", 
            "È stato rilevato un profilo temporaneo attivo dall'ultima sessione.\n"
            "Vuoi ripristinare il profilo predefinito?"
        )
        if result:
            # Rimuovi il marker e carica il profilo predefinito
            os.remove(tempMarkerFile)
            set_active_profile("default")
            update_desktop_registry(defaultDesktop)
            restart_explorer()
            return "default"
    return get_active_profile()

# Funzioni per la system tray
def show_window():
    """Mostra la finestra principale."""
    root.after(0, root.deiconify)
    root.lift()

def hide_window():
    """Nasconde la finestra principale."""
    root.withdraw()
    
def exit_app():
    """Esce dall'applicazione."""
    if tray_icon:
        tray_icon.stop()
    root.destroy()
    sys.exit()
    

def create_tray_menu():
    """Crea il menu contestuale per l'icona nel tray."""
    profiles = get_profiles()
    active_profile = get_active_profile()

    # Menu degli items (la lista verrà costruita dinamicamente)
    menu_items = []
    def apri_app_automazioni():
        auto.after(0, auto.deiconify)
        auto.lift()
    def apri_fasky_app():
        auto.after(0, _app.window.deiconify)
        _app.window.lift()
        
    # Intestazione con profilo attivo
    menu_items.append(pystray.MenuItem(f"Profilo attivo: {active_profile}", None, enabled=False))
    menu_items.append(pystray.MenuItem("Apri Manager", show_window))
    menu_items.append(pystray.MenuItem("Apri Automazioni", apri_app_automazioni))
    menu_items.append(pystray.MenuItem("Apri Fasky", apri_fasky_app))
    menu_items.append(pystray.Menu.SEPARATOR)
    menu_items.append(pystray.MenuItem("Crea Profilo", create_profile_ui))
    # Sottovoce "Cambia profilo" con tutti i profili disponibili
    profile_items = []
    for profile in profiles:
        # Funzione per cambiare profilo direttamente dal tray
        def create_profile_switcher(p):
            def switch_profile():
                # Salva profilo attuale
                current = get_active_profile()
                if current != "temp":
                    salva_disposizione(current)
                
                # Imposta nuovo profilo
                set_active_profile(p)
                profile_var.set(p)
                
                # Carica nuovo profilo
                file_path = f'{basePath}/{p}.reg'
                desktop_path_file = f"{basePath}/{p}_desktop.txt"
                
                if os.path.exists(file_path):
                    os.system(f'reg import "{file_path}"')
                    
                    if os.path.exists(desktop_path_file):
                        with open(desktop_path_file, "r") as f:
                            new_desktop = f.readline().strip()
                    else:
                        new_desktop = defaultDesktop
                        
                    if update_desktop_registry(new_desktop):
                        restart_explorer()
                        create_toast_notification(f"Profilo '{p}' caricato")
                        
                        # Ricrea il menu del tray per aggiornare il profilo attivo
                        tray_icon.menu = create_tray_menu()
                                        
                    themePath = fr"{basePath}/{p}.theme"
                    if not os.path.exists(themePath):
                        themePath = get_current_theme_path()
                    if themePath and os.path.exists(themePath):
                        apply_theme(themePath)

                    
            return switch_profile
        
        def eliminaProfile(profile):
            def deleteProfile():
                elimina_profilo_specifico(profile)
            return deleteProfile
        def rinominaProfile(profile):
            def rinominaProfilo():
                rinomina_profilo_ui(profile=profile)
            return rinominaProfilo    
        
        def goToDir(profile):
            def apriCartella():
                desktop_path_file = f"{basePath}/{profile}_desktop.txt"
                if os.path.exists(desktop_path_file):
                    with open(desktop_path_file, "r") as f:
                        new_desktop = f.readline().strip()
                        os.startfile(new_desktop)
            return apriCartella
        def modifica_azioni(profile):
            def modificaAutomazioni():
                create_profile(root, profile)
            return modificaAutomazioni
        
        optionProfile = [pystray.MenuItem("carica", create_profile_switcher(profile)), 
                         pystray.MenuItem("elimina", eliminaProfile(profile)), 
                         pystray.MenuItem("rinomina", rinominaProfile(profile)), 
                         pystray.MenuItem("apri cartella",goToDir(profile)), 
                         pystray.MenuItem("modifica automazioni", modifica_azioni(profile))]

        profile_items.append(pystray.MenuItem(
            profile, 
            pystray.Menu(*optionProfile),#create_profile_switcher(profile),
            checked=lambda item, p=profile: get_active_profile() == p,
            radio=True
        ))
    
    # Aggiungi il sottomenu dei profili al menu principale
    menu_items.append(pystray.MenuItem("Profili", pystray.Menu(*profile_items)))
    
    # Opzioni aggiuntive
    menu_items.append(pystray.Menu.SEPARATOR)
    menu_items.append(pystray.MenuItem("Desktop temporaneo", lambda: (show_window(), apri_desktop_temporaneo())))
    #menu_items.append(pystray.MenuItem("Ripristina Desktop predefinito", lambda: (ripristina_desktop_default(), tray_icon.menu = create_tray_menu())))
    menu_items.append(pystray.Menu.SEPARATOR)
    menu_items.append(pystray.MenuItem("Esci", exit_app))
    
    return pystray.Menu(*menu_items)

def setup_tray_icon():
    """Configura l'icona nel tray di sistema."""
    # Crea un'icona per il tray (idealmente crea un'icona specifica)
    # Per ora utilizziamo un'icona generica (crea un quadrato blu)
    icon_image = Image.new('RGB', (64, 64), color=PRIMARY_COLOR)
    
    # Percorso per l'icona
    """icon_path = f"tray_icon.png"
    
    # Se non esiste, crea un'icona predefinita
    if not os.path.exists(icon_path):
        icon_image.save(icon_path)
    else:
        try:
            icon_image = Image.open(icon_path)
        except Exception as e:
            print(f"Errore nel caricamento dell'icona: {e}")"""
    
    # Crea l'icona del tray
    icon = pystray.Icon(
        "DesktopProfileManager",
        icon_image,
        "Desktop Profile Manager",
        menu=create_tray_menu()
    )
    
    return icon

def minimize_to_tray():
    """Minimizza l'applicazione nel tray."""
    root.withdraw()  # Nascondi la finestra
    create_toast_notification("Desktop Profile Manager è ancora in esecuzione nella tray", duration=5)

def clean_temp_profile():
    """Pulisce tutti i file relativi al profilo temporaneo."""
    temp_files = [
        f"{basePath}/temp.reg",
        f"{basePath}/temp_desktop.txt",
        f"{basePath}/temp.theme",
        tempMarkerFile
    ]
    
    for file_path in temp_files:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                print(f"Rimosso file temporaneo: {file_path}")
            except Exception as e:
                print(f"Errore nella rimozione del file {file_path}: {e}")

def register_context_menu():
    """Registra il menu contestuale per le cartelle."""
    try:
        # Ottieni il percorso dell'eseguibile
        if getattr(sys, 'frozen', False):
            # Eseguibile compilato
            exe_path = sys.executable
            
        else:
            # Script Python
            exe_path = sys.argv[0]
        print(f"Eseguibile trovato: {exe_path}")
        exe_path = os.path.abspath(exe_path)
        
        # Opzione per aprire come Desktop temporaneo
        temp_key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, r"Directory\shell\DPM_TempDesktop")
        winreg.SetValueEx(temp_key, "", 0, winreg.REG_SZ, "Apri come Desktop temporaneo")
        winreg.SetValueEx(temp_key, "Icon", 0, winreg.REG_SZ, exe_path)
        temp_cmd_key = winreg.CreateKey(temp_key, "command")
        winreg.SetValueEx(temp_cmd_key, "", 0, winreg.REG_SZ, f'"{exe_path}" --temp "%1"')
        
        # Opzione per creare un nuovo profilo
        new_key = winreg.CreateKey(winreg.HKEY_CLASSES_ROOT, r"Directory\shell\DPM_NewProfile")
        winreg.SetValueEx(new_key, "", 0, winreg.REG_SZ, "Crea profilo desktop")
        winreg.SetValueEx(new_key, "Icon", 0, winreg.REG_SZ, exe_path)
        new_cmd_key = winreg.CreateKey(new_key, "command")
        winreg.SetValueEx(new_cmd_key, "", 0, winreg.REG_SZ, f'"{exe_path}" --new "%1"')
        
        print("Menu contestuale registrato con successo.")
        return True
    except Exception as e:
        print(f"Errore nella registrazione del menu contestuale: {e}")
        return False

def unregister_context_menu():
    """Rimuove il menu contestuale."""
    try:
        # Rimuovi le chiavi di registro
        try:
            winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, r"Directory\shell\DPM_TempDesktop\command")
            winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, r"Directory\shell\DPM_TempDesktop")
        except Exception as e:
            print(f"Avviso: {e}")
            
        try:
            winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, r"Directory\shell\DPM_NewProfile\command")
            winreg.DeleteKey(winreg.HKEY_CLASSES_ROOT, r"Directory\shell\DPM_NewProfile")
        except Exception as e:
            print(f"Avviso: {e}")
        
        print("Menu contestuale rimosso con successo.")
        return True
    except Exception as e:
        print(f"Errore nella rimozione del menu contestuale: {e}")
        return False

def create_new_profile_from_folder(folder_path):
    """Crea un nuovo profilo utilizzando la cartella specificata come desktop."""
    # Genera un nome profilo dal nome della cartella
    folder_name = os.path.basename(folder_path)
    profile_name = f"{folder_name}_profile"
    
    # Crea il profilo
    with open(f"{basePath}/{profile_name}.reg", "w") as f:
        f.write("")  # Crea un file vuoto
    
    with open(f"{basePath}/{profile_name}_desktop.txt", "w") as f:
        f.write(folder_path)  # Salva il percorso del Desktop
        
    currentTheme = get_current_theme_path()
    if currentTheme is None:
        currentTheme = r"C:\WINDOWS\resources\Themes\themeD.theme"
    sht.copy(currentTheme, fr"{basePath}/{profile_name}.theme")
    
    # Salva la disposizione attuale
    active_profile = get_active_profile()
    if active_profile != "temp":
        salva_disposizione(active_profile)
    else:
        clean_temp_profile()
    
    # Imposta e carica il nuovo profilo
    set_active_profile(profile_name)
    
    # Aggiorna il registro
    if update_desktop_registry(folder_path):
        restart_explorer()
        create_toast_notification(f"Nuovo profilo '{profile_name}' creato e attivato!")
    else:
        print("Errore: Impossibile aggiornare il registro di sistema")

def process_command_line():
    """Gestisce i parametri della riga di comando."""
    if len(sys.argv) > 1:
        # Gestisci l'apertura come desktop temporaneo
        if sys.argv[1] == "--temp" and len(sys.argv) > 2:
            folder_path = sys.argv[2]
            apri_desktop_temporaneo(folder_path)
            sys.exit(0)
            
        # Gestisci la creazione di un nuovo profilo
        elif sys.argv[1] == "--new" and len(sys.argv) > 2:
            folder_path = sys.argv[2]
            create_new_profile_from_folder(folder_path)
            sys.exit(0)
            
        # Registra il menu contestuale
        elif sys.argv[1] == "--register":
            if register_context_menu():
                print("Menu contestuale registrato con successo.")
            else:
                print("Errore nella registrazione del menu contestuale.")
            sys.exit(0)
            
        # Rimuovi il menu contestuale
        elif sys.argv[1] == "--unregister":
            if unregister_context_menu():
                print("Menu contestuale rimosso con successo.")
            else:
                print("Errore nella rimozione del menu contestuale.")
                sys.exit(0)

# Processo i parametri della riga di comando all'avvio
process_command_line()

# Configurazione UI con CustomTkinter
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

root = ctk.CTkToplevel()
root.title("Desktop Profile Manager")
root.geometry("700x500")
root.minsize(600, 400)

# Gestione eventi della finestra
root.protocol("WM_DELETE_WINDOW", minimize_to_tray)  # Intercetta la chiusura della finestra

# Imposta l'opacità
opacity.set(root, 0.95)

# Variabile per il profilo attivo - viene inizializzata più tardi
profile_var = ctk.StringVar()

# Layout principale
main_frame = ctk.CTkFrame(root)
main_frame.pack(fill="both", expand=True, padx=10, pady=10)

# Header
header_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
header_frame.pack(fill="x", pady=(0, 10))

title_label = ctk.CTkLabel(header_frame, text="Desktop Profile Manager", font=ctk.CTkFont(size=24, weight="bold"))
title_label.pack(side="left", padx=10)

# Aggiungi pulsante per minimizzare nel tray
tray_button = ctk.CTkButton(
    header_frame,
    text="Minimizza nel Tray",
    command=minimize_to_tray,
    fg_color=ACCENT_COLOR,
    hover_color=PRIMARY_COLOR,
    width=150
)
tray_button.pack(side="right", padx=10)

# Profili disponibili (scrollable)
profiles_label = ctk.CTkLabel(main_frame, text="Profili disponibili:", font=ctk.CTkFont(size=16))
profiles_label.pack(anchor="w", padx=10, pady=(5, 0))

profiles_container = ctk.CTkFrame(main_frame)
profiles_container.pack(fill="x", padx=10, pady=5)

profiles_frame = ctk.CTkFrame(profiles_container, fg_color=("#e0e0e0", "#333333"))
profiles_frame.pack(fill="x", padx=5, pady=5)

# Frame per i dettagli del profilo
content_frame = ctk.CTkFrame(main_frame)
content_frame.pack(fill="both", expand=True, padx=10, pady=10)

profile_label = ctk.CTkLabel(content_frame, text="", font=ctk.CTkFont(size=20, weight="bold"))
profile_label.pack(pady=(10, 5))

temp_label = ctk.CTkLabel(content_frame, text="Profilo temporaneo attivo", 
                         font=ctk.CTkFont(size=14), 
                         text_color=TEMP_COLOR)

info_label = ctk.CTkLabel(content_frame, text="", font=ctk.CTkFont(size=14))
info_label.pack(pady=10)

# Frame per i pulsanti di azione principali
action_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
action_frame.pack(pady=10, fill="x")

load_button = ctk.CTkButton(
    action_frame, 
    text="Carica Profilo", 
    command=carica_profilo,
    fg_color=PRIMARY_COLOR,
    hover_color=ACCENT_COLOR,
    font=ctk.CTkFont(size=14, weight="bold"),
    width=150,
    height=40
)
load_button.pack(side="left", padx=5)

delete_button = ctk.CTkButton(
    action_frame, 
    text="Elimina Profilo", 
    command=elimina_profilo,
    fg_color=DANGER_COLOR,
    hover_color="#c1121f",
    font=ctk.CTkFont(size=14),
    width=150,
    height=40
)
delete_button.pack(side="left", padx=5)
rinomina_button = ctk.CTkButton(
    action_frame, 
    text="Rinomina Profilo", 
    command=rinomina_profilo_ui,
    fg_color="#b6a12b",
    hover_color="#c1121f",
    font=ctk.CTkFont(size=14),
    width=150,
    height=40
)
rinomina_button.pack(side="left", padx=5)


# Frame per modalità temporanea
temp_frame = ctk.CTkFrame(content_frame, fg_color="transparent")
temp_frame.pack(pady=10, fill="x")

temp_button = ctk.CTkButton(
    temp_frame, 
    text="Apri Desktop Temporaneo", 
    command=apri_desktop_temporaneo,
    fg_color=TEMP_COLOR,
    hover_color="#e76f51",
    font=ctk.CTkFont(size=14),
    width=200,
    height=40
)
temp_button.pack(side="left", padx=5)

default_button = ctk.CTkButton(
    temp_frame, 
    text="Ripristina Desktop Predefinito", 
    command=ripristina_desktop_default,
    fg_color=SUCCESS_COLOR,
    hover_color="#1d7d74",
    font=ctk.CTkFont(size=14),
    width=200,
    height=40
)
default_button.pack(side="left", padx=5)

# Sezione per creare un nuovo profilo
create_frame = ctk.CTkFrame(main_frame)
create_frame.pack(fill="x", padx=10, pady=10)

ctk.CTkLabel(create_frame, text="Crea nuovo profilo:", font=ctk.CTkFont(size=16)).pack(side="left", padx=10)
profile_entry = ctk.CTkEntry(create_frame, width=200)
profile_entry.pack(side="left", padx=10)

create_button = ctk.CTkButton(
    create_frame, 
    text="Crea Profilo", 
    command=crea_profilo,
    fg_color=SUCCESS_COLOR,
    hover_color="#1d7d74",
    font=ctk.CTkFont(size=14)
)
create_button.pack(side="left", padx=10)

# Stato
status_frame = ctk.CTkFrame(root, fg_color="transparent")
status_frame.pack(fill="x", padx=10, pady=5)

status_label = ctk.CTkLabel(status_frame, text="", font=ctk.CTkFont(size=12))
status_label.pack(side="left", padx=10)

version_label = ctk.CTkLabel(status_frame, text="v2.2", font=ctk.CTkFont(size=12))
version_label.pack(side="right", padx=10)

# Controlla se c'è un profilo temporaneo attivo all'avvio
active_profile = check_temp_profile()
profile_var.set(active_profile)

############################################
context_menu_frame = ctk.CTkFrame(main_frame)
context_menu_frame.pack(fill="x", padx=10, pady=10)
register_button = ctk.CTkButton(
    context_menu_frame, 
    text="aggiungi shortcut tasto destro", 
    command=register_context_menu,
    fg_color=PRIMARY_COLOR,
    hover_color=ACCENT_COLOR,
    font=ctk.CTkFont(size=14)
)
register_button.pack(side="left", padx=10)

unregister_button = ctk.CTkButton(
    context_menu_frame, 
    text="rimuovi shortcut", 
    command=unregister_context_menu,
    fg_color=DANGER_COLOR,
    hover_color="#c1121f",
    font=ctk.CTkFont(size=14)
)
unregister_button.pack(side="left", padx=10)
############################################

# Imposta il profilo iniziale
aggiorna_profili()

# Configurazione del tray
tray_icon = setup_tray_icon()
# Avvia thread per l'icona tray
def run_tray():
    tray_icon.run()


# Avvia il thread dell'icona tray
tray_thread = threading.Thread(target=run_tray, daemon=True)
tray_thread.start()

def switch_profile(p):
    # Salva profilo attuale
    current = get_active_profile()
    if current != "temp":
        salva_disposizione(current)
    
    # Imposta nuovo profilo
    set_active_profile(p)
    profile_var.set(p)
    
    # Carica nuovo profilo
    file_path = f'{basePath}/{p}.reg'
    desktop_path_file = f"{basePath}/{p}_desktop.txt"
    
    if os.path.exists(file_path):
        os.system(f'reg import "{file_path}"')
        
        if os.path.exists(desktop_path_file):
            with open(desktop_path_file, "r") as f:
                new_desktop = f.readline().strip()
        else:
            new_desktop = defaultDesktop
            
        if update_desktop_registry(new_desktop):
            restart_explorer()
            create_toast_notification(f"Profilo '{p}' caricato")
            
            # Ricrea il menu del tray per aggiornare il profilo attivo
            tray_icon.menu = create_tray_menu()
                            
        themePath = fr"{basePath}/{p}.theme"
        if not os.path.exists(themePath):
            themePath = get_current_theme_path()
        if themePath and os.path.exists(themePath):
            apply_theme(themePath)

"""if __name__ == "__main__":
#def run():
    try:
        root.withdraw()
        root.mainloop()
    except KeyboardInterrupt:
        # Assicurati che l'icona nel tray venga rimossa
        if tray_icon:
            tray_icon.stop()
    finally:
        # Chiusura pulita
        if tray_icon:
            tray_icon.stop()
        sys.exit(0)
"""
