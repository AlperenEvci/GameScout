# gamescout/capture/ocr_processor.py

import pytesseract
from PIL import Image
from config import settings
from utils.helpers import get_logger, clean_text

logger = get_logger(__name__)

# Tesseract yolu ayarlandıysa yapılandır
if settings.TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
    logger.info(f"Tesseract yolu kullanılıyor: {settings.TESSERACT_CMD}")
else:
    logger.warning("Tesseract yolu ayarlanmamış!")

def extract_text_from_image(image: Image.Image) -> str:
    """
    Tesseract OCR kullanarak bir PIL Image nesnesinden metin çıkarır.

    Args:
        image: İşlenecek PIL Image nesnesi.

    Returns:
        Çıkarılan metin bir dize olarak, veya bir hata oluşursa veya metin bulunamazsa boş bir dize.
    """
    if image is None:
        logger.warning("OCR işleme için None görüntü alındı.")
        return ""
    try:
        # Hata ayıklama için görüntü detaylarını kaydet
        logger.info(f"OCR için görüntü işleniyor: Boyut={image.size}, Mod={image.mode}")
        
        # Ön işleme adımları burada eklenebilir (örn., gri tonlama, eşikleme)
        # image = image.convert('L') # Örnek: Gri tonlamaya dönüştür
        # custom_config = r'--oem 3 --psm 6' # Örnek Tesseract yapılandırması
        
        # Hata ayıklama için geçerli görüntünün bir kopyasını kaydet
        debug_path = "ocr_debug_image.png"
        image.save(debug_path)
        logger.info(f"Hata ayıklama görüntüsü şuraya kaydedildi {debug_path}")
        
        text = pytesseract.image_to_string(image, lang=settings.OCR_LANGUAGE) #, config=custom_config)
        cleaned = clean_text(text)
        
        # Hata ayıklama için tam metni kaydet
        logger.info(f"OCR çıkarılan tam metin: {cleaned}")
        
        return cleaned
    except pytesseract.TesseractNotFoundError:
        logger.error("Tesseract Hatası: Tesseract yürütülebilir dosyası bulunamadı veya doğru yapılandırılmadı.")
        logger.error(f"Lütfen Tesseract'ın kurulu olduğundan ve '{settings.TESSERACT_CMD}' yolunun (ayarlandıysa) doğru olduğundan emin olun.")
        # Belirli bir istisna fırlatmayı veya özel bir değer döndürmeyi düşünün
        return "TESSERACT_ERROR"
    except Exception as e:
        logger.error(f"OCR işleme sırasında hata: {e}", exc_info=True)
        return ""

if __name__ == '__main__':
    # Örnek kullanım: Test görüntüsü yükle ve metin çıkar
    print("OCR işleyici test ediliyor...")
    try:
        # Test için bir kukla görüntü oluşturun veya bir tane yükleyin
        # img = Image.new('RGB', (600, 150), color = 'white')
        # d = ImageDraw.Draw(img)
        # d.text((10,10), "OCR Testinden Merhaba Dünya", fill=(0,0,0))
        # img.save("test_ocr_input.png")

        test_image_path = "test_screenshot.png" # screen_capture'ın bunu oluşturduğunu varsayar
        img = Image.open(test_image_path)
        extracted = extract_text_from_image(img)
        print(f"'{test_image_path}' dosyasından çıkarılan metin:\n---\n{extracted}\n---")
    except FileNotFoundError:
        print(f"Hata: Test görüntüsü '{test_image_path}' bulunamadı. Önce screen_capture.py'yi çalıştırın veya geçerli bir görüntü sağlayın.")
    except Exception as e:
        print(f"OCR testi sırasında bir hata oluştu: {e}")
