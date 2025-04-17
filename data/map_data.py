# gamescout/data/map_data.py

import requests
from bs4 import BeautifulSoup
import json
from utils.helpers import get_logger
from config import settings
import os
import time

logger = get_logger(__name__)

# Harita verileri için cache süresi (saniye)
CACHE_DURATION = 3600  # 1 saat

# Cache klasörü
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache")
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# Veri kaynakları
DATA_SOURCES = {
    "web_scraping": {
        "fextralife": "https://baldursgate3.wiki.fextralife.com/Maps",
        "mapgenie_wilderness": "https://mapgenie.io/baldurs-gate-3/maps/wilderness",
        "mapgenie_shadow-cursed-lands": "https://mapgenie.io/baldurs-gate-3/maps/shadow-cursed-lands",
        "mapgenie_baldurs-gate": "https://mapgenie.io/baldurs-gate-3/maps/baldurs-gate",
    },
    "web_search": {
        "enabled": True,
        "search_engine": "duckduckgo",  # veya "google" ya da başka bir arama motoru
        "search_template": "Baldur's Gate 3 {region_name} konum rehberi",
        "max_results": 3
    },
    "llm": {
        "enabled": True,  # LLM entegrasyonunu kullanıp kullanmamak
        "prompt_template": "Baldur's Gate 3 oyununda {region_name} bölgesi hakkında bilgi ver. Bu bölgedeki önemli noktalar, görevler ve karakterler nelerdir?"
    }
}

