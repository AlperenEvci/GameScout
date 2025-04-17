# gamescout/agent/decision_engine.py

from config import settings
from utils.helpers import get_logger
import random
import time
from data import map_data  # Yeni map_data modülünü içe aktar
from data.map_data import get_nearby_points_of_interest, get_quests_for_region
from data.web_search import search_game_content, get_region_information
from llm.api_client import LLMAPIClient
import re

logger = get_logger(__name__)

class GameState:
    """Oyunun mevcut algılanan durumunu temsil eder."""
    def __init__(self):
        self.current_region: str | None = None
        self.active_quests: list[str] = []
        self.character_class: str = settings.DEFAULT_CHARACTER_CLASS
        self.last_ocr_text: str = ""
        self.detected_keywords: list[str] = []
        self.last_tip_time = 0
        self.recent_tips = []  # Tekrarı önlemek için son gösterilen ipuçlarını sakla
        self.last_location_check_time = 0  # En son konum bilgisi güncellenme zamanı
        self.nearby_points_of_interest = []  # Yakındaki önemli noktalar
        self.region_quests = []  # Bölgedeki görevler
        # İhtiyaç duyuldukça daha fazla durum değişkeni ekleyin (örn. oyuncu sağlığı, seviye, envanter)

    def update_from_ocr(self, text: str):
        """OCR metin analizine dayalı oyun durumunu günceller."""
        self.last_ocr_text = text
        logger.debug("OCR metninden oyun durumu güncelleniyor...")
        
        # Hata ayıklama için OCR metninin uzunluğunu kaydet
        text_length = len(text.strip())
        logger.info(f"Alınan OCR metni uzunluğu: {text_length} karakter")
        
        if text_length == 0:
            logger.warning("Boş OCR metni alındı - oyun durumu güncellemesi mümkün değil")
            return
            
        # --- Bölge, görevleri vb. ayrıştırmak için mantık ekleyin ---
        # Önceki tespit edilen anahtar kelimeleri temizle
        self.detected_keywords = []
        
        # Bölge tespiti
        previous_region = self.current_region
        
        # OCR temizleme - renkli/ANSI kodları ve gereksiz karakterleri temizle
        # Bu kısım kritik - OCR çıktısı yeşil renkli ve karmaşık formatlar içerebilir
        cleaned_text = self._clean_ocr_text(text)
        
        # OCR varyasyonlarını daha iyi karşılamak için düşük seviyeye getir
        text_lower = cleaned_text.lower()
        
        # Bölge tespiti geliştirme - BG3'e özgü bölge isimleri
        bg3_regions = {
            # İngilizce bölge adları
            "ravaged beach": "Ravaged Beach",
            "emerald grove": "Emerald Grove", 
            "blighted village": "Blighted Village", 
            "moonrise towers": "Moonrise Towers",
            "underdark": "Underdark", 
            "grymforge": "Grymforge", 
            "shadowfell": "Shadowfell", 
            "gauntlet of shar": "Gauntlet of Shar",
            "githyanki creche": "Githyanki Creche",
            "last light inn": "Last Light Inn", 
            "wyrm's rock": "Wyrm's Rock",
            "wyrms rock": "Wyrm's Rock",  # Apostrof olmadan alternatif yazım
            "shadow-cursed lands": "Shadow-Cursed Lands", 
            "baldur's gate": "Baldur's Gate",
            "baldurs gate": "Baldur's Gate",  # Apostrof olmadan alternatif yazım
            
            # Türkçe bölge adları
            "harap sahil": "Ravaged Beach",
            "zumrut koru": "Emerald Grove",  # ü olmadan alternatif yazım
            "zümrüt koru": "Emerald Grove",
            "lanetli köy": "Blighted Village",
            "lanetli koy": "Blighted Village",  # ö olmadan alternatif yazım
            "ay doğuşu kuleleri": "Moonrise Towers",
            "ay dogusu kuleleri": "Moonrise Towers",  # ğ, ü olmadan alternatif yazım
            "yeraltı diyarı": "Underdark",
            "yeralti diyari": "Underdark",  # ı, ğ olmadan alternatif yazım
            "grym demirhanesi": "Grymforge",
            "gölge düşüşü": "Shadowfell",
            "golge dususu": "Shadowfell",  # ö, ü, ş olmadan alternatif yazım
            "shar'ın eldiveni": "Gauntlet of Shar",
            "sharin eldiveni": "Gauntlet of Shar",  # ' olmadan alternatif yazım
            "githyanki beşiği": "Githyanki Creche",
            "githyanki besigi": "Githyanki Creche",  # ş, ğ olmadan alternatif yazım
            "son ışık hanı": "Last Light Inn",
            "son isik hani": "Last Light Inn",  # ı, ş olmadan alternatif yazım
            "ejderha kayası": "Wyrm's Rock",
            "ejderha kayasi": "Wyrm's Rock",  # ı olmadan alternatif yazım
            "gölge-lanetli topraklar": "Shadow-Cursed Lands",
            "golge-lanetli topraklar": "Shadow-Cursed Lands",  # ö olmadan alternatif yazım
            "gölge lanetli topraklar": "Shadow-Cursed Lands",  # tire olmadan alternatif yazım
        }
        
        # 1. Metin içinde doğrudan bir bölge adı var mı kontrol et
        region_detected = False
        
        # Doğrudan tam eşleşme kontrolü
        for region_name, region_key in bg3_regions.items():
            if region_name in text_lower:
                self.current_region = region_key
                logger.info(f"BG3 bölgesi tespit edildi: '{region_name}' -> '{region_key}'")
                region_detected = True
                break
        
        # 2. "Bölge:" veya "location:" gibi anahtar kelimeler etrafında bölge adı arama
        if not region_detected:
            # Bölge etiketlerini içeren metni ara
            region_labels = [
                "bölge:", "bolge:", "bölgeye giriş:", "bolgeye giris:",
                "konum:", "location:", "region:", "entering region:"
            ]
            
            for label in region_labels:
                if label in text_lower:
                    # Etiketten sonraki metni al
                    parts = text_lower.split(label, 1)
                    if len(parts) > 1:
                        after_label = parts[1].strip()
                        # İlk 30 karakter içinde bölge adını ara (yeni satır veya nokta ile sınırla)
                        region_text = after_label.split("\n")[0].split(".")[0][:30].strip()
                        
                        # Bu bölge metni bildiğimiz bir bölge adıyla eşleşiyor mu?
                        for region_name, region_key in bg3_regions.items():
                            if (region_name in region_text or 
                                self._fuzzy_region_match(region_text, region_name)):
                                self.current_region = region_key
                                logger.info(f"Etiket '{label}' sonrası bölge tespit edildi: '{region_text}' -> '{region_key}'")
                                region_detected = True
                                break
                    if region_detected:
                        break
        
        # 3. "Yeni Görev" veya "New Quest" gibi ipuçlarında bölge adı olabilir
        if not region_detected:
            quest_triggers = [
                "yeni görev:", "görev güncellendi:", "yeni gorev:", "gorev guncellendi:",
                "new quest:", "quest updated:", "mission:"
            ]
            
            for trigger in quest_triggers:
                if trigger in text_lower:
                    # Tetikleyiciden sonraki metni al
                    parts = text_lower.split(trigger, 1)
                    if len(parts) > 1:
                        after_trigger = parts[1].strip()
                        # İlk 50 karakter içinde bölge adını ara
                        for region_name, region_key in bg3_regions.items():
                            if (region_name in after_trigger[:50] or 
                                self._fuzzy_region_match(after_trigger[:50], region_name)):
                                self.current_region = region_key
                                logger.info(f"Görev tetikleyicisi '{trigger}' içinde bölge tespit edildi: '{region_name}' -> '{region_key}'")
                                region_detected = True
                                break
                    if region_detected:
                        break
        
        # 4. Bulanık eşleştirme - metin içinde herhangi bir yerde kısmi bölge adı ara
        if not region_detected:
            for region_name, region_key in bg3_regions.items():
                # Birden fazla kelimeden oluşan bölge adları için her bir kelimeyi kontrol et
                words = region_name.split()
                if len(words) > 1:
                    matches = 0
                    important_words = 0
                    
                    for word in words:
                        if len(word) > 3:  # Önemli kelimeler (3 harften uzun)
                            important_words += 1
                            # Kelimenin kendisi veya benzeri var mı?
                            if word in text_lower or self._fuzzy_word_match(text_lower, word):
                                matches += 1
                    
                    # Eşleşme puanı hesapla - önemli kelimelerin en az %70'i eşleşmeli
                    if important_words > 0 and matches / important_words >= 0.7:
                        self.current_region = region_key
                        match_percent = (matches / important_words) * 100
                        logger.info(f"Bulanık kelime eşleştirmesi ile bölge tespit edildi: '{region_name}' -> '{region_key}' (%{match_percent:.1f} eşleşme)")
                        region_detected = True
                        break
                
                # Tek kelimelik bölge adları için kısmi eşleşme kontrolü
                elif len(region_name) > 5:  # Yalnızca uzun tek kelimeler
                    similarity = self._string_similarity(text_lower, region_name)
                    if similarity > 0.7:  # %70'den fazla benzerlik
                        self.current_region = region_key
                        logger.info(f"Metin benzerliği ile bölge tespit edildi: '{region_name}' -> '{region_key}' (%{similarity*100:.1f} benzerlik)")
                        region_detected = True
                        break
        
        # 5. Son çare: Özel BG3 anahtar kelimeleri (tek başına)
        if not region_detected:
            # Oyunda geçen özel yer/NPC adları veya anahtar kelimeler (bölge ile ilişkilendirilmiş)
            bg3_keywords = {
                "halsin": "Emerald Grove",
                "zevlor": "Emerald Grove",
                "kagha": "Emerald Grove",
                "arka": "Emerald Grove",
                "goblin camp": "Blighted Village",
                "goblin kamp": "Blighted Village",
                "dank crypt": "Blighted Village",
                "rutubetli kripta": "Blighted Village",
                "minthara": "Moonrise Towers",
                "ketheric": "Moonrise Towers",
                "myconid colony": "Underdark",
                "mikonid kolonisi": "Underdark",
                "glut": "Underdark",
                "auntie ethel": "Emerald Grove",
                "teyze ethel": "Emerald Grove",
                "isobel": "Last Light Inn",
                "shar": "Gauntlet of Shar",
                "nightsong": "Shadow-Cursed Lands",
                "jaheira": "Last Light Inn"
            }
            
            for keyword, region in bg3_keywords.items():
                if keyword in text_lower:
                    self.current_region = region
                    logger.info(f"BG3 anahtar kelimesi ile bölge tespit edildi: '{keyword}' -> '{region}'")
                    region_detected = True
                    break
        
        # Konum değiştiyse veya uzun süre geçtiyse harita bilgilerini güncelle
        current_time = time.time()
        if (self.current_region != previous_region or 
            current_time - self.last_location_check_time > 300):  # 5 dakikada bir güncelle
            
            if self.current_region != previous_region and previous_region is not None:
                logger.info(f"Bölge değişti: '{previous_region}' -> '{self.current_region}'")
                
            self.update_location_data()
            self.last_location_check_time = current_time
        
        # Metinden ilginç anahtar kelimeleri çıkar (Türkçe ve İngilizce)
        interesting_keywords = [
            # İngilizce anahtar kelimeler
            "quest", "mission", "objective", "enemy", "gold", "weapon", "armor", 
            "character", "health", "magic", "skill", "battle", "dialog", "choice",
            "companion", "camp", "rest", "spell", "attack", "defend", "loot", "chest",
            "trap", "lock", "stealth", "hidden", "secret", "map", "journal", "party",
            "inventory", "level up", "ability", "saving throw", "roll", "dice",
            
            # Türkçe anahtar kelimeler
            "görev", "gorev", "misyon", "hedef", "düşman", "dusman", "altın", "altin", "silah", "zırh", "zirh", "karakter", 
            "sağlık", "saglik", "büyü", "buyu", "yetenek", "beceri", "savaş", "savas", "diyalog", "seçim", "secim", 
            "yoldaş", "yoldas", "kamp", "dinlenme", "büyü", "buyu", "saldırı", "saldiri", "savunma", "ganimet", 
            "sandık", "sandik", "hazine", "tuzak", "kilit", "gizlilik", "gizli", "sır", "sir", "harita", 
            "günlük", "gunluk", "parti", "grup", "envanter", "seviye atlama", "yetenek", 
            "kurtarma zarı", "kurtarma zari", "zar", "konum", "bölge", "bolge"
        ]
        
        for keyword in interesting_keywords:
            if keyword.lower() in text_lower:
                logger.info(f"OCR metninde '{keyword}' anahtar kelimesi tespit edildi")
                self.detected_keywords.append(keyword)
        
        # Görev tespit mantığı (Türkçe ve İngilizce)
        quest_triggers = [
            # İngilizce
            "new quest", "quest updated", "journal updated", "mission acquired",
            # Türkçe
            "yeni görev", "yeni gorev", "görev güncellendi", "gorev guncellendi", "günlük güncellendi", "gunluk guncellendi", 
            "görev alındı", "gorev alindi", "misyon başladı", "misyon basladi", "görev başladı", "gorev basladi", 
            "görev tamamlandı", "gorev tamamlandi"
        ]
        
        for trigger in quest_triggers:
            if trigger.lower() in text_lower:
                logger.info(f"Görev aktivitesi tespit edildi: '{trigger}'")
                self.detected_keywords.append("quest_update")
                break
    
    def _clean_ocr_text(self, text):
        """OCR metnini temizler - ANSI renk kodları, escape karakterleri vs. kaldırılır."""
        # ANSI renk ve format kodlarını kaldır
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        text = ansi_escape.sub('', text)
        
        # Terminale özgü kontrol karakterlerini kaldır (örn: ^M, ^G vb.)
        text = re.sub(r'[\x00-\x1F\x7F]', '', text)
        
        # Birden fazla boşluk, sekme ve yeni satırı tek bir boşlukla değiştir
        text = re.sub(r'\s+', ' ', text)
        
        # OCR'de yaygın olarak karıştırılan karakterleri düzelt
        replacements = {
            '0': 'o',  # Sıfır -> küçük o
            'l': 'i',  # küçük L -> küçük i
            '1': 'i',  # Bir -> küçük i
            '@': 'a',  # at işareti -> küçük a
            '$': 's',  # dolar işareti -> küçük s
            # Diğer yaygın OCR hataları burada eklenebilir
        }
        
        # Türkçe karakterlerin ASCII karşılıklarını kabul et
        tr_replacements = {
            'ı': 'i',
            'i̇': 'i',  # noktalı i karakteri
            'ö': 'o',
            'ü': 'u',
            'ş': 's',
            'ç': 'c',
            'ğ': 'g',
            # Büyük harfler için de
            'İ': 'I',
            'Ö': 'O',
            'Ü': 'U',
            'Ş': 'S',
            'Ç': 'C',
            'Ğ': 'G'
        }
        
        # Tüm karakter değişimlerini uygula
        for old, new in {**replacements, **tr_replacements}.items():
            text = text.replace(old, new)
        
        # Gereksiz noktalama işaretlerini temizle
        text = re.sub(r'[^\w\s\.]', ' ', text)
        
        logger.debug(f"OCR metni temizlendi - Orijinal uzunluk: {len(text)}")
        return text
        
    def _fuzzy_region_match(self, text, region_name):
        """Bulanık bölge eşleştirme - bölge adı ve metin arasındaki benzerliği kontrol eder."""
        # Bölge adı kelimelerinin en az %60'ı metinde varsa eşleşme kabul et
        words = region_name.split()
        if len(words) <= 1:
            return False
            
        matches = 0
        for word in words:
            if len(word) > 2 and (word in text or self._fuzzy_word_match(text, word)):
                matches += 1
                
        match_ratio = matches / len(words)
        return match_ratio >= 0.6
        
    def _fuzzy_word_match(self, text, word):
        """Bulanık kelime eşleştirme - metin içinde kelimenin benzeri var mı kontrol eder."""
        if len(word) <= 3:
            return False  # Çok kısa kelimeler için bulanık eşleştirme yapmıyoruz
            
        # Kelimenin ilk 2/3'ünü ve son 2/3'ünü metin içinde ara
        word_lower = word.lower()
        prefix_len = max(2, int(len(word) * 0.67))
        suffix_len = max(2, int(len(word) * 0.67))
        
        prefix = word_lower[:prefix_len]
        suffix = word_lower[-suffix_len:]
        
        # Prefix veya suffix metin içinde geçiyorsa bu bir eşleşmedir
        return prefix in text or suffix in text
        
    def _string_similarity(self, s1, s2):
        """İki metin arasındaki benzerlık oranını hesapla."""
        # Levenshtein mesafesi yerine basitleştirilmiş bir benzerlik ölçüsü kullanıyoruz
        if not s1 or not s2:
            return 0.0
            
        # Her iki metinde de geçen karakter sayısını hesapla
        s1_chars = set(s1.lower())
        s2_chars = set(s2.lower())
        
        common_chars = len(s1_chars.intersection(s2_chars))
        total_chars = len(s1_chars.union(s2_chars))
        
        if total_chars == 0:
            return 0.0
            
        return common_chars / total_chars
            
    def update_location_data(self):
        """Mevcut bölge için harita verilerini günceller."""
        if not self.current_region:
            logger.debug("Tespit edilmiş bölge yok, konum verisi güncellemesi atlanıyor")
            return
            
        logger.info(f"Şu bölge için konum verileri güncelleniyor: {self.current_region}")
        
        # Bölge için önemli noktaları getir
        self.nearby_points_of_interest = map_data.get_nearby_points_of_interest(self.current_region)
        logger.debug(f"{len(self.nearby_points_of_interest)} önemli nokta bulundu")
        
        # Bölgeye ait görevleri getir
        self.region_quests = map_data.get_quests_for_region(self.current_region)
        logger.debug(f"Bu bölge için {len(self.region_quests)} görev bulundu")

    def add_recent_tip(self, tip):
        """Tekrarı önlemek için son gösterilen ipuçlarını takip et"""
        self.recent_tips.append(tip)
        # Listeyi sonsuz büyümesini önlemek için sadece son 10 ipucunu tut
        if len(self.recent_tips) > 10:
            self.recent_tips.pop(0)

    def was_recently_shown(self, tip):
        """Bir ipucunun yakın zamanda gösterilip gösterilmediğini kontrol et"""
        return tip in self.recent_tips

    def __str__(self):
        return (f"OyunDurumu(Bölge: {self.current_region}, "
                f"Görevler: {len(self.active_quests)}, "
                f"Sınıf: {self.character_class}, "
                f"Anahtar Kelimeler: {self.detected_keywords}, "
                f"ÖnemliNoktalar: {len(self.nearby_points_of_interest)})")


