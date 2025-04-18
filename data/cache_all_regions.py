# gamescout/data/cache_all_regions.py
#
# Bu script, Baldur's Gate 3'teki tüm bölgeler için harita verilerini
# önbelleğe alır. Programın ilk başlatılması sırasında veya verileri
# güncellemek istediğinizde çalıştırın.

import os
import sys
import time

# Ana dizini (gamescout/) Python yoluna ekle
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.map_data import GAME_REGIONS, fetch_fextralife_map_data, save_to_cache
from utils.helpers import get_logger

logger = get_logger(__name__)

def cache_all_regions():
    """Tüm bölgelerin harita verilerini önbelleğe alır."""
    logger.info("Tüm harita verilerini önbelleğe alma işlemi başlatılıyor...")
    
    # Toplam bölge sayısını hesapla
    total_regions = len(GAME_REGIONS)
    cached_regions = 0
    failed_regions = []
    
    # Her bölge için işlem yap
    for region_name in GAME_REGIONS:
        try:
            logger.info(f"Şu bölge için veri alınıyor: {region_name} ({cached_regions+1}/{total_regions})")
            
            # Veriyi al
            region_data = fetch_fextralife_map_data(region_name)
            
            if region_data:
                # Yerel bilgilerle zenginleştir
                if "map_coordinates" not in region_data and region_name in GAME_REGIONS:
                    region_data["map_coordinates"] = GAME_REGIONS[region_name].get("map_coordinates")
                
                # Önbelleğe kaydet
                success = save_to_cache(region_name, region_data)
                if success:
                    cached_regions += 1
                    logger.info(f"✓ Bölge önbelleğe alındı: {region_name}")
                else:
                    failed_regions.append(region_name)
                    logger.error(f"✗ Bölge önbelleğe alınamadı: {region_name}")
            else:
                # Bölge verisi alınamadı, yerel veriyi kullan
                if region_name in GAME_REGIONS:
                    local_data = GAME_REGIONS[region_name]
                    success = save_to_cache(region_name, local_data)
                    if success:
                        cached_regions += 1
                        logger.info(f"✓ Bölge yerel veriden önbelleğe alındı: {region_name}")
                    else:
                        failed_regions.append(region_name)
                        logger.error(f"✗ Bölge önbelleğe alınamadı: {region_name}")
                else:
                    failed_regions.append(region_name)
                    logger.error(f"✗ Veri bulunamadı: {region_name}")
            
            # Sunucuları rahatsız etmemek için biraz bekle
            time.sleep(1)
            
        except Exception as e:
            failed_regions.append(region_name)
            logger.error(f"✗ Bölge önbelleğe alma işlemi sırasında hata: {region_name}: {e}")
    
    # Sonuçları raporla
    logger.info(f"Önbelleğe alma işlemi tamamlandı. "
                f"Toplam {total_regions} bölgeden {cached_regions} tanesi başarıyla önbelleğe alındı.")
    
    if failed_regions:
        logger.warning(f"Önbelleğe alınamayan bölgeler ({len(failed_regions)}): {', '.join(failed_regions)}")
    
    return cached_regions, failed_regions

if __name__ == "__main__":
    print("Baldur's Gate 3 harita verilerini önbelleğe alma işlemi başlatılıyor...")
    
    start_time = time.time()
    cached, failed = cache_all_regions()
    elapsed_time = time.time() - start_time
    
    print(f"\nÖnbelleğe alma işlemi tamamlandı!")
    print(f"Toplam süre: {elapsed_time:.1f} saniye")
    print(f"Başarılı: {cached} bölge")
    
    if failed:
        print(f"Başarısız: {len(failed)} bölge - {', '.join(failed)}")
    else:
        print("Tüm bölgeler başarıyla önbelleğe alındı!")
    
    print("\nİpucu: GameScout uygulamasını başlatmadan önce tüm bölge verilerinin")
    print("önbelleğe alınmış olması performansı artıracak ve internet bağlantısı")
    print("olmadığında bile çalışmasını sağlayacaktır.")