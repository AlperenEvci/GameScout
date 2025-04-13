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
        "search_template": "Baldur's Gate 3 {region_name} location guide",
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
            {"name": "Nautiloid Crash Site", "description": "The Mind Flayer ship crashed here. Search for survivors and useful items."},
            {"name": "Beach Cave", "description": "A small cave with some basic supplies and your first companion opportunity."},
            {"name": "US Crash Site", "description": "Another crashed ship section with dangers and loot."}
        ],
        "map_coordinates": {"x": 120, "y": 85}
    },
    "Emerald Grove": {
        "points_of_interest": [
            {"name": "Druid Circle", "description": "Center of the grove where the druids perform their rituals. Speak with Rath here."},
            {"name": "Tiefling Camp", "description": "Refugees from Elturel. Zevlor leads them and has several quests."},
            {"name": "Hidden Entrance", "description": "Secret entrance to the Underdark behind a waterfall."},
            {"name": "Inner Sanctum", "description": "Where Halsin can be found when he returns. Houses the grove's artifacts."}
        ],
        "map_coordinates": {"x": 230, "y": 175} 
    },
    "Blighted Village": {
        "points_of_interest": [
            {"name": "Windmill", "description": "Check the cellar for valuable items and a mysterious book."},
            {"name": "Apothecary", "description": "Contains materials for potions and scrolls. Watch for traps."},
            {"name": "Runestone", "description": "Powerful magic stone. Possible to use in multiple ways."},
            {"name": "Destroyed Houses", "description": "Many hidden items in destructible objects."}
        ],
        "map_coordinates": {"x": 320, "y": 150}
    },
    "Underdark": {
        "points_of_interest": [
            {"name": "Myconid Colony", "description": "Peaceful mushroom people who can become allies. Speak with Sovereign Spaw."},
            {"name": "Selûnite Outpost", "description": "Followers of the goddess Selûne. Contains important quest items."},
            {"name": "Bulette Cave", "description": "Home to a dangerous bulette. High level loot inside."},
            {"name": "Grymforge Entrance", "description": "Path leading to the Grymforge. Guarded by duergar."}
        ],
        "map_coordinates": {"x": 280, "y": 320}
    },
    "Moonrise Towers": {
        "points_of_interest": [
            {"name": "Main Gate", "description": "Heavily guarded entrance. Alternative entrances available."},
            {"name": "Prison Cells", "description": "Contains notable prisoners and important information about the main plot."},
            {"name": "Central Chamber", "description": "Where the ritual takes place. Critical story location."},
            {"name": "Secret Library", "description": "Hidden area with valuable lore books and magic items."}
        ],
        "map_coordinates": {"x": 420, "y": 260}
    },
    "Shadowfell": {
        "points_of_interest": [
            {"name": "Shar's Temple", "description": "Center of worship for the goddess of darkness. Dangerous but valuable loot."},
            {"name": "Abandoned Camp", "description": "Former explorer camp with clues about the region."},
            {"name": "Shadow Portal", "description": "Can be used to access other areas quickly."}
        ],
        "map_coordinates": {"x": 380, "y": 340}
    },
    "Grymforge": {
        "points_of_interest": [
            {"name": "Forge of Grym", "description": "Ancient forge with unique crafting possibilities."},
            {"name": "Duergar Outpost", "description": "Duergar settlement with possible allies or enemies."},
            {"name": "Deep Pool", "description": "Contains a hidden passage and valuable resources."}
        ],
        "map_coordinates": {"x": 340, "y": 380}
    },
    "Last Light Inn": {
        "points_of_interest": [
            {"name": "Main Hall", "description": "Safe haven in the shadow-cursed lands. Important NPCs gather here."},
            {"name": "Isobel's Room", "description": "Where you can find Isobel and learn about her connection to the inn."},
            {"name": "Hidden Cellar", "description": "Secret area with special items and information."}
        ],
        "map_coordinates": {"x": 460, "y": 280}
    },
    "Baldur's Gate": {
        "points_of_interest": [
            {"name": "Lower City", "description": "Poorer district with many secrets and sidequests."},
            {"name": "Upper City", "description": "Wealthy district with important political NPCs."},
            {"name": "Rivington", "description": "Waterfront district with unique shops and quests."},
            {"name": "Wyrm's Rock", "description": "Former prison now taken over by cultists."},
            {"name": "Philgrave Mansion", "description": "Home to an important plot character with valuable information."}
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
        logger.debug(f"Map data cached for region: {region_name}")
        return True
    except Exception as e:
        logger.error(f"Error caching map data: {e}")
        return False

def load_from_cache(region_name):
    """Cache'ten veri yükler."""
    cache_file = get_cached_filename(region_name)
    if is_cache_valid(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.debug(f"Loaded map data from cache for region: {region_name}")
            return data
        except Exception as e:
            logger.error(f"Error loading cached map data: {e}")
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
    logger.info(f"Attempting to fetch directly from Fextralife URL: {region_url}")
    
    try:
        headers = {'User-Agent': settings.SCRAPER_USER_AGENT}
        response = requests.get(region_url, headers=headers, timeout=10)
        
        # Sayfa bulunamazsa (404), hata logla ve yerel veriyi dene
        if response.status_code == 404:
            logger.warning(f"Direct Fextralife page not found: {region_url}. Falling back to local data.")
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
        
        logger.info(f"Successfully fetched map data for region: {region_name} from direct URL")
        return region_data
        
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching direct Fextralife URL {region_url}: {e}")
        # Hata durumunda yerel veriyi kullan
        if region_name in GAME_REGIONS:
            logger.info(f"Using local data for region due to fetch error: {region_name}")
            return GAME_REGIONS[region_name]
        return None
    except Exception as e:
        logger.error(f"Error processing Fextralife data for {region_name}: {e}")
        # Genel hata durumunda yerel veriyi kullan
        if region_name in GAME_REGIONS:
            logger.info(f"Using local data for region due to processing error: {region_name}")
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
    print(f"Testing map data retrieval for {test_region}...")
    map_data = fetch_fextralife_map_data(test_region)
    
    if map_data:
        print(f"\nRegion: {map_data['name']}")
        if "description" in map_data and map_data["description"]:
            print(f"\nDescription: {map_data['description']}")
        
        if "points_of_interest" in map_data and map_data["points_of_interest"]:
            print("\nPoints of Interest:")
            for poi in map_data["points_of_interest"]:
                print(f"- {poi['name']}: {poi['description']}")
        
        if "quests" in map_data and map_data["quests"]:
            print("\nQuests:")
            for quest in map_data["quests"]:
                print(f"- {quest['name']}")
        
        if "npcs" in map_data and map_data["npcs"]:
            print("\nNPCs:")
            for npc in map_data["npcs"]:
                print(f"- {npc['name']}")
    else:
        print(f"No data found for region: {test_region}")