# BG3 ipuçları veritabanı kategorilere göre düzenlendi
BG3_TIPS = {
    "general": [
        "İpucu: Oyununuzu düzenli olarak kaydetmeyi unutmayın.",
        "İpucu: Tehlikeli karşılaşmalardan kaçınmak için gizlilik kullanarak keşif yapın.",
        "İpucu: Savaşa başlamadan önce taktiksel avantaj için ekibinizi konumlandırın.",
        "İpucu: Gizli hazineler ve gizli yollar için çevrenizi kontrol edin.",
        "İpucu: Savaşta kullanabileceğiniz çevresel tehlikelere dikkat edin.",
        "İpucu: NPC'lerle birden fazla kez konuşun, yeni diyalog seçenekleri olabilir.",
        "İpucu: Daha iyi saldırı zarları için yükseklik avantajı kullanın.",
        "İpucu: Gölgelerdeki karakterler gizlilik kontrollerinde avantaja sahiptir.",
        "İpucu: Büyü slotlarını ve yetenekleri yenilemek için uzun dinlenme yapın.",
        "İpucu: Düşmanları tehlikelere veya uçurumlara itmek için İtme kullanabilirsiniz.",
        "İpucu: Yeni zorluklara uyum sağlamak için uzun dinlenmeden sonra farklı büyüler hazırlayın.",
        "İpucu: İyileştirme iksirlerini tüm parti üyeleri arasında dağıtın.",
        "İpucu: Pasif becerilerin otomatik olarak çalıştığını unutmayın - etkinleştirmenize gerek yok.",
        "İpucu: Hareketli nesneleri sol tıklama tuşunu basılı tutarak alabilirsiniz.",
        "İpucu: Bazı kilitler, maymuncuk başarısız olursa kırılabilir.",
    ],
    "combat": [
        "Savaş İpucu: Saldırılarda avantaj için yüksek zemini kullanın.",
        "Savaş İpucu: Zorlu savaşlarda tomar ve iksir gibi tüketilebilir öğeleri kullanmayı düşünün.",
        "Savaş İpucu: Büyü yapmalarını engellemek için önce düşman büyücüleri hedef alın.",
        "Savaş İpucu: Fırsat saldırılarından kaçınmak için Ayrılma kullanın.",
        "Savaş İpucu: Etkili hasar türleri seçmek için düşman dirençlerini kontrol edin.",
        "Savaş İpucu: Müttefiklerinize avantaj sağlamak için Yardım eylemi kullanın.",
        "Savaş İpucu: Bir düşmanı yandan sıkıştırmak saldırı zarlarında avantaj sağlar.",
        "Savaş İpucu: Yeniden konumlanmak için savaş sırasında zıplayabileceğinizi unutmayın.",
        "Savaş İpucu: Savunma konumlanması için Kaçınma kullanın.",
        "Savaş İpucu: AOE büyüleri birden çok hedefi vurabilir ancak dost ateşine dikkat edin.",
    ],
    "exploration": [
        "Keşif İpucu: Zindanlarda gizli düğmeler ve kollar arayın.",
        "Keşif İpucu: Gizli hazineleri tespit etmek için en yüksek Algılama karakterinizi kullanın.",
        "Keşif İpucu: Hikâye ve eşyalar için kitap raflarını ve kapları kontrol edin.",
        "Keşif İpucu: Tuzakları gizleyebilecek renkli zemin karolarına dikkat edin.",
        "Keşif İpucu: Bazı duvarlar, gizli alanları açığa çıkarmak için yok edilebilir.",
        "Keşif İpucu: Görünüşte erişilemeyen alanlara ulaşmak için Zıplama kullanın.",
        "Keşif İpucu: Anahtarlarla daha sonra dönmek için kilitli kapıların notunu tutun.",
        "Keşif İpucu: Bazı sandıklar tuzaklıdır - kontrol etmek için yüksek Algılama karakteri kullanın.",
        "Keşif İpucu: Güvenle keşfetmek için Arkadaş Bul ile keşif yapın.",
        "Keşif İpucu: Yukarıya bakın - hazineler ve yollar yukarıda olabilir.",
    ],
    "social": [
        "Sosyal İpucu: Karakterinizin geçmişi bazı diyalog seçeneklerini etkiler.",
        "Sosyal İpucu: Yüksek Karizma ikna ve gözdağı vermede yardımcı olur.",
        "Sosyal İpucu: Farklı yoldaşların belirli NPC'lerle özel diyalogları olabilir.",
        "Sosyal İpucu: Belirli eşyalar özel diyalog seçeneklerinin kilidini açabilir.",
        "Sosyal İpucu: Karakter ırkı ve sınıfı NPC'lerin size nasıl yanıt vereceğini etkileyebilir.",
        "Sosyal İpucu: İçgörü, bir NPC'nin dürüst olup olmadığını belirlemeye yardımcı olabilir.",
        "Sosyal İpucu: Bazı diyalog seçimleri, yoldaşlarınızla ilişkinizi kalıcı olarak etkiler.",
        "Sosyal İpucu: Görevlere farklı yaklaşımlar farklı ödüllere yol açabilir.",
        "Sosyal İpucu: Yoldaş diyaloğu sırasında onay/onaylamama göstergelerine dikkat edin.",
        "Sosyal İpucu: Bazı kararlar belirli görev yollarını kalıcı olarak kapatabilir.",
    ],
    "class_specific": {
        "Wizard": [
            "Büyücü İpucu: Büyü kitabınıza eklemek için büyü tomarları arayın.",
            "Büyücü İpucu: Uzun dinlenmeden sonra farklı büyüler hazırlamayı unutmayın.",
            "Büyücü İpucu: Büyü slotlarını korumak için ritüel büyüleri kullanmayı düşünün.",
            "Büyücü İpucu: Yakın dövüşten uzak duracak şekilde konumlanın.",
            "Büyücü İpucu: Tehlikeli alanları keşfetmek için aşina kullanın.",
        ],
        "Fighter": [
            "Savaşçı İpucu: İkinci Nefes, savaşta acil iyileştirme sağlayabilir.",
            "Savaşçı İpucu: Eylem Dalgası size ekstra bir eylem verir - akıllıca kullanın.",
            "Savaşçı İpucu: Savaş alanını kontrol etmek için Nöbetçi yeteneğini düşünün.",
            "Savaşçı İpucu: Daha kırılgan parti üyelerini korumak için kendinizi konumlandırın.",
            "Savaşçı İpucu: Yeterliliğiniz nedeniyle ağır silahları etkili bir şekilde kullanabilirsiniz.",
        ],
        "Cleric": [
            "Rahip İpucu: Uzun dinlenmeden sonra büyülerinizi hazırlamayı unutmayın.",
            "Rahip İpucu: Kanal Tanrısallığınız kısa dinlenme ile yenilenir.",
            "Rahip İpucu: Alan büyüleri her zaman hazırdır ve limitinize karşı sayılmaz.",
            "Rahip İpucu: Saldırı, savunma ve iyileştirme büyülerini dengeleyin.",
            "Rahip İpucu: Ölümsüz Kovma, ölümsüz düşman kalabalıklarını kontrol etmeye yardımcı olabilir.",
        ],
        "Rogue": [
            "Hırsız İpucu: Saldırdıktan sonra ayrılmak için Kurnaz Eylem kullanın.",
            "Hırsız İpucu: Sürpriz saldırı bonusu almak için savaştan önce gizlenin.",
            "Hırsız İpucu: Gizli Saldırı hasarı kazanmak için fırsatlar arayın.",
            "Hırsız İpucu: Tuzakları etkisiz hale getirmede ve kilitleri açmada mükemmelsiniz.",
            "Hırsız İpucu: Temel becerilerde olağanüstü iyi olmak için Uzmanlık kullanın.",
        ],
        "Ranger": [
            "Korucu İpucu: Düşmanları bonuslar için Favori Düşman olarak işaretleyin.",
            "Korucu İpucu: Taktiksel avantajlar için hayvan arkadaşınızı kullanın.",
            "Korucu İpucu: Favori Arazinizde yaratıkları etkili bir şekilde takip edebilirsiniz.",
            "Korucu İpucu: Avcı İşareti hasar çıkışınızı artırır.",
            "Korucu İpucu: Güvende saldırmak için menzilli silahlar kullanmayı düşünün.",
        ],
        "Druid": [
            "Druid İpucu: Vahşi Şekil savaş veya keşif için kullanılabilir.",
            "Druid İpucu: Konsantrasyon büyüleri Vahşi Şekil halindeyken çalışmaya devam eder.",
            "Druid İpucu: Bilgi edinmek için hayvanlarla konuşabilirsiniz.",
            "Druid İpucu: Alan etkili büyüleri kullanırken araziyi dikkate alın.",
            "Druid İpucu: Farklı zorluklar beklendiğinde farklı büyüler hazırlayın.",
        ],
        "Paladin": [
            "Paladin İpucu: Maksimum hasar için kritik vuruşlarda İlahi Darbe kullanın.",
            "Paladin İpucu: Aura'nız yakındaki müttefiklere kurtarma zarlarında bonuslar verir.",
            "Paladin İpucu: El Koyma hastalıkları iyileştirebilir ve aynı zamanda iyileştirebilir.",
            "Paladin İpucu: Ahlaki seçimler yaparken yemininizi göz önünde bulundurun.",
            "Paladin İpucu: Yüksek Karizmanız sosyal etkileşimlerde yardımcı olur.",
        ],
        "Bard": [
            "Ozan İpucu: Bardik İlham, müttefiklerin kritik anlarda başarılı olmasına yardımcı olabilir.",
            "Ozan İpucu: Büyülü Sırlar ile herhangi bir sınıftan büyüler öğrenebilirsiniz.",
            "Ozan İpucu: Bütün Becerilerin Üstadı tüm beceri kontrollerine bonuslar verir.",
            "Ozan İpucu: Yüksek Karizmanız sizi sosyal karşılaşmalarda mükemmel kılar.",
            "Ozan İpucu: Düşman başarılarını önlemek için tepkinizi Keskin Sözler için saklayın.",
        ],
        "Sorcerer": [
            "Büyücü İpucu: Meta Büyü büyülerinizi özelleştirmenize olanak tanır.",
            "Büyücü İpucu: Gerektiğinde büyücülük puanlarını büyü slotlarına dönüştürün.",
            "Büyücü İpucu: Dikkatli Büyü, müttefikleri AOE büyülerden korumaya yardımcı olur.",
            "Büyücü İpucu: İkiz Büyü tek hedefli büyüleri etkili bir şekilde ikiye katlar.",
            "Büyücü İpucu: Karizmanız büyünüzü ve sosyal becerilerinizi güçlendirir.",
        ],
        "Warlock": [
            "Büyücü Paktı İpucu: Büyü slotlarınız kısa dinlenme ile yenilenir.",
            "Büyücü Paktı İpucu: Şeytani Çağrılar seviye atlarken değiştirilebilir.",
            "Büyücü Paktı İpucu: Lanet belirli bir hedefe karşı hasarınızı artırır.",
            "Büyücü Paktı İpucu: Pakt Hediyeniz oyun tarzınızı tanımlar - akıllıca seçin.",
            "Büyücü Paktı İpucu: Şeytani Patlama çağrılarla geliştirilebilir.",
        ],
        "Monk": [
            "Keşiş İpucu: Ki puanlarını akıllıca harcayın - kısa dinlenme ile yenilenirler.",
            "Keşiş İpucu: Sabırlı Savunma size karşı yapılan saldırılara dezavantaj verir.",
            "Keşiş İpucu: Darbe Sağanağı Ki puanları için ekstra saldırılar verir.",
            "Keşiş İpucu: Füzeleri saptırabilir ve potansiyel olarak geri fırlatabilirsiniz.",
            "Keşiş İpucu: Sersemletici Vuruş güçlü düşmanları geçici olarak devre dışı bırakabilir.",
        ],
        "Barbarian": [
            "Barbar İpucu: Öfke hasar direnci ve bonus hasar verir.",
            "Barbar İpucu: Pervasız Saldırı avantaj sağlar ancak sizi savunmasız bırakır.",
            "Barbar İpucu: Tehlike Sezgisi Çeviklik kurtarma zarlarında avantaj sağlar.",
            "Barbar İpucu: Zırhsız savunmanız yüksek Dayanıklılık ile en iyi sonucu verir.",
            "Barbar İpucu: Hızlı Hareket düşmanlara hızla ulaşmanıza yardımcı olur.",
        ]
    },
    "region_specific": {
        "Ravaged Beach": [
            "Bölge İpucu: Kullanışlı eşyalar için gemi enkazını iyice araştırın.",
            "Bölge İpucu: Nautiloid'un keşfedilecek birçok sırrı var.",
            "Bölge İpucu: Bilgi ve ödüller için yaralı hayatta kalanlara yardım edin.",
            "Bölge İpucu: Beyin iribaşlarına dikkat edin - illithid enfeksiyonuna neden olurlar.",
        ],
        "Emerald Grove": [
            "Bölge İpucu: Druidlerin iribaşlar hakkında önemli bilgileri olabilir.",
            "Bölge İpucu: Güçlü bir müttefik kazanmak için Halsin'e yardım edin.",
            "Bölge İpucu: Goblin liderleriyle birden çok şekilde başa çıkılabilir.",
            "Bölge İpucu: Tieflingler'in durumu çözüm için çok yönlü yollar sunar.",
        ],
        "Blighted Village": [
            "Bölge İpucu: Gizli bir mahzen girişi için yel değirmenini kontrol edin.",
            "Bölge İpucu: Gnollar tehlikelidir ancak değerli ganimetlere sahiptir.",
            "Bölge İpucu: Terk edilmiş evlerde gizli hazineler arayın.",
            "Bölge İpucu: Zhentarim'in burada bir varlığı var - etkileşimleri dikkatle seçin.",
        ],
        "Underdark": [
            "Bölge İpucu: Underdark'taki mantarların çeşitli etkileri vardır.",
            "Bölge İpucu: Myconid kolonisi benzersiz görevler ve müttefikler sunar.",
            "Bölge İpucu: Düşmanca olabilecek duergar devriyelerine dikkat edin.",
            "Bölge İpucu: Bazı geçitler gizlidir ve dikkatli arama gerektirir.",
        ],
        "Moonrise Towers": [
            "Bölge İpucu: Mutlak'ın takipçileri burada çok sayıda - dikkatle yaklaşın.",
            "Bölge İpucu: Karmaşık yapıda gizli geçitler arayın.",
            "Bölge İpucu: Buradaki farklı fraksiyonlar birbirine karşı oynatılabilir.",
        ],
        "Baldur's Gate": [
            "Bölge İpucu: Şehirde her biri benzersiz görevlere sahip birçok bölge vardır.",
            "Bölge İpucu: Çeşitli loncalar farklı ödüllerle fraksiyon görevleri sunar.",
            "Bölge İpucu: Sokak çocukları genellikle şehir hakkında değerli bilgilere sahiptir.",
            "Bölge İpucu: Kalabalık alanlarda yankesicilere dikkat edin.",
        ]
    },
    "keyword_triggered": {
        "quest": [
            "Görev İpucu: Detaylı görev hedefleri için günlüğünüzü kontrol edin.",
            "Görev İpucu: Bazı görevlerin zamana duyarlı bileşenleri vardır.",
            "Görev İpucu: Yan görevler değerli ödüller ve deneyim sağlayabilir.",
            "Görev İpucu: Farklı görev çözümleri yoldaşlarınızı farklı şekilde etkileyebilir.",
        ],
        "battle": [
            "Savaş İpucu: Zorlu karşılaşmalardan önce yemek bonuslarını kullanmayı düşünün.",
            "Savaş İpucu: Bazı düşmanların kullanabileceğiniz belirli zayıflıkları vardır.",
            "Savaş İpucu: Çevresel etkiler savaşın gidişatını değiştirebilir.",
            "Savaş İpucu: Menzilli saldırganlarınızı yüksek zeminde konumlandırın.",
        ],
        "trap": [
            "Tuzak İpucu: Yüksek algılamaya sahip karakterler tuzakları daha kolay görebilirler.",
            "Tuzak İpucu: Bazı tuzaklar etkisiz hale getirilebilir, diğerlerinden kaçınılmalıdır.",
            "Tuzak İpucu: Tehlikeli alanlardan şüpheleniyorsanız Tuzakları Bul büyüsünü kullanın.",
            "Tuzak İpucu: Tuzaklardan şüpheleniyorsanız önden harcamaya değer çağrılmış varlıkları gönderin.",
        ],
        "chest": [
            "Sandık İpucu: Bazı kilitli sandıklar maymuncuk açma başarısız olursa kırılabilir.",
            "Sandık İpucu: Değerli görünen sandıkları açmadan önce tuzakları kontrol edin.",
            "Sandık İpucu: Bazı sandıklar başka yerlerde bulunan belirli anahtarlar gerektirir.",
            "Sandık İpucu: Tüm değerli eşyalar belirgin kaplarda değildir.",
        ],
        "spell": [
            "Büyü İpucu: Alan etkili büyüler müttefiklere isabet edebilir - dikkatli konumlanın.",
            "Büyü İpucu: Bazı büyüler çevre ile benzersiz şekillerde etkileşime girer.",
            "Büyü İpucu: Karşı Büyü, düşman büyücülerin güçlü büyüler kullanmasını önleyebilir.",
            "Büyü İpucu: Önemli hasar alırsanız konsantrasyon büyüleri sona erer.",
        ]
    }
}


def generate_recommendations(game_state: GameState) -> list[str]:
    """
    Mevcut oyun durumuna göre öneriler oluşturur.
    Bu, temel 'ajan' mantığıdır.
    """
    logger.debug(f"Şu durum için öneriler oluşturuluyor: {game_state}")
    recommendations = []

    # Zaman kontrolü
    current_time = time.time()
    time_since_last = current_time - game_state.last_tip_time
    logger.debug(f"Son öneri denemesinden bu yana geçen süre: {time_since_last:.2f}sn")

    # 2 dakikalık bekleme süresi geçti mi kontrol et (önceki: 6 dakika/360 saniye)
    if time_since_last >= 120:  # 120 saniye = 2 dakika
        logger.info("Bekleme süresi geçti. Yeni öneriler oluşturmaya çalışılıyor.")
        
        # --- LLM-bazlı öneriler ---
        llm_client = LLMAPIClient()  # LLMAPIClient örneğini başlat
        try:
            if llm_client.is_available():
                logger.info("LLM API'den öneriler isteniyor...")
                llm_recommendations = llm_client.get_recommendation(game_state)
                
                if llm_recommendations:
                    logger.info(f"{len(llm_recommendations)} LLM-üretimi öneri kullanılıyor")
                    recommendations = [f"AI: {rec}" for rec in llm_recommendations]
                    # Öneri üretildi, son öneri zamanını güncelle
                    game_state.last_tip_time = current_time
                else:
                    logger.warning("LLM API hiç öneri döndürmedi")
            else:
                logger.debug("LLM API yapılandırılmamış, hiçbir öneri gösterilmeyecek")
        except ImportError:
            logger.warning("LLM modülü bulunamadı, hiçbir öneri gösterilmeyecek")
        except Exception as e:
            logger.error(f"LLM önerileri alınırken hata: {e}", exc_info=True)
    else:
        logger.debug(f"Bekleme süresi aktif. Öneri oluşturma atlanıyor. Kalan süre: {120 - time_since_last:.2f}sn")
        return [] # Bekleme süresindeyken boş liste döndür

    # Önerileri sınırla
    recommendations = recommendations[:3]
    logger.info(f"Bu döngüde {len(recommendations)} öneri oluşturuldu.")
    return recommendations


if __name__ == '__':  # Örnek kullanım: Bir durum oluştur ve öneriler oluştur
    print("Karar Motoru Test Ediliyor...")
    current_state = GameState()
    # Bazı metin bulma simülasyonu
    test_text = "Entering region: Moonrise Towers\nSome other irrelevant text.\nJournal Updated"
    current_state.update_from_ocr(test_text)
    current_state.character_class = "Cleric" # Sınıf tespiti simülasyonu

    print(f"Mevcut Durum: {current_state}")
    recs = generate_recommendations(current_state)

    print("\nOluşturulan Öneriler:")
    for rec in recs:
        print(f"- {rec}")
