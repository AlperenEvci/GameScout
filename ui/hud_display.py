# gamescout/ui/hud_display.py

import tkinter as tk
from tkinter import ttk, font # Themed Tkinter widgets
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
        self.theme = "dark"  # default tema

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

            # --- Tema ayarları ---
            if self.theme == "dark":
                bg_color = "#1E1E1E"  # Koyu arka plan
                fg_color = "#00FF00"  # Yeşil metin
                highlight_color = "#3700B3"  # Vurgu rengi
            else:  # light tema
                bg_color = "#F0F0F0"  # Açık arka plan
                fg_color = "#007700"  # Koyu yeşil metin
                highlight_color = "#BB86FC"  # Vurgu rengi

            # HUD'u daha görünür kılmak için belirgin bir kenarlık ekle
            self.root.configure(bg=highlight_color)  # Kenarlık için renk
            
            # --- HUD elemanları ekle ---
            style = ttk.Style()
            style.configure("TLabel", background=bg_color, foreground=fg_color, padding=5, font=('Helvetica', 10, 'bold'))
            style.configure("TFrame", background=bg_color)

            main_frame = ttk.Frame(self.root, padding="5", style="TFrame")
            main_frame.pack(expand=True, fill=tk.BOTH)

            # Başlık alanı
            header_frame = ttk.Frame(main_frame, style="TFrame")
            header_frame.pack(fill=tk.X, pady=(0, 5))
            
            title_font = font.Font(family="Helvetica", size=12, weight="bold")
            title_label = tk.Label(
                header_frame, 
                text=f"{settings.APP_NAME}", 
                font=title_font,
                background=bg_color,
                foreground=fg_color
            )
            title_label.pack(side=tk.LEFT)
            
            # Ana içerik alanı
            self.info_label = ttk.Label(
                main_frame,
                text="GameScout HUD başlatılıyor...",
                wraplength=settings.HUD_WIDTH - 20, # Metni pencere genişliğine sığdır
                justify=tk.LEFT,
                style="TLabel"
            )
            self.info_label.pack(pady=5, padx=5, anchor='nw', fill=tk.BOTH, expand=True)

            # İlk güncelleme kontrolünü planla
            self.root.after(settings.HUD_UPDATE_INTERVAL_MS, self.check_queue)

            # Klavye kısayolları ekle
            self.root.bind("<Escape>", lambda e: self.toggle_visibility())
            self.root.bind("<F1>", lambda e: self.toggle_theme())

            logger.info("HUD penceresi oluşturuldu. Ana döngü başlatılıyor.")
            self.root.mainloop()

        except Exception as e:
            logger.error(f"HUD thread'de hata: {e}", exc_info=True)
        finally:
            logger.info("HUD thread sonlandı.")
            self.root = None # Döngü çıkışında root'un temizlendiğinden emin ol

    def toggle_visibility(self):
        """HUD penceresini gizle/göster."""
        if self.root:
            if self.root.winfo_viewable():
                self.root.withdraw()  # Pencereyi gizle
                logger.debug("HUD gizlendi")
            else:
                self.root.deiconify()  # Pencereyi göster
                self.root.lift()  # Pencereyi en öne getir
                logger.debug("HUD gösterildi")

    def toggle_theme(self):
        """Tema değiştir (açık/koyu)"""
        if self.theme == "dark":
            self.theme = "light"
        else:
            self.theme = "dark"
        
        # Tema değişimi için pencereyi yeniden oluşturmalıyız
        # Bu yüzden şimdilik sadece log kaydı yapıyoruz
        logger.info(f"Tema değiştirildi: {self.theme}")
        
        # İdeal olarak, tüm widget'ların renklerini güncellememiz gerekir
        # Ama bu basit bir örnekte gözardı ediyoruz

    def format_rag_response(self, text):
        """RAG yanıtlarını daha güzel formatlar"""
        if "📝 Soru:" in text and "🔍 Yanıt:" in text:
            parts = text.split("🔍 Yanıt:")
            if len(parts) == 2:
                question_part = parts[0].replace("📝 Soru:", "").strip()
                answer_part = parts[1].strip()
                
                formatted = f"📝 SORU: {question_part}\n\n"
                formatted += f"🔍 YANIT: {answer_part}"
                return formatted
        
        return text  # Format uymazsa orijinal metni döndür

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
                        # RAG yanıtlarını formatla
                        formatted_text = self.format_rag_response(new_text)
                        self.info_label.config(text=formatted_text)
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
        time.sleep(2)
        
        # RAG formatında test mesajı
        rag_test = """
📝 Soru: Shadowheart kimdir?

🔍 Yanıt: 
Shadowheart, Shar'a tapan ve gruptaki ana rahip (Cleric) karakteri olan bir Yarı-Elf'tir. 
Gizli bir geçmişe sahiptir ve Absolute'a ibadet eden kült ile bağlantıları vardır. 
Karanlık ve gizemli bir kişiliğe sahiptir, ancak zamanla karakterinize bağlılık geliştirebilir.
        """
        q.put(rag_test)
        time.sleep(5) # Bir süre çalışmaya devam et

    except KeyboardInterrupt:
        print("\nKlavye kesintisi alındı.")
    finally:
        print("HUD durduruluyor...")
        hud.stop()
        hud.join(timeout=2) # Thread'in bitmesini bekle
        print("HUD testi tamamlandı.")
