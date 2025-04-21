#!/usr/bin/env python3
# rag.py - RAG (Retrieval-Augmented Generation) entegrasyonu

import os
import sys
import logging
import queue
import time
from pathlib import Path

# Proje kök dizinini ekleyerek diğer modülleri içe aktarabilmemizi sağlayalım
sys.path.append(str(Path(__file__).parent.parent))

from query import BG3KnowledgeBase
from llm.api_client import LLMAPIClient
from ui.hud_display import HudWindow
from utils.helpers import get_logger

logger = get_logger(__name__)

class RAGAssistant:
    """
    Baldur's Gate 3 oyuncularına bilgi ve görevlerle ilgili yardım sağlayan RAG sistemi.
    
    Bu sınıf, vektör veritabanı üzerinde arama yapar, sonuçları LLM'e prompt olarak gönderir
    ve oyuncuya HUD üzerinde gösterir.
    """
    
    def __init__(self):
        """RAG asistanını başlat ve gerekli bileşenleri yükle."""
        self.knowledge_base = BG3KnowledgeBase()
        self.llm_client = LLMAPIClient()
        self.hud_queue = queue.Queue()
        self.hud = None
        self.is_initialized = False
        self.last_query_time = 0
        self.rate_limit = 3  # Saniye cinsinden sorgu sıklığı limiti
        
    def initialize(self):
        """Bilgi tabanını ve HUD'u başlat."""
        try:
            # Bilgi tabanını yükle
            kb_loaded = self.knowledge_base.initialize()
            if not kb_loaded:
                logger.error("Bilgi tabanı yüklenemedi. İndeksleme işlemi çalıştırıldı mı?")
                return False
            
            # HUD'u başlat
            self.hud = HudWindow(self.hud_queue)
            self.hud.start()
            self.hud_queue.put("GameScout RAG Asistanı yükleniyor...")
            
            self.is_initialized = True
            logger.info("RAG Asistanı başlatıldı")
            return True
            
        except Exception as e:
            logger.error(f"RAG Asistanı başlatılırken hata: {str(e)}")
            return False
    
    def rag_search(self, query, top_k=3):
        """Bilgi tabanında arama yaparak ilgili belgeleri getir."""
        if not self.is_initialized:
            logger.error("RAG Asistanı başlatılmadı. initialize() metodunu çağırın.")
            return []
        
        try:
            logger.info(f"'{query}' için bilgi tabanında arama yapılıyor...")
            results = self.knowledge_base.search(query, top_k=top_k)
            logger.info(f"{len(results)} sonuç bulundu")
            return results
        except Exception as e:
            logger.error(f"Arama sırasında hata: {str(e)}")
            return []
    
    def build_prompt(self, user_query, contexts):
        """Kullanıcı sorgusu ve bağlamlardan bir LLM prompt'u oluştur."""
        prompt = f"""
        Kullanıcının Sorusu: {user_query}
        
        Aşağıdaki bağlamları kullanarak kullanıcının sorusuna Türkçe olarak yanıt ver. 
        Eğer verilen bilgiler İngilizce ise, bunları doğru bir şekilde Türkçeye çevirerek cevap ver.
        Cevabın net, kısa ve doğru olsun. Sadece verilen bağlamlara dayanarak cevap ver.
        Eğer bağlamlarda cevap yoksa, "Bu konu hakkında yeterli bilgim yok" şeklinde yanıt ver.
        Sen bir Baldur's Gate 3 oyunu asistanısın ve görevin oyuncuya yardımcı olmaktır.
        
        Bağlamlar:
        """
        
        for i, context in enumerate(contexts, 1):
            prompt += f"\n--- Bağlam {i} ---\n"
            prompt += f"Başlık: {context.get('title', 'Başlık yok')}\n"
            content = context.get('content', 'İçerik yok')
            # İçeriği LLM token limitlerini aşmamak için kısalt
            if len(content) > 1000:
                content = content[:1000] + "..."
            prompt += f"İçerik: {content}\n"
        
        return prompt
    
    def process_response_for_turkish(self, response):
        """LLM yanıtını Türkçe karakterleri koruyacak şekilde işle."""
        # Türkçe karakterlerin düzgün görüntülenmesi için kontroller
        tr_replacements = {
            'Ä±': 'ı',
            'Ã¼': 'ü',
            'Ã¶': 'ö',
            'ÅŸ': 'ş', 
            'Ã§': 'ç',
            'Äž': 'ğ',
            'Ä°': 'İ',
            'Ãœ': 'Ü',
            'Ã–': 'Ö',
            'Åž': 'Ş',
            'Ã‡': 'Ç',
            'Äž': 'Ğ'
        }
        
        for wrong, correct in tr_replacements.items():
            response = response.replace(wrong, correct)
            
        return response
    
    def ask_llm(self, prompt):
        """LLM'e prompt gönder ve yanıt al."""
        if not self.llm_client.is_available():
            logger.warning("LLM API yapılandırılmamış. Öneriler devre dışı.")
            return "LLM API yapılandırılmamış. Ayarlarınızı kontrol edin."
            
        try:
            # GameState nesnesinin özelliklerini prompt'a göre ayarla
            from agent.decision_engine import GameState
            game_state = GameState()
            game_state.detected_keywords = prompt.split()[:5]  # İlk 5 kelimeyi anahtar kelime olarak kullan
            
            # LLM'den yanıt al
            recommendations = self.llm_client.get_recommendation(game_state, "general")
            
            if not recommendations:
                return "LLM'den yanıt alınamadı."
                
            response = "\n".join(recommendations)
            # Türkçe karakter düzeltmesi yap
            response = self.process_response_for_turkish(response)
            return response
            
        except Exception as e:
            logger.error(f"LLM yanıtı alınırken hata: {str(e)}")
            return f"Hata oluştu: {str(e)}"
    
    def _is_rate_limited(self):
        """Sorgu hızı sınırına ulaşılıp ulaşılmadığını kontrol et"""
        current_time = time.time()
        if current_time - self.last_query_time < self.rate_limit:
            return True
        return False
    
    def ask_game_ai(self, user_input):
        """
        Oyuncu sorusunu al, RAG sistemini kullanarak yanıtla ve HUD'da göster.
        
        Args:
            user_input: Kullanıcının sorusu/girdisi
            
        Returns:
            str: LLM yanıtı
        """
        if not self.is_initialized:
            logger.error("RAG Asistanı başlatılmadı. initialize() metodunu çağırın.")
            return "RAG Asistanı başlatılmadı."
        
        # Sorgu sıklığı kontrolü yap
        if self._is_rate_limited():
            wait_time = self.rate_limit - (time.time() - self.last_query_time)
            msg = f"Lütfen {wait_time:.1f} saniye bekleyin..."
            logger.info(f"Sorgu sıklığı sınırına takıldı: {msg}")
            self.hud_queue.put(msg)
            return msg
        
        try:
            # Sorgu zamanını güncelle
            self.last_query_time = time.time()
            
            # Kullanıcı girdi bilgisini günlüğe kaydet
            logger.info(f"Kullanıcı sorusu: {user_input}")
            
            # HUD'a yükleniyor mesajı gönder
            self.hud_queue.put(f"'{user_input}' için yanıt aranıyor...")
            
            # Bilgi tabanında arama yap
            contexts = self.rag_search(user_input, top_k=5)  # Daha fazla bağlam getir
            
            if not contexts:
                response = "Bu konu hakkında bilgi bulunamadı."
                self.hud_queue.put(response)
                return response
            
            # LLM promptunu oluştur
            prompt = self.build_prompt(user_input, contexts)
            
            # LLM'e gönder ve yanıtı al
            response = self.ask_llm(prompt)
            
            # HUD'da göster (daha düzenli ve okunaklı)
            formatted_response = f"""
📝 Soru: {user_input}

🔍 Yanıt: 
{response}
            """
            self.hud_queue.put(formatted_response)
            
            return response
            
        except Exception as e:
            error_msg = f"Soru yanıtlanırken hata: {str(e)}"
            logger.error(error_msg)
            self.hud_queue.put(error_msg)
            return error_msg
    
    def shutdown(self):
        """RAG Asistanını düzgün şekilde kapat."""
        if self.hud:
            logger.info("HUD kapatılıyor...")
            self.hud.stop()
            self.hud.join(timeout=2)
        logger.info("RAG Asistanı kapatıldı")


# Örnek kullanım
if __name__ == "__main__":
    import time
    
    print("RAG Asistanı test ediliyor...")
    assistant = RAGAssistant()
    
    if not assistant.initialize():
        print("RAG Asistanı başlatılamadı.")
        sys.exit(1)
        
    try:
        # Birkaç örnek soru sor
        questions = [
            "Shadowheart kimdir?",
            "Emerald Grove'da hangi görevler var?",
            "Baldur's Gate 3'te savaş sistemi nasıl çalışır?",
            "Çıkış"
        ]
        
        for question in questions:
            if question.lower() == "çıkış":
                break
                
            print(f"\nSoru: {question}")
            response = assistant.ask_game_ai(question)
            print(f"Yanıt: {response}")
            time.sleep(5)  # HUD'daki yanıtı görmek için bekle
            
    except KeyboardInterrupt:
        print("\nKlavye kesintisi alındı.")
    finally:
        print("RAG Asistanı kapatılıyor...")
        assistant.shutdown()
        print("Test tamamlandı.")