# Oyun bölgeleri ve koordinat bilgileri
GAME_REGIONS = {
    "Ravaged Beach": {
        "points_of_interest": [
            {"name": "Nautiloid Çarpma Bölgesi", "description": "Zihin Yüzücüsü gemisi buraya düştü. Hayatta kalanları ve kullanışlı eşyaları arayın."},
            {"name": "Sahil Mağarası", "description": "Bazı temel malzemeler ve ilk yoldaş fırsatı bulunan küçük bir mağara."},
            {"name": "ABD Çarpma Bölgesi", "description": "Tehlikeler ve ganimetlerle dolu başka bir düşmüş gemi bölümü."}
        ],
        "map_coordinates": {"x": 120, "y": 85}
    },
    "Emerald Grove": {
        "points_of_interest": [
            {"name": "Druid Çemberi", "description": "Druidlerin ritüellerini gerçekleştirdiği korunun merkezi. Burada Rath ile konuşun."},
            {"name": "Tiefling Kampı", "description": "Elturel'den mülteciler. Zevlor onlara liderlik eder ve çeşitli görevleri vardır."},
            {"name": "Gizli Giriş", "description": "Bir şelalenin arkasında Underdark'a giden gizli giriş."},
            {"name": "İç Mabet", "description": "Halsin geri döndüğünde bulunabileceği yer. Korunun eserlerini barındırır."}
        ],
        "map_coordinates": {"x": 230, "y": 175} 
    },
    "Blighted Village": {
        "points_of_interest": [
            {"name": "Yel Değirmeni", "description": "Değerli eşyalar ve gizemli bir kitap için mahzeni kontrol edin."},
            {"name": "Eczane", "description": "İksirler ve tomarlar için malzemeler içerir. Tuzaklara dikkat edin."},
            {"name": "Rün Taşı", "description": "Güçlü büyülü taş. Birden çok şekilde kullanılabilir."},
            {"name": "Yıkılmış Evler", "description": "Yok edilebilir nesnelerde birçok gizli eşya."}
        ],
        "map_coordinates": {"x": 320, "y": 150}
    },
    "Underdark": {
        "points_of_interest": [
            {"name": "Myconid Kolonisi", "description": "Müttefik olabilecek barışçıl mantar insanlar. Hükümdar Spaw ile konuşun."},
            {"name": "Selûnite Karakolu", "description": "Tanrıça Selûne'nin takipçileri. Önemli görev eşyaları içerir."},
            {"name": "Bulette Mağarası", "description": "Tehlikeli bir bulette'nin evi. İçinde yüksek seviyeli ganimetler var."},
            {"name": "Grymforge Girişi", "description": "Grymforge'a giden yol. Duergar tarafından korunur."}
        ],
        "map_coordinates": {"x": 280, "y": 320}
    },
    "Moonrise Towers": {
        "points_of_interest": [
            {"name": "Ana Kapı", "description": "Ağır korunan giriş. Alternatif girişler mevcut."},
            {"name": "Zindan Hücreleri", "description": "Dikkat çekici mahkumlar ve ana olay örgüsü hakkında önemli bilgiler içerir."},
            {"name": "Merkez Oda", "description": "Ritüelin gerçekleştiği yer. Kritik hikaye konumu."},
            {"name": "Gizli Kütüphane", "description": "Değerli hikaye kitapları ve büyülü eşyalar bulunan gizli alan."}
        ],
        "map_coordinates": {"x": 420, "y": 260}
    },
    "Shadowfell": {
        "points_of_interest": [
            {"name": "Shar'ın Tapınağı", "description": "Karanlık tanrıçasına tapınma merkezi. Tehlikeli ama değerli ganimetler."},
            {"name": "Terk Edilmiş Kamp", "description": "Bölge hakkında ipuçları bulunan eski kaşif kampı."},
            {"name": "Gölge Portalı", "description": "Diğer alanlara hızlıca erişmek için kullanılabilir."}
        ],
        "map_coordinates": {"x": 380, "y": 340}
    },
    "Grymforge": {
        "points_of_interest": [
            {"name": "Grym Demirhanesi", "description": "Benzersiz zanaat olanaklarına sahip antik demirci ocağı."},
            {"name": "Duergar Karakolu", "description": "Olası müttefikler veya düşmanlarla duergar yerleşimi."},
            {"name": "Derin Havuz", "description": "Gizli bir geçit ve değerli kaynaklar içerir."}
        ],
        "map_coordinates": {"x": 340, "y": 380}
    },
    "Last Light Inn": {
        "points_of_interest": [
            {"name": "Ana Salon", "description": "Gölge-lanetli topraklarda güvenli sığınak. Burada önemli NPC'ler toplanır."},
            {"name": "Isobel'in Odası", "description": "Isobel'i bulabileceğiniz ve hana bağlantısı hakkında bilgi edinebileceğiniz yer."},
            {"name": "Gizli Mahzen", "description": "Özel eşyalar ve bilgiler içeren gizli alan."}
        ],
        "map_coordinates": {"x": 460, "y": 280}
    },
    "Baldur's Gate": {
        "points_of_interest": [
            {"name": "Aşağı Şehir", "description": "Birçok sır ve yan görev içeren fakir bölge."},
            {"name": "Yukarı Şehir", "description": "Önemli politik NPC'lerle zengin bölge."},
            {"name": "Rivington", "description": "Benzersiz dükkanlar ve görevlere sahip su kıyısı bölgesi."},
            {"name": "Wyrm's Rock", "description": "Şimdi tarikatçıların ele geçirdiği eski hapishane."},
            {"name": "Philgrave Malikanesi", "description": "Değerli bilgilere sahip önemli bir olay örgüsü karakterinin evi."}
        ],
        "map_coordinates": {"x": 520, "y": 320}
    }
}

def get_cached_filename(region_name):
    """Bölge adına göre cache dosya adını oluşturur."""
    safe_name = region_name.lower().replace(" ", "_").replace("'", "")
    return os.path.join(CACHE_DIR, f"{safe_name}_map_data.json")

def is_cache_valid(cache_file):
    """Cache dosyasının geçerli olup olmadığını kontrol eder."""
    if not os.path.exists(cache_file):
        return False
    
    file_age = time.time() - os.path.getmtime(cache_file)
    return file_age < CACHE_DURATION

