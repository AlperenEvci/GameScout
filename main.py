# gamescout/main.py

import time
import queue
import sys
from config import settings
from utils.helpers import get_logger
from capture import screen_capture, ocr_processor
from agent import decision_engine
from ui import hud_display
# from data import forum_scraper # İhtiyaç olduğunda ana döngüde içe aktarın

logger = get_logger(settings.APP_NAME)

def check_dependencies():
    """Tüm gerekli bağımlılıkların mevcut olup olmadığını kontrol et."""
    # Tesseract'ın yapılandırılıp yapılandırılmadığını kontrol et
    if not settings.TESSERACT_CMD:
        logger.error("Tesseract OCR bulunamadı! GameScout, metin tanıma için Tesseract OCR gerektirir.")
        print("\n==== Tesseract OCR Bulunamadı ====")
        print("GameScout, metin tanıma için Tesseract OCR gerektirir. Lütfen:")
        print("1. Tesseract OCR'yi buradan indirin: https://github.com/UB-Mannheim/tesseract/wiki")
        print("2. Kurun (önerilen yol: C:\\Program Files\\Tesseract-OCR\\)")
        print("3. GameScout'u yeniden başlatın")
        print("\nTesseract zaten özel bir konuma kuruluysa, config/settings.py içindeki TESSERACT_CMD'yi güncelleyin")
        print("=================================\n")
        return False
        
    # Türkçe dil verilerinin mevcut olup olmadığını kontrol et
    if settings.OCR_LANGUAGE == 'tur':
        try:
            import pytesseract
            import tempfile
            from PIL import Image, ImageDraw
            
            # Türkçe metinli geçici bir görüntü oluştur
            img = Image.new('RGB', (200, 50), color='white')
            d = ImageDraw.Draw(img)
            d.text((10, 10), "Test Türkçe", fill=(0, 0, 0))
            
            # Türkçe dil ile OCR yapmayı dene
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
            result = pytesseract.image_to_string(img, lang='tur')
            logger.info("Türkçe dil desteği doğrulandı.")
        except Exception as e:
            logger.error(f"Türkçe dil verileri kurulu olmayabilir: {e}")
            print("\n==== Türkçe Dil Verileri Bulunamadı ====")
            print("GameScout Türkçe OCR kullanacak şekilde yapılandırıldı, ancak dil verileri kurulu olmayabilir.")
            print("Türkçe dil verilerini kurmak için:")
            print("1. Türkçe verileri buradan indirin: https://github.com/tesseract-ocr/tessdata/")
            print("2. 'tur.traineddata' dosyasını Tesseract 'tessdata' klasörüne yerleştirin")
            print("   (Genellikle C:\\Program Files\\Tesseract-OCR\\tessdata\\)")
            print("3. GameScout'u yeniden başlatın")
            print("\nAlternatif olarak, config/settings.py içindeki OCR_LANGUAGE'ı 'eng' olarak değiştirebilirsiniz")
            print("===========================================\n")
            return False
            
    return True

def main_loop():
    """GameScout için ana yürütme döngüsü."""
    logger.info(f"{settings.APP_NAME} v{settings.VERSION} başlatılıyor")
    
    # Başlamadan önce bağımlılıkları kontrol et
    if not check_dependencies():
        logger.error("Kritik bağımlılık eksik. Çıkılıyor.")
        return

    # Ana döngü ve HUD iş parçacığı arasındaki iletişim için iş parçacığı güvenli kuyruk
    hud_update_queue = queue.Queue()

    # Bileşenleri başlat
    game_state = decision_engine.GameState()
    hud = hud_display.HudWindow(hud_update_queue)
    hud.start() # HUD iş parçacığını başlat

    try:
        # İlk mesaj
        hud_update_queue.put("GameScout Başlatılıyor...")

        while True:
            start_time = time.time()
            logger.debug("--- Ana Döngü Yinelemesi Başlangıcı ---")

            # 1. Ekranı Yakala
            screenshot = screen_capture.take_screenshot()

            if screenshot:
                # 2. OCR İşle
                ocr_text = ocr_processor.extract_text_from_image(screenshot)

                if ocr_text == "TESSERACT_ERROR":
                    logger.error("Tesseract hatası tespit edildi. Uygulama durduruluyor.")
                    hud_update_queue.put("HATA: Tesseract bulunamadı veya yapılandırılmadı. Çıkılıyor.")
                    break # Kritik hatada döngüden çık

                if ocr_text:
                    # 3. Oyun Durumunu Güncelle
                    game_state.update_from_ocr(ocr_text) # Şimdilik temel güncelleme
                    logger.debug(f"Mevcut Oyun Durumu: {game_state}")

                    # 4. Önerileri Oluştur (Agent Mantığı)
                    recommendations = decision_engine.generate_recommendations(game_state)

                    # 5. Biçimlendir ve HUD'a Gönder
                    hud_text = f"Bölge: {game_state.current_region or 'Bilinmiyor'}\n\n"
                    
                    # Yakındaki önemli noktaları ekle
                    if game_state.nearby_points_of_interest:
                        hud_text += "Yakındaki Önemli Noktalar:\n"
                        for i, poi in enumerate(game_state.nearby_points_of_interest[:3]):
                            hud_text += f"• {poi['name']}\n"
                        hud_text += "\n"
                    
                    # Bölgedeki görevleri ekle
                    if game_state.region_quests:
                        hud_text += "Bölge Görevleri:\n"
                        for i, quest in enumerate(game_state.region_quests[:2]):
                            hud_text += f"• {quest['name']}\n"
                        hud_text += "\n"
                    
                    # Önerileri ekle
                    if recommendations:
                        hud_text += "Öneriler:\n" + "\n".join(f"• {rec}" for rec in recommendations)
                    else:
                        hud_text += "Öneriler: Şu an mevcut değil."
                    
                    hud_update_queue.put(hud_text)
                else:
                    logger.debug("Ekran görüntüsünde metin bulunamadı.")
                    # İsteğe bağlı olarak HUD'a bir "Taranıyor..." mesajı gönder veya son mesajı koru
                    # hud_update_queue.put(f"Bölge: {game_state.current_region or 'Bilinmiyor'}\n\nTaranıyor...")


            else:
                logger.warning("Bu döngüde ekran görüntüsü alınamadı.")
                hud_update_queue.put("Ekran yakalama hatası...")


            # Geçen süreyi hesapla ve ona göre bekle
            end_time = time.time()
            elapsed_time = end_time - start_time
            sleep_time = max(0, settings.SCREENSHOT_INTERVAL_SECONDS - elapsed_time)
            logger.debug(f"Döngü yinelemesi {elapsed_time:.2f}s sürdü. {sleep_time:.2f}s uyuluyor.")
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        logger.info("Klavye kesintisi alındı. Kapatılıyor...")
    except Exception as e:
        logger.critical(f"Ana döngüde beklenmeyen bir hata oluştu: {e}", exc_info=True)
        try:
            # Çıkmadan önce HUD aracılığıyla kullanıcıyı bilgilendirmeyi dene
             hud_update_queue.put(f"KRİTİK HATA: {e}\nÇıkılıyor.")
             time.sleep(1) # HUD'a potansiyel olarak görüntüleme zamanı ver
        except Exception:
            pass # Kapatma bildirimi sırasındaki hataları yoksay
    finally:
        logger.info("HUD iş parçacığı durduruluyor...")
        hud.stop()
        hud.join(timeout=2) # HUD iş parçacığının bitmesini bekle
        logger.info(f"{settings.APP_NAME} tamamlandı.")


if __name__ == "__main__":
    main_loop()