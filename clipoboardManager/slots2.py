import os
import threading
import keyboard as kb
import win32clipboard as cp
import win32con  # for CF_UNICODETEXT
import pyautogui as pya
import time

class ClipboardManager:
    """
    A clipboard slot manager with start() and stop() methods.
    Ctrl+Shift+<n>: save selection to slot n
    Ctrl+Shift+F<n+1>: paste from slot n (e.g., Ctrl+Shift+F1 pastes from slot 0, F10 pastes from slot 9)
    """
    def __init__(self, slots_path="slots.txt", num_slots=10):
        self.slots_path = slots_path
        self.num_slots = num_slots
        self._stop_event = threading.Event()
        self._original_clipboard = None

        # Verifica che il nome file sia valido
        if not self.slots_path or not isinstance(self.slots_path, str):
            raise ValueError("Il percorso del file dei slot non è valido.")

        # initialize slots file
        if not os.path.isfile(self.slots_path):
            with open(self.slots_path, "w", encoding="utf-8") as f:
                f.write("\n" * self.num_slots)
            print(f"Created {self.slots_path} with {self.num_slots} empty slots.")
        else:
            print(f"Loaded existing {self.slots_path}")

        # load into memory
        try:
            with open(self.slots_path, "r", encoding="utf-8") as f:
                self.slots = f.read().splitlines()
        except Exception as e:
            print(f"Errore durante la lettura di {self.slots_path}: {e}")
            raise

        # ensure correct length
        self.slots += [""] * (self.num_slots - len(self.slots))

    def _get_clipboard_text(self):
        text = ""
        for _ in range(3):  # Ritenta fino a 3 volte
            try:
                cp.OpenClipboard()
                if cp.IsClipboardFormatAvailable(win32con.CF_UNICODETEXT):
                    text = cp.GetClipboardData(win32con.CF_UNICODETEXT)
                cp.CloseClipboard()
                if text and text != self._original_clipboard:
                    break
                elif text == self._original_clipboard:
                    print("failed to get new clipboard text, retrying...")
                time.sleep(0.1)
            except Exception as e:
                print(f"Errore durante la lettura della clipboard: {e}")
                time.sleep(0.1)
                try:
                    cp.CloseClipboard()
                except:
                    pass
            time.sleep(0.1)
        return text

    def _set_clipboard_text(self, text):
        for _ in range(3):  # Ritenta fino a 3 volte
            try:
                cp.OpenClipboard()
                cp.EmptyClipboard()
                cp.SetClipboardData(win32con.CF_UNICODETEXT, text)
                cp.CloseClipboard()
                return True
            except Exception as e:
                print(f"Errore durante la scrittura nella clipboard: {e}")
                time.sleep(0.1)
                try:
                    cp.CloseClipboard()
                except:
                    pass
        return False

    def _save_clipboard(self):
        """Salva il contenuto attuale della clipboard"""
        try:
            self._original_clipboard = self._get_clipboard_text()
        except:
            self._original_clipboard = ""

    def _restore_clipboard(self):
        """Ripristina il contenuto originale della clipboard"""
        if self._original_clipboard is not None:
            self._set_clipboard_text(self._original_clipboard)

    def copy_selection(self):
        """Copy currently selected text to the system clipboard."""
        self._save_clipboard()  # Salva prima il contenuto attuale
        
        # Esegui la copia
        pya.hotkey("ctrl", "c")
        time.sleep(0.2)  # Attendi che la copia venga completata
        
        # Leggi il nuovo contenuto
        text = self._get_clipboard_text()
        return text

    def set_slot(self, idx):
        """Copy selection and store into slots[idx], then persist to file."""
        text = self.copy_selection()
        if text:
            self.slots[idx] = text
            with open(self.slots_path, "w", encoding="utf-8") as f:
                f.write("\n".join(self.slots))
            print(f"Slot {idx} saved: {repr(text)[:50]}")
        else:
            print(f"Impossibile salvare nello slot {idx}: testo non copiato")
        
        # Ripristina clipboard originale
        self._restore_clipboard()

    def get_slot(self, idx):
        """Put slots[idx] into clipboard and paste it."""
        if idx < len(self.slots):
            text = self.slots[idx]
            if text:
                self._save_clipboard()  # Salva clipboard attuale
                
                if self._set_clipboard_text(text):
                    time.sleep(0.2)  # Attendi che la clipboard sia pronta
                    
                    # Usa send_keys invece di hotkey per maggiore affidabilità
                    try:
                        # Metodo 1: usa pya.write direttamente (più affidabile in certi contesti)
                        # pya.write(text)
                        
                        # Metodo 2: usa Ctrl+V standard
                        pya.keyDown('ctrl')
                        pya.press('v')
                        pya.keyUp('ctrl')
                        
                        print(f"Pasted slot {idx}: {repr(text)[:50]}")
                    except Exception as e:
                        print(f"Errore durante l'incollaggio: {e}")
                    
                    # Attendi che l'incollaggio sia completato 
                    time.sleep(0.3)
                    
                    # Ripristina clipboard originale dopo un breve ritardo
                    self._restore_clipboard()
                else:
                    print(f"Errore nell'impostare la clipboard per lo slot {idx}")
            else:
                print(f"Slot {idx} è vuoto")
        else:
            print(f"Indice slot {idx} non valido")

    def start(self):
        """Register hotkeys and block until stop() is called."""
        # register hotkeys
        for i in range(self.num_slots):
            kb.add_hotkey(f"ctrl+shift+{i}", lambda i=i: self.set_slot(i))
            # Usa i tasti funzione F1-F10 per incollare (F1 per slot 0, F2 per slot 1, ecc.)
            if i < 9:
                kb.add_hotkey(f"ctrl+shift+f{i+1}", lambda i=i: self.get_slot(i))
            else:
                kb.add_hotkey(f"ctrl+shift+f10", lambda i=i: self.get_slot(i))
        kb.add_hotkey("esc", self.stop)
        print("Hotkeys registered. ClipboardManager started.")
        print("Usa Ctrl+Shift+<n> per salvare nello slot n")
        print("Usa Ctrl+Shift+F<n+1> per incollare dallo slot n (es: Ctrl+Shift+F1 per slot 0, F10 per slot 9)")
        print("Premi ESC per uscire.")
        # block until stop
        self._stop_event.wait()
        print("ClipboardManager stopped. Hotkeys removed.")

    def stop(self):
        """Unregister all hotkeys and unblock start()."""
        kb.clear_all_hotkeys()
        self._stop_event.set()


# Example usage:
if __name__ == '__main__':
    mgr = ClipboardManager()
    try:
        mgr.start()
    except KeyboardInterrupt:
        mgr.stop()
