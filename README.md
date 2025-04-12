# GameScout - Agentic AI Oyun Asistanı

GameScout, Baldur's Gate 3 gibi RPG oyunları için geliştirilen gerçek zamanlı bir yapay zeka asistanıdır. Oyuncunun ekranını analiz eder, ilgili forumlardan bilgi toplar, görevler ve stratejiler hakkında öneriler sunar ve basit bir HUD (Heads-Up Display) aracılığıyla bilgi sağlar.

## Özellikler (Planlanan)

- Gerçek zamanlı ekran görüntüsü alma ve OCR ile metin analizi.
- Oyun içi olayları (bölge değişimi, görev güncellemeleri) algılama.
- Reddit, Fextralife gibi kaynaklardan ilgili görev/build bilgilerini çekme.
- Oyuncunun karakter sınıfına ve mevcut duruma göre kişiselleştirilmiş öneriler sunma.
- Oyun üzerinde temel bilgileri gösteren basit bir arayüz (HUD).

## Kurulum

1.  **Depoyu Klonla:**
    ```bash
    git clone <repository_url>
    cd GameScout
    ```
2.  **Gerekli Kütüphaneleri Yükle:**
    ```bash
    pip install -r requirements.txt
    ```
3.  **Tesseract OCR Kurulumu:**
    - [Tesseract OCR](https://github.com/tesseract-ocr/tesseract#installing-tesseract) indirin ve kurun.
    - Windows'ta, Tesseract kurulum dizinini sistem PATH'ine ekleyin veya `gamescout/config/settings.py` dosyasında yolunu belirtin.
    - Gerekli dil verilerini (örn. İngilizce, Türkçe) yüklediğinizden emin olun.

## Kullanım

Uygulamayı ana dizinden çalıştırın:

```bash
python gamescout/main.py
```
