import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from threading import Thread
import argparse

# Importa le classi e funzioni dal file originale
try:
    from app import (
        AppFinder, 
        ProfileManager, 
        ProfileEditorWindow,
        LoadingDialog
    )
except ImportError:
    print("Errore: File auto5.py non trovato.")
    print("Assicurati che il file sia nella stessa cartella di questo script.")
    sys.exit(1)

# Variabili globali
profile_manager = ProfileManager()
app_finder = AppFinder()

def list_profiles():
    """Mostra la lista di profili disponibili."""
    profiles = list(profile_manager.profiles.keys())
    
    if not profiles:
        print("Nessun profilo disponibile.")
        return
    
    print("\nProfili disponibili:")
    for i, profile in enumerate(profiles, 1):
        print(f"{i}. {profile}")
    print()

def create_profile(w, name):
    """Apre la finestra grafica per creare un nuovo profilo."""
    # Inizializza una finestra Tk minima
    root = tk.Toplevel()
    root.withdraw()  # Nascondi la finestra principale
    
    # Carica le app in background
    print("Scansione delle applicazioni in corso...")
    try:
        installed_apps = app_finder.find_apps()
        app_finder.installed_apps = installed_apps
        print(f"Trovate {len(installed_apps)} applicazioni")
    except Exception as e:
        print(f"Errore nella scansione: {str(e)}")
        root.destroy()
        return
    
    # Funzione di callback quando il profilo viene salvato
    def on_save():
        print("Profilo salvato con successo!")
    
    # Crea la finestra di editing del profilo
    editor = ProfileEditorWindow(
        w, 
        profile_manager, 
        on_save=on_save,
        app_finder=app_finder,
        profile_name=name
    )
    
    # Porta in primo piano la finestra di creazione
    editor.lift()
    editor.focus_force()
    
    # Attendi finché la finestra non viene chiusa
    root.wait_window(editor)
    root.destroy()

def aggiorna():
    global profile_manager
    profile_manager = ProfileManager()

def execute_profile(profile_name):
    """Esegue il profilo specificato."""
    if profile_name not in profile_manager.profiles:
        print(f"Errore: Profilo '{profile_name}' non trovato.")
        return False
    
    # Funzione di callback per gli errori
    def on_error(action_type, target, error_msg):
        print(f"Errore durante l'esecuzione dell'azione {action_type}: {error_msg}")
    
    print(f"Avvio del profilo '{profile_name}'...")
    result = profile_manager.execute_profile(profile_name, on_error)
    
    if result:
        print(f"Profilo '{profile_name}' avviato con successo!")
        return True
    else:
        print(f"Errore nell'avvio del profilo '{profile_name}'.")
        return False

def show_help():
    """Mostra l'aiuto del comando."""
    print("\nUtilizzo:")
    print("  python command_line_profile_manager.py [opzione]")
    print("\nOpzioni:")
    print("  -h, --help              Mostra questo messaggio di aiuto")
    print("  -l, --list              Elenca i profili disponibili")
    print("  -c, --create            Crea un nuovo profilo")
    print("  -e, --execute PROFILO   Esegue il profilo specificato")
    print("\nEsempi:")
    print("  python command_line_profile_manager.py --list")
    print("  python command_line_profile_manager.py --create")
    print("  python command_line_profile_manager.py --execute \"Profilo di lavoro\"")
    print()

def main():
    """Funzione principale che gestisce i comandi."""
    parser = argparse.ArgumentParser(description='Gestore Profili da linea di comando', add_help=False)
    parser.add_argument('-h', '--help', action='store_true', help='Mostra questo messaggio di aiuto')
    parser.add_argument('-l', '--list', action='store_true', help='Elenca i profili disponibili')
    parser.add_argument('-c', '--create', action='store_true', help='Crea un nuovo profilo')
    parser.add_argument('-e', '--execute', metavar='PROFILO', help='Esegue il profilo specificato')
    
    # In caso di nessun argomento, mostra l'aiuto
    if len(sys.argv) == 1:
        show_help()
        return
    
    args = parser.parse_args()
    
    if args.help:
        show_help()
    elif args.list:
        list_profiles()
    elif args.create:
        create_profile()
    elif args.execute:
        execute_profile(args.execute)
    else:
        print("Comando non riconosciuto. Usa --help per vedere le opzioni disponibili.")

if __name__ == "__main__":
    main()