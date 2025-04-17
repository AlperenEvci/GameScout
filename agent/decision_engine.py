# gamescout/agent/decision_engine.py

from config import settings
from utils.helpers import get_logger
import random
import time
from data import map_data  # Yeni map_data modülünü içe aktar
from data.map_data import get_nearby_points_of_interest, get_quests_for_region
from data.web_search import search_game_content, get_region_information
from llm.api_client import LLMAPIClient

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
        
        if "Entering region:" in text:
            try:
                self.current_region = text.split("Entering region:")[1].split("\n")[0].strip()
                logger.info(f"Bölge değişikliği tespit edildi: {self.current_region}")
            except IndexError:
                logger.warning("'Entering region:' sonrasında bölge adı ayrıştırılamadı.")
        
        # Oyunda olabilecek alternatif metni dene
        elif "location:" in text.lower():
            try:
                self.current_region = text.lower().split("location:")[1].split("\n")[0].strip()
                logger.info(f"Konum tespit edildi: {self.current_region}")
            except IndexError:
                logger.warning("Konum adı ayrıştırılamadı.")
        
        # BG3'e özgü bölge tespiti
        bg3_regions = ["Ravaged Beach", "Emerald Grove", "Blighted Village", "Moonrise Towers", 
                       "Underdark", "Grymforge", "Shadowfell", "Gauntlet of Shar", "Githyanki Creche",
                       "Last Light Inn", "Wyrm's Rock", "Shadow-Cursed Lands", "Baldur's Gate"]
        
        for region in bg3_regions:
            if region.lower() in text.lower():
                self.current_region = region
                logger.info(f"BG3 bölgesi tespit edildi: {self.current_region}")
                break
        
        # Konum değiştiyse veya uzun süre geçtiyse harita bilgilerini güncelle
        current_time = time.time()
        if (self.current_region != previous_region or 
            current_time - self.last_location_check_time > 300):  # 5 dakikada bir güncelle
            
            self.update_location_data()
            self.last_location_check_time = current_time
        
        # Metinden ilginç anahtar kelimeleri çıkar
        interesting_keywords = [
            "quest", "mission", "objective", "enemy", "gold", "weapon", "armor", 
            "character", "health", "magic", "skill", "battle", "dialog", "choice",
            "companion", "camp", "rest", "spell", "attack", "defend", "loot", "chest",
            "trap", "lock", "stealth", "hidden", "secret", "map", "journal", "party",
            "inventory", "level up", "ability", "saving throw", "roll", "dice",
            # Türkçe anahtar kelimeler
            "görev", "düşman", "altın", "silah", "zırh", "karakter", "sağlık", "büyü",
            "beceri", "savaş", "diyalog", "seçim", "yoldaş", "kamp", "dinlenme", "büyü",
            "saldırı", "savunma", "ganimet", "sandık", "tuzak", "kilit", "gizlilik",
            "gizli", "sır", "harita", "günlük", "parti", "envanter", "seviye atlama",
            "yetenek", "kurtarma zarı", "zar"
        ]
        
        for keyword in interesting_keywords:
            if keyword in text.lower():
                logger.info(f"OCR metninde '{keyword}' anahtar kelimesi tespit edildi")
                self.detected_keywords.append(keyword)
        
        # Görev tespit mantığı vb. ekle
        if "new quest" in text.lower() or "quest updated" in text.lower() or "journal updated" in text.lower() or "yeni görev" in text.lower() or "görev güncellendi" in text.lower() or "günlük güncellendi" in text.lower():
            logger.info("Görev aktivitesi tespit edildi")
            self.detected_keywords.append("quest_update")
            
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

    # 6 dakikalık bekleme süresi geçti mi kontrol et
    if time_since_last >= 360:
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
        logger.debug(f"Bekleme süresi aktif. Öneri oluşturma atlanıyor. Kalan süre: {360 - time_since_last:.2f}sn")
        return [] # Bekleme süresindeyken boş liste döndür

    # Önerileri sınırla
    recommendations = recommendations[:3]
    logger.info(f"Bu döngüde {len(recommendations)} öneri oluşturuldu.")
    return recommendations


if __name__ == '__main__':
    # Örnek kullanım: Bir durum oluştur ve öneriler oluştur
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
