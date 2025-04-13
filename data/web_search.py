# gamescout/data/web_search.py

import requests
import json
import os
import time
from urllib.parse import quote_plus
from config import settings
from utils.helpers import get_logger

logger = get_logger(__name__)

# Web aramaları için cache süresi (saniye)
CACHE_DURATION = 86400  # 24 saat

# Cache klasörü
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cache")
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

class WebSearchClient:
    """Farklı arama motorları üzerinden web araması yapmak için sınıf"""
    
    def __init__(self, search_engine="duckduckgo"):
        """
        WebSearch istemcisini başlat
        
        Args:
            search_engine: Kullanılacak arama motoru ('duckduckgo', 'google', vb.)
        """
        self.search_engine = search_engine.lower()
        self.user_agent = settings.SCRAPER_USER_AGENT
    
    def search(self, query, max_results=3, region=None):
        """
        Web araması yap ve sonuçları döndür
        
        Args:
            query: Arama sorgusu
            max_results: Maksimum sonuç sayısı
            region: Arama yapılacak bölge (ülke kodu)
            
        Returns:
            Arama sonuçlarını içeren liste
        """
        # Cache kontrolü
        cache_file = self._get_cache_filename(query)
        if self._is_cache_valid(cache_file):
            cached_results = self._load_from_cache(cache_file)
            if cached_results:
                logger.info(f"Loading search results from cache: '{query}'")
                return cached_results[:max_results]
        
        # Seçilen arama motoruna göre arama yap
        if self.search_engine == "duckduckgo":
            results = self._search_duckduckgo(query, max_results)
        elif self.search_engine == "google":
            results = self._search_google(query, max_results, region)
        else:
            logger.error(f"Unsupported search engine: {self.search_engine}")
            return []
        
        # Sonuçları cache'e kaydet
        if results:
            self._save_to_cache(cache_file, results)
        
        return results
    
    def _search_duckduckgo(self, query, max_results):
        """DuckDuckGo üzerinden arama yap (API)"""
        try:
            # DuckDuckGo API endpoint'i
            url = f"https://api.duckduckgo.com/?q={quote_plus(query)}&format=json"
            
            headers = {'User-Agent': self.user_agent}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            results = []
            
            # Related Topics'ten sonuçları çıkar
            if "RelatedTopics" in data:
                for topic in data["RelatedTopics"][:max_results]:
                    if "Text" in topic and "FirstURL" in topic:
                        results.append({
                            "title": topic["Text"].split(" - ")[0] if " - " in topic["Text"] else topic["Text"],
                            "description": topic["Text"],
                            "url": topic["FirstURL"]
                        })
            
            # Yeterli sonuç yoksa normal DuckDuckGo HTML araması da yap
            if len(results) < max_results:
                html_results = self._search_duckduckgo_html(query, max_results - len(results))
                results.extend(html_results)
            
            return results[:max_results]
            
        except Exception as e:
            logger.error(f"Error searching DuckDuckGo API: {e}")
            # API başarısız olursa HTML aramayı dene
            return self._search_duckduckgo_html(query, max_results)
    
    def _search_duckduckgo_html(self, query, max_results):
        """DuckDuckGo üzerinden HTML tabanlı arama (scraping)"""
        try:
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            
            headers = {
                'User-Agent': self.user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            for result in soup.select('.result')[:max_results]:
                title_elem = result.select_one('.result__title')
                url_elem = result.select_one('.result__url')
                snippet_elem = result.select_one('.result__snippet')
                
                if title_elem and url_elem:
                    title = title_elem.get_text(strip=True)
                    url = url_elem.get('href') if url_elem.get('href') else title_elem.find('a').get('href')
                    description = snippet_elem.get_text(strip=True) if snippet_elem else ""
                    
                    results.append({
                        "title": title,
                        "description": description,
                        "url": url
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching DuckDuckGo HTML: {e}")
            return []
    
    def _search_google(self, query, max_results, region=None):
        """Google üzerinden arama yap (scraping)"""
        try:
            # Google arama URL'i
            url = f"https://www.google.com/search?q={quote_plus(query)}&num={max_results}"
            if region:
                url += f"&gl={region}"
            
            headers = {
                'User-Agent': self.user_agent,
                'Accept': 'text/html,application/xhtml+xml,application/xml'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            results = []
            
            # Google arama sonuçlarını çıkar
            for result in soup.select('.g')[:max_results]:
                title_elem = result.select_one('h3')
                url_elem = result.select_one('a')
                snippet_elem = result.select_one('.VwiC3b') or result.select_one('.st')
                
                if title_elem and url_elem:
                    title = title_elem.get_text(strip=True)
                    url = url_elem.get('href')
                    if url and url.startswith('/url?q='):
                        url = url.split('/url?q=')[1].split('&')[0]
                    description = snippet_elem.get_text(strip=True) if snippet_elem else ""
                    
                    results.append({
                        "title": title,
                        "description": description,
                        "url": url
                    })
            
            return results
            
        except Exception as e:
            logger.error(f"Error searching Google: {e}")
            return []
    
    def _get_cache_filename(self, query):
        """Sorgu için cache dosya adını oluştur"""
        safe_query = query.lower().replace(" ", "_").replace("'", "").replace("?", "").replace(",", "")
        safe_query = ''.join(c for c in safe_query if c.isalnum() or c == '_')
        if len(safe_query) > 50:
            safe_query = safe_query[:50]  # Dosya adını sınırla
        return os.path.join(CACHE_DIR, f"search_{self.search_engine}_{safe_query}.json")
    
    def _is_cache_valid(self, cache_file):
        """Cache dosyasının geçerli olup olmadığını kontrol et"""
        if not os.path.exists(cache_file):
            return False
        
        file_age = time.time() - os.path.getmtime(cache_file)
        return file_age < CACHE_DURATION
    
    def _save_to_cache(self, cache_file, data):
        """Veriyi cache'e kaydet"""
        try:
            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            logger.debug(f"Search results cached to {cache_file}")
            return True
        except Exception as e:
            logger.error(f"Error caching search results: {e}")
            return False
    
    def _load_from_cache(self, cache_file):
        """Cache'ten veri yükle"""
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            logger.debug(f"Loaded search results from cache: {cache_file}")
            return data
        except Exception as e:
            logger.error(f"Error loading cached search results: {e}")
            return None

def search_game_content(query, region_name=None, search_engine="duckduckgo", max_results=3):
    """
    Oyun içeriği için web araması yapar
    
    Args:
        query: Temel arama sorgusu
        region_name: Aranacak oyun bölgesi (None ise genel arama yapılır)
        search_engine: Kullanılacak arama motoru
        max_results: Maksimum sonuç sayısı
        
    Returns:
        Arama sonuçlarını içeren liste
    """
    search_client = WebSearchClient(search_engine)
    
    if region_name:
        full_query = f"Baldur's Gate 3 {region_name} {query}"
    else:
        full_query = f"Baldur's Gate 3 {query}"
    
    logger.info(f"Searching for: '{full_query}'")
    return search_client.search(full_query, max_results)

def get_region_information(region_name, search_engine="duckduckgo"):
    """
    Belirli bir oyun bölgesi hakkında bilgi arar
    
    Args:
        region_name: Aranan bölge adı
        search_engine: Kullanılacak arama motoru
        
    Returns:
        Bölge bilgilerini içeren sözlük
    """
    results = search_game_content("location guide walkthrough", region_name, search_engine, max_results=5)
    
    # Sonuçları bölge bilgileri formatında yapılandır
    region_info = {
        "name": region_name,
        "description": "",
        "points_of_interest": [],
        "quests": [],
        "urls": []  # Daha fazla bilgi için URL'ler
    }
    
    # İlk sonucun açıklamasını bölge açıklaması olarak kullan
    if results and results[0]["description"]:
        region_info["description"] = results[0]["description"]
    
    # Aramalarda geçen önemli noktaları topla
    poi_keywords = ["landmark", "location", "point of interest", "place", "area", "building"]
    quest_keywords = ["quest", "mission", "task", "objective"]
    
    for result in results:
        # Sonuç URL'lerini kaydet
        region_info["urls"].append({
            "title": result["title"],
            "url": result["url"]
        })
        
        # İçeriği analiz et
        description = result["description"].lower()
        title = result["title"].lower()
        
        # Önemli nokta olabilecek içeriği ara
        for keyword in poi_keywords:
            if keyword in description or keyword in title:
                # Basit bir NLP yaklaşımı - daha gelişmiş yöntemler kullanılabilir
                sentences = description.split(". ")
                for sentence in sentences:
                    if keyword in sentence and len(sentence) > 20:
                        # Önemli nokta olarak eklenmemiş mi kontrol et
                        is_new = True
                        for poi in region_info["points_of_interest"]:
                            if sentence[:20] in poi["description"]:
                                is_new = False
                                break
                        
                        if is_new:
                            name = sentence.split(" " + keyword)[0].strip()
                            if len(name) > 30:
                                name = name[:30] + "..."
                            
                            region_info["points_of_interest"].append({
                                "name": name.capitalize(),
                                "description": sentence.strip().capitalize()
                            })
        
        # Görev olabilecek içeriği ara
        for keyword in quest_keywords:
            if keyword in description or keyword in title:
                sentences = description.split(". ")
                for sentence in sentences:
                    if keyword in sentence and len(sentence) > 15:
                        # Görev olarak eklenmemiş mi kontrol et
                        is_new = True
                        for quest in region_info["quests"]:
                            if sentence[:15] in quest["description"]:
                                is_new = False
                                break
                        
                        if is_new:
                            name = sentence[:40] + "..." if len(sentence) > 40 else sentence
                            region_info["quests"].append({
                                "name": name.capitalize(),
                                "description": sentence.strip().capitalize()
                            })
    
    # En fazla 5 POI ve 5 görev göster
    region_info["points_of_interest"] = region_info["points_of_interest"][:5]
    region_info["quests"] = region_info["quests"][:5]
    
    return region_info

# Test fonksiyonu
if __name__ == "__main__":
    # Belirli bir bölge için bilgi ara
    test_region = "Emerald Grove"
    print(f"Searching for information about '{test_region}'...")
    
    region_info = get_region_information(test_region)
    
    print(f"\nRegion: {region_info['name']}")
    if region_info["description"]:
        print(f"\nDescription: {region_info['description']}")
    
    if region_info["points_of_interest"]:
        print("\nPoints of Interest:")
        for poi in region_info["points_of_interest"]:
            print(f"- {poi['name']}: {poi['description']}")
    
    if region_info["quests"]:
        print("\nQuests:")
        for quest in region_info["quests"]:
            print(f"- {quest['name']}")
    
    if region_info["urls"]:
        print("\nMore Information:")
        for url_info in region_info["urls"]:
            print(f"- {url_info['title']}: {url_info['url']}")
    
    # Genel oyun sorgusu ara
    test_query = "best wizard build"
    print(f"\n\nSearching for '{test_query}'...")
    
    results = search_game_content(test_query)
    
    if results:
        print("\nSearch Results:")
        for i, result in enumerate(results, 1):
            print(f"\n{i}. {result['title']}")
            print(f"   {result['description']}")
            print(f"   URL: {result['url']}")
    else:
        print("No results found.")