def save_to_cache(region_name, data):
    """Veriyi cache'e kaydeder."""
    cache_file = get_cached_filename(region_name)
    try:
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        logger.debug(f"Harita verisi şu bölge için önbelleğe alındı: {region_name}")
        return True
    except Exception as e:
        logger.error(f"Harita verisi önbelleğe alınırken hata: {e}")
        return False

def load_from_cache(region_name):
    """Cache'ten veri yükler."""
    cache_file = get_cached_filename(region_name)
    if is_cache_valid(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.debug(f"Şu bölge için önbellekten harita verisi yüklendi: {region_name}")
            return data
        except Exception as e:
            logger.error(f"Önbellekli harita verisi yüklenirken hata: {e}")
    return None

def fetch_fextralife_map_data(region_name):
    """Fextralife wikisinden harita verilerini çeker (doğrudan sayfa URL'si ile)."""
    if not region_name:
        return None
    
    # Önce cache'i kontrol et
    cached_data = load_from_cache(region_name)
    if cached_data:
        return cached_data
    
    # Doğrudan bölge sayfası URL'sini oluştur
    # Boşlukları '+' ile, kesme işaretini '%27' ile değiştir
    safe_region_for_url = region_name.replace(" ", "+").replace("'", "%27")
    region_url = f"https://baldursgate3.wiki.fextralife.com/{safe_region_for_url}"
    logger.info(f"Fextralife URL'sinden doğrudan çekme girişimi: {region_url}")
    
    try:
        headers = {'User-Agent': settings.SCRAPER_USER_AGENT}
        response = requests.get(region_url, headers=headers, timeout=10)
        
        # Sayfa bulunamazsa (404), hata logla ve yerel veriyi dene
        if response.status_code == 404:
            logger.warning(f"Doğrudan Fextralife sayfası bulunamadı: {region_url}. Yerel veriye dönülüyor.")
            if region_name in GAME_REGIONS:
                return GAME_REGIONS[region_name]
            else:
                return None
        
        response.raise_for_status() # Diğer HTTP hatalarını kontrol et
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # --- Bölge bilgilerini çıkarma mantığı (öncekiyle aynı) ---
        region_data = {
            "name": region_name,
            "description": "",
            "points_of_interest": [],
            "quests": [],
            "npcs": [],
            "enemies": [],
            "loot": []
        }
        
        # Ana açıklama
        description_elem = soup.select_one('div.wiki-content p')
        if description_elem:
            region_data["description"] = description_elem.text.strip()
        
        # Önemli noktalar
        poi_section = None
        headings = soup.select('h2, h3, h4')
        for heading in headings:
            if 'location' in heading.text.lower() or 'area' in heading.text.lower() or 'point' in heading.text.lower():
                poi_section = heading
                break
        
        if poi_section:
            next_elem = poi_section.find_next_sibling()
            while next_elem and next_elem.name not in ['h2', 'h3', 'h4']:
                if next_elem.name == 'ul':
                    for li in next_elem.select('li'):
                        poi = {"name": li.text.strip(), "description": ""}
                        region_data["points_of_interest"].append(poi)
                next_elem = next_elem.find_next_sibling()
        
        # Görevler
        quest_section = None
        for heading in headings:
            if 'quest' in heading.text.lower() or 'mission' in heading.text.lower():
                quest_section = heading
                break
        
        if quest_section:
            next_elem = quest_section.find_next_sibling()
            while next_elem and next_elem.name not in ['h2', 'h3', 'h4']:
                if next_elem.name == 'ul':
                    for li in next_elem.select('li'):
                        quest = {"name": li.text.strip(), "description": ""}
                        region_data["quests"].append(quest)
                next_elem = next_elem.find_next_sibling()
        
        # NPC'ler
        npc_section = None
        for heading in headings:
            if 'npc' in heading.text.lower() or 'character' in heading.text.lower():
                npc_section = heading
                break
        
        if npc_section:
            next_elem = npc_section.find_next_sibling()
            while next_elem and next_elem.name not in ['h2', 'h3', 'h4']:
                if next_elem.name == 'ul':
                    for li in next_elem.select('li'):
                        npc = {"name": li.text.strip(), "description": ""}
                        region_data["npcs"].append(npc)
                next_elem = next_elem.find_next_sibling()
        
        # Yerel veri ile birleştir
        if region_name in GAME_REGIONS:
            local_data = GAME_REGIONS[region_name]
            
            # Hâlihazırda bildiğimiz POI'leri ekle
            existing_poi_names = [poi["name"] for poi in region_data["points_of_interest"]]
            for local_poi in local_data.get("points_of_interest", []):
                if local_poi["name"] not in existing_poi_names:
                    region_data["points_of_interest"].append(local_poi)
            
            # Harita koordinatlarını ekle
            region_data["map_coordinates"] = local_data.get("map_coordinates")
        
        # Cache'e kaydet
        save_to_cache(region_name, region_data)
        
        logger.info(f"Şu bölge için doğrudan URL'den harita verisi başarıyla çekildi: {region_name}")
        return region_data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Doğrudan Fextralife URL'si çekilirken hata {region_url}: {e}")
        # Hata durumunda yerel veriyi kullan
        if region_name in GAME_REGIONS:
            logger.info(f"Çekme hatası nedeniyle bölge için yerel veri kullanılıyor: {region_name}")
            return GAME_REGIONS[region_name]
        return None
    except Exception as e:
        logger.error(f"Şu bölge için Fextralife verisi işlenirken hata: {region_name}: {e}")
        # Genel hata durumunda yerel veriyi kullan
        if region_name in GAME_REGIONS:
            logger.info(f"İşleme hatası nedeniyle bölge için yerel veri kullanılıyor: {region_name}")
            return GAME_REGIONS[region_name]
        return None

def get_nearby_points_of_interest(region_name):
    """Bölgedeki önemli noktaları döndürür."""
    region_data = fetch_fextralife_map_data(region_name)
    if region_data:
        return region_data.get("points_of_interest", [])
    
    # Veri çekilemezse yerel verilere başvur
    if region_name in GAME_REGIONS:
        return GAME_REGIONS[region_name].get("points_of_interest", [])
    
    return []

def get_quests_for_region(region_name):
    """Bölgedeki görevleri döndürür."""
    region_data = fetch_fextralife_map_data(region_name)
    if region_data and "quests" in region_data:
        return region_data["quests"]
    return []

def get_npcs_in_region(region_name):
    """Bölgedeki NPC'leri döndürür."""
    region_data = fetch_fextralife_map_data(region_name)
    if region_data and "npcs" in region_data:
        return region_data["npcs"]
    return []

def get_region_description(region_name):
    """Bölge açıklamasını döndürür."""
    region_data = fetch_fextralife_map_data(region_name)
    if region_data and "description" in region_data:
        return region_data["description"]
    return ""

if __name__ == "__main__":
    # Test: Bir bölge için veri çek
    test_region = "Emerald Grove"
    print(f"{test_region} için harita verisi çekme testi yapılıyor...")
    map_data = fetch_fextralife_map_data(test_region)
    
    if map_data:
        print(f"\nBölge: {map_data['name']}")
        if "description" in map_data and map_data["description"]:
            print(f"\nAçıklama: {map_data['description']}")
        
        if "points_of_interest" in map_data and map_data["points_of_interest"]:
            print("\nÖnemli Noktalar:")
            for poi in map_data["points_of_interest"]:
                print(f"- {poi['name']}: {poi['description']}")
        
        if "quests" in map_data and map_data["quests"]:
            print("\nGörevler:")
            for quest in map_data["quests"]:
                print(f"- {quest['name']}")
        
        if "npcs" in map_data and map_data["npcs"]:
            print("\nNPC'ler:")
            for npc in map_data["npcs"]:
                print(f"- {npc['name']}")
    else:
        print(f"Şu bölge için veri bulunamadı: {test_region}")