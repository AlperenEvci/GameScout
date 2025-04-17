# gamescout/ui/hud_display.py

import tkinter as tk
from tkinter import ttk # Themed Tkinter widgets
from config import settings
from utils.helpers import get_logger
import threading
import queue # For thread-safe communication

logger = get_logger(__name__)

class HudWindow(threading.Thread):
    """
    Ayrı bir thread'de Tkinter kullanarak HUD ekranını yönetir.
    """
    def __init__(self, update_queue: queue.Queue):
        super().__init__(daemon=True) # Ana program sonlandığında thread'i sonlandır
        self.update_queue = update_queue
        self.root = None
        self.info_label = None
        self._stop_event = threading.Event()

    def stop(self):
        """Thread'in durmasını sağlar."""
        self._stop_event.set()
        if self.root:
            # Tkinter ana döngüsünde destroy işlemini planla
            self.root.after(0, self.root.destroy)
        logger.info("HUD durdurma isteği alındı.")

    def run(self):
        """Tkinter penceresi için ana döngü."""
        logger.info("HUD thread başlatılıyor.")
        try:
            self.root = tk.Tk()
            self.root.title(f"{settings.APP_NAME} HUD")
            self.root.geometry(f"{settings.HUD_WIDTH}x{settings.HUD_HEIGHT}")

            # Pencereyi her zaman üstte tut
            self.root.wm_attributes("-topmost", 1)
            # Pencereyi (kısmen) şeffaf yap (işletim sistemine/pencere yöneticisine bağlı olabilir)
            try:
                self.root.attributes("-alpha", settings.HUD_TRANSPARENCY)
            except tk.TclError:
                logger.warning("Pencere şeffaflığı (-alpha) bu sistemde desteklenmiyor.")

            # HUD'u daha görünür kılmak için belirgin bir kenarlık ekle
            self.root.configure(bg="green")  # Kenarlık için parlak renk
            
            # --- HUD elemanları ekle ---
            style = ttk.Style()
            style.configure("TLabel", background="black", foreground="#00FF00", padding=5, font=('Helvetica', 10, 'bold'))  # Daha parlak metin
            style.configure("TFrame", background="black")

            main_frame = ttk.Frame(self.root, padding="5", style="TFrame")
            main_frame.pack(expand=True, fill=tk.BOTH)

            self.info_label = ttk.Label(
                main_frame,
                text="GameScout HUD başlatılıyor...",
                wraplength=settings.HUD_WIDTH - 20, # Metni pencere genişliğine sığdır
                justify=tk.LEFT,
                style="TLabel"
            )
            self.info_label.pack(pady=5, padx=5, anchor='nw')

            # İlk güncelleme kontrolünü planla
            self.root.after(settings.HUD_UPDATE_INTERVAL_MS, self.check_queue)

            logger.info("HUD penceresi oluşturuldu. Ana döngü başlatılıyor.")
            self.root.mainloop()

        except Exception as e:
            logger.error(f"HUD thread'de hata: {e}", exc_info=True)
        finally:
            logger.info("HUD thread sonlandı.")
            self.root = None # Döngü çıkışında root'un temizlendiğinden emin ol

    def check_queue(self):
        """Kuyruğu yeni metin için kontrol eder ve etiketi günceller."""
        if self._stop_event.is_set():
            logger.debug("Durdurma etkinliği ayarlandı, kuyruk kontrolü atlanıyor.")
            return # Durduruluyorsa yeniden planlamayın

        try:
            # Kuyruktaki tüm mevcut mesajları bloke olmadan işle
            while True:
                try:
                    new_text = self.update_queue.get_nowait()
                    if self.info_label and self.root: # Widget'ların hala var olup olmadığını kontrol et
                        self.info_label.config(text=new_text)
                        logger.debug(f"HUD yeni metinle güncellendi: {new_text[:50]}...")
                    self.update_queue.task_done()
                except queue.Empty:
                    break # Başka mesaj yok
                except tk.TclError as e:
                     # Widget'ın güncelleme sırasında yok edilebileceği durumları ele al
                     logger.warning(f"HUD güncellemesi sırasında Tkinter hatası (muhtemelen widget yok edildi): {e}")
                     break # Widget yoksa güncellemeyi denemeye devam etme
                except Exception as e:
                    logger.error(f"HUD güncelleme kuyruğunu işlerken hata: {e}", exc_info=True)
                    break # Beklenmeyen hatalarda potansiyel sonsuz döngüden kaçının


        except Exception as e:
            logger.error(f"check_queue içinde hata: {e}", exc_info=True)

        # Durdurulmuyorsa ve root varsa kontrolü yeniden planla
        if not self._stop_event.is_set() and self.root:
            self.root.after(settings.HUD_UPDATE_INTERVAL_MS, self.check_queue)


if __name__ == '__main__':
    # Örnek kullanım: HUD'ı başlat ve güncellemeler gönder
    print("HUD Ekranı Test Ediliyor...")
    q = queue.Queue()
    hud = HudWindow(q)
    hud.start()
    print("HUD thread başlatıldı. Test mesajları gönderiliyor...")

    try:
        # Bazı test mesajları gönder
        q.put("Test Mesajı 1: Hoş Geldiniz!")
        import time
        time.sleep(2)
        q.put("Test Mesajı 2: Bu, HUD pencere sınırları içinde güzelce sarılması gereken daha uzun bir mesajdır.")
        time.sleep(2)
        q.put("Test Mesajı 3: Tekrar güncelleniyor...")
        time.sleep(5) # Bir süre çalışmaya devam et

    except KeyboardInterrupt:
        print("\nKlavye kesintisi alındı.")
    finally:
        print("HUD durduruluyor...")
        hud.stop()
        hud.join(timeout=2) # Thread'in bitmesini bekle
        print("HUD testi tamamlandı.")
