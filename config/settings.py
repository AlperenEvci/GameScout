# gamescout/config/settings.py

import os
import shutil
import sys

# Add project root to path to enable importing from src
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


from dotenv import load_dotenv

# .env dosyasından değerleri yükle (eğer varsa)
# .env dosyası yoksa, bu işlem sessizce başarısız olur ve ortam değişkenlerini kullanmaya devam eder
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
load_dotenv(dotenv_path)

# --- General Settings ---
APP_NAME = "GameScout"
VERSION = "0.1.0"

# --- Screen Capture & OCR ---
SCREENSHOT_INTERVAL_SECONDS = 15  # How often to capture the screen

# Set the path to Tesseract - automatically tries to find it if possible
def find_tesseract_path():
    # Default paths to check
    default_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        # Add custom paths here if needed
    ]
    
    # First check the default installation paths
    for path in default_paths:
        if os.path.isfile(path):
            return path
    
    # Then try to find it in PATH
    tesseract_path = shutil.which('tesseract')
    if tesseract_path:
        return tesseract_path
        
    return None

TESSERACT_CMD = find_tesseract_path()
OCR_LANGUAGE = 'tur'  # Set to 'tur' for Turkish language support
# Optional: Define specific screen region for capture (left, top, width, height)
CAPTURE_REGION = None # Set to None to capture the primary monitor

# Set this to the title of the window you want to capture
# If set, GameScout will try to capture this window instead of using CAPTURE_REGION
CAPTURE_WINDOW_TITLE = "Baldur's Gate 3 (1920x1080) - (Vulkan) - (6 + 6 WT)"  # Exact window title for capture

# --- Data Scraping ---
# Target forum URLs (add more as needed)
FORUM_URLS = {

    "fextralife_bg3": "https://baldursgate3.wiki.fextralife.com/Baldur's+Gate+3+Wiki",
    # Add more specific pages if needed
}
SCRAPER_USER_AGENT = f"{APP_NAME}/{VERSION} (GameScout Application)" # Be polite to websites

# --- Agent Settings ---
# Placeholder for character class or other agent logic triggers
DEFAULT_CHARACTER_CLASS = "Fighter"

# --- LLM API Settings ---
# Set to "none" to disable, or choose "openai", "gemini", "deepseek", "openrouter" or "azure"
LLM_PROVIDER = "openrouter"  # Set to "openrouter" for accessing DeepSeek

# LLM API değişkenleri
# api_client.py tarafından kullanılan değişken adları
LLM_API_TYPE = LLM_PROVIDER  # LLM_PROVIDER'ı LLM_API_TYPE olarak kullan
LLM_API_KEY = os.environ.get("OPENROUTER_API_KEY", "")
LLM_API_MODEL = LLM_MODEL = "deepseek/deepseek-r1:free"  # DeepSeek model via OpenRouter
LLM_API_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

# Temperature (randomness) - lower for more consistent responses
LLM_TEMPERATURE = 0.7
# Maximum tokens in response
LLM_MAX_TOKENS = 300
# System prompt to set context for LLM
LLM_SYSTEM_PROMPT = """Sen Baldur's Gate 3 oyunu için bir akıllı asistansın. 
Oyuncuya yararlı bilgiler, taktikler ve ipuçları ver. Özellikle oyuncunun karakterinin sınıfına 
ve bulunduğu bölgeye göre kişiselleştirilmiş öneriler yap. 
Kısa ve öz cümleler kullan. Önerileri maddeler halinde ver."""

# Prompt template for generating recommendations
LLM_PROMPT_TEMPLATE = """Şu an Baldur's Gate 3 oyunundayım.
Bölge: {region}
Karakter Sınıfı: {character_class}
Tespit Edilen Anahtar Kelimeler: {keywords}

Yakındaki Önemli Noktalar:
{points_of_interest}

Bölge Görevleri:
{quests}

Bu bilgileri kullanarak bana oyundaki mevcut durumuma göre 3-5 kısa, pratik öneri/tavsiye ver. 
Bulunduğum bölgedeki değerli eşyaları, taktikleri, görevleri veya karakter sınıfıma özgü ipuçlarını içersin. 
Tavsiyeler kısa ve direkt olsun."""

# LangChain Web Search Settings
ENABLE_WEB_SEARCH = True  # Set to False to disable web search
WEB_SEARCH_MAX_RESULTS = 3  # Maximum number of search results to retrieve
WEB_SEARCH_TIMEOUT = 10  # Timeout in seconds for web search requests

# --- UI Settings ---
HUD_UPDATE_INTERVAL_MS = 2500  # 1 saniyeden 2.5 saniyeye çıkarıldı - HUD yenileme sıklığı
HUD_WIDTH = 400  # Daha iyi görünürlük için 300'den artırıldı
HUD_HEIGHT = 350  # Daha fazla içerik gösterebilmek için 300'den 350'ye çıkarıldı
HUD_TRANSPARENCY = 0.85  # Daha iyi görünürlük için 0.9'dan 0.85'e değiştirildi (daha az şeffaf)

# --- Logging ---
LOG_FILE = "gamescout.log"
LOG_LEVEL = "INFO" # DEBUG, INFO, WARNING, ERROR, CRITICAL

# --- Game Regions ---
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
            {"name": "Limanlar", "description": "Suç ve kaçakçılık faaliyetleriyle dolu kıyı bölgesi."},
            {"name": "Saray", "description": "Politik entrikalar ve önemli kararların alındığı şehir merkezi."}
        ],
        "map_coordinates": {"x": 520, "y": 380}
    }
}

# --- Utility Functions ---
def get_tesseract_path():
    """Returns the configured Tesseract path or None."""
    return TESSERACT_CMD

# Add more configuration loading logic if needed (e.g., from environment variables or files)