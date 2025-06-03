import threading
import customtkinter as ctk
import keyboard as kb
import pyautogui as pya
import win32clipboard as cp
import time
from queue import Queue, Empty
from deep_translator import GoogleTranslator
from langdetect import detect, DetectorFactory
loader_window = None
# Per risultati deterministici in langdetect
DetectorFactory.seed = 0
startClipboardData = ""
class TranslatorApp:
    def __init__(self):
        self.running = True

        # Stato dell'app
        self.state = type('obj', (object,), {
            'listening': True,
            'is_visible': False,
            'last_translation_time': 0
        })

        # Code di comunicazione
        self.text_queue = Queue()
        self.result_queue = Queue()

        # Worker thread
        self.worker_thread = threading.Thread(target=self.worker, daemon=True)
        self.worker_thread.start()

        # Setup GUI
        self.setup_gui()

        # Registrazione hotkey
        kb.add_hotkey('f8+ctrl', self.handle_shortcut)

    def start(self):
        # Avvia la GUI loop separatamente
        self.queue_job = self.app.after(100, self.check_queue)
        self.app.withdraw()
        self.app.mainloop()

    def stop(self):
        print("Stopping TranslatorApp...")
        self.running = False

        try:
            kb.unhook_all_hotkeys()
            if hasattr(self, 'queue_job'):
                self.app.after_cancel(self.queue_job)

            self.app.withdraw()  # Nascondi subito
            self.app.after(300, self.safe_destroy)  # Distruggi dopo 300ms
        except Exception as e:
            print(f"Error stopping app: {e}")

    def safe_destroy(self):
        try:
            self.app.quit()
            self.app.destroy()
        except Exception as e:
            print(f"Error during safe_destroy: {e}")

    def hide_window(self):
        """Nasconde la finestra invece di distruggerla"""
        self.app.withdraw()
        self.state.is_visible = False
        if hasattr(self, 'queue_job'):
            self.app.after_cancel(self.queue_job)  # Cancella il ciclo after()
            
    def show_window(self):
        """Mostra la finestra"""
        self.app.deiconify()  # Riapri la finestra
        self.app.lift()
        self.state.is_visible = True
        # Riavvia il ciclo after per il polling della coda
        self.queue_job = self.app.after(100, self.check_queue)

    def setup_gui(self):
        ctk.set_appearance_mode("System")
        ctk.set_default_color_theme("blue")
        self.app = ctk.CTk()
        self.app.title("Traduttore IT⇄EN")
        self.app.attributes("-topmost", True)
        self.app.geometry("300x100")
        
        # Casella di testo per output
        self.result_box = ctk.CTkTextbox(self.app, wrap='word')
        self.result_box.pack(fill='both', expand=True, padx=10, pady=10)
        self.result_box.configure(state="disabled")  # sola lettura, ma selezionabile
        
        # Gestione chiusura finestra (nascondi invece di chiudere)
        self.app.protocol("WM_DELETE_WINDOW", self.hide_window)

    def hide_window(self):
        """Nasconde la finestra invece di chiuderla"""
        self.app.withdraw()
        self.state.is_visible = False

    def show_window(self):
        """Mostra la finestra"""
        self.app.deiconify()
        self.app.lift()
        self.state.is_visible = True

    def handle_shortcut(self):
        global startClipboardData
        """Gestisce la pressione del tasto F8"""
        # Previeni attivazioni multiple troppo ravvicinate
        current_time = time.time()
        if current_time - self.state.last_translation_time < 0.5:
            return
            
        self.state.last_translation_time = current_time
        print("Tasto F8 rilevato! Traduzione in corso...")
        
        # Prima memorizza lo stato delle modifiche della tastiera
        # poi rilascia tutti i tasti modificatori per evitare interferenze
        ctrl_pressed = kb.is_pressed('ctrl')
        shift_pressed = kb.is_pressed('shift')
        alt_pressed = kb.is_pressed('alt')
        
        # Rilascia eventuali tasti modificatori che potrebbero interferire
        if ctrl_pressed:
            pya.keyUp('ctrl')
        if shift_pressed:
            pya.keyUp('shift')
        if alt_pressed:
            pya.keyUp('alt')
            
        time.sleep(0.05)  # Breve pausa
        try:
            cp.OpenClipboard()
            startClipboardData = cp.GetClipboardData()
            print(f"start clipboard data: {startClipboardData}")
            cp.CloseClipboard()
        except:
            pass
        
        try:
            print("simulazione CTRL + C")
            # Simula Ctrl+C con sequenza precisa
            pya.hotkey("ctrl", "c")
            time.sleep(0.03)  # Pausa più lunga per assicurarsi che la copia sia completata
            
            # Ottieni il testo dagli appunti
            self.process_clipboard()
        except Exception as e:
            print(f"Errore durante la simulazione di Ctrl+C: {e}")

    def process_clipboard(self):
        """Processa il contenuto degli appunti"""
        max_attempts = 3
        attempt = 0
        data = ""
        
        while attempt < max_attempts and not data:
            attempt += 1
            try:
                cp.OpenClipboard()
                if cp.IsClipboardFormatAvailable(cp.CF_UNICODETEXT):
                    data = cp.GetClipboardData()
                cp.CloseClipboard()
                
                if not data and attempt < max_attempts:
                    print(f"Tentativo {attempt}: Clipboard vuota, riprovo...")
                    time.sleep(0.1 * attempt)  # Aumenta il tempo di attesa a ogni tentativo
            except Exception as e:
                print(f"Errore durante l'accesso agli appunti (tentativo {attempt}): {e}")
                time.sleep(0.1)
        
        if data and data.strip():
            print(f"Testo trovato negli appunti: '{data[:50]}...'")
            # Invia il testo per la traduzione
            self.text_queue.put(data.strip())
            
            # Mostra la finestra se nascosta
            if not self.state.is_visible:
                self.show_window()
        else:
            print("Nessun testo rilevato negli appunti dopo multipli tentativi.")
        try:
            cp.OpenClipboard()
            cp.EmptyClipboard()
            cp.SetClipboardText(startClipboardData)
            print(f"testo iniziale clipboard da rimettere: {startClipboardData}")
            cp.CloseClipboard()
        except:
            print("error during the restore of the clipboard")

    def translate_auto(self, text):
        """Funzione di traduzione automatica"""
        # Rende maiuscola la prima lettera
        if text:
            text = text[0].upper() + text[1:]
        try:
            src_lang = detect(text)
        except:
            src_lang = 'auto'
        
        target = 'italian' if src_lang == 'en' else 'english'
        
        try:
            translated = GoogleTranslator(source='auto', target=target).translate(text)
            print(f"Traduzione completata: {src_lang} -> {target}")
            return translated
        except Exception as e:
            print(f"Errore durante la traduzione: {e}")
            return f"Errore di traduzione: {str(e)}"

    def worker(self):
        """Thread che esegue traduzioni dai testi in coda"""
        while self.state.listening and self.running:
            try:
                txt = self.text_queue.get(timeout=1)
                if txt is None:
                    break
                trad = self.translate_auto(txt)
                self.result_queue.put(trad)
            except Empty:
                continue

    def show_translation(self, text):
        """Mostra la traduzione nella casella di testo"""
        self.result_box.configure(state="normal")
        self.result_box.delete("1.0", "end")
        self.result_box.insert("1.0", text)
        self.result_box.configure(state="disabled")
        
        # Ridimensiona la finestra in base al contenuto
        self.app.update_idletasks()
        req_h = min(300, max(100, self.result_box.winfo_reqheight() + 20))
        req_w = min(500, max(300, self.result_box.winfo_reqwidth() + 20))
        self.app.geometry(f"{req_w}x{req_h}")

    def check_queue(self):
        if not self.running:
            return  # se l'app è in chiusura, esci subito

        try:
            res = self.result_queue.get_nowait()
            self.show_translation(res)
        except Empty:
            pass

        self.queue_job = self.app.after(100, self.check_queue)


    
"""if __name__ == "__main__":
    print("=" * 50)
    print("Traduttore IT⇄EN avviato")
    print("1. Seleziona testo in qualsiasi applicazione")
    print("2. Premi F8 per tradurre")
    print("3. La finestra apparirà con la traduzione")
    print("=" * 50)
    app = TranslatorApp()
    app.start()"""