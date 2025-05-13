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
        """
        RAG asistanını başlat ve gerekli bileşenleri yükle.
        
        Modern RAG mimarisi (2025) şunları içerir:
        1. Gelişmiş bilgi tabanı entegrasyonu
        2. Sorgu sonuçları için önbellek
        3. Çoklu dil desteği
        4. Oturum yönetimi
        5. Metrik takibi
        """
        self.knowledge_base = BG3KnowledgeBase()
        self.llm_client = LLMAPIClient()
        self.hud_queue = queue.Queue()
        self.hud = None
        self.is_initialized = False
        self.last_query_time = 0
        self.rate_limit = 3  # Saniye cinsinden sorgu sıklığı limiti
        
        # Çoklu dil desteği (varsayılan Türkçe)
        self.language = "tr"
        
        # Sorgu önbelleği - sık sorulan sorular için yanıtları cache'le
        self.query_cache = {}
        self.max_cache_size = 50  # Maksimum önbellek boyutu
        
        # Oturum verisi - kullanıcının sorgu geçmişini tut
        self.session_history = []
        self.max_history = 10
        
        # Performans metrikleri
        self.metrics = {
            "total_queries": 0,
            "successful_queries": 0,
            "failed_queries": 0,
            "cache_hits": 0,
            "avg_response_time": 0,
        }
        
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
      def _get_context_window(self):
        """API tipine göre maksimum bağlam penceresini belirle."""
        # Different LLM providers have different context window limits
        context_limits = {
            "openai": 14000,  # Approximate for gpt-3.5-turbo
            "deepseek": 8000,  # DeepSeek Chat model
            "gemini": 12000,   # Gemini Pro
            # Default to conservative value
            "default": 4000  
        }
        
        from config import settings
        api_type = settings.LLM_API_TYPE.lower()
        return context_limits.get(api_type, context_limits["default"])
        
    def _prepare_contexts(self, contexts, max_length=None):
        """
        Birden fazla bağlamı birleştirip formatla, token limitlerini aşmamak için optimize et.
        
        Yeni stratejiler:
        1. Bağlam penceresine sığacak şekilde içeriği kısalt
        2. İçeriği alakasına göre sırala
        3. Duplicated içeriği temizle
        4. Her bir bağlam kaynağını daha net belirt
        """
        if not max_length:
            max_length = self._get_context_window() - 2000  # Prompt için 2000 token rezerve et
        
        formatted_contexts = []
        current_length = 0
        seen_content = set()  # Duplicate içerik tespiti için
        
        # Sort contexts by relevance score if available
        if contexts and "score" in contexts[0]:
            contexts = sorted(contexts, key=lambda x: x.get("score", 0), reverse=True)
        
        for i, context in enumerate(contexts):
            title = context.get('title', 'Başlık yok')
            content = context.get('content', 'İçerik yok')
            url = context.get('url', 'URL yok')
            
            # Skip duplicate content
            content_hash = hash(content[:100])  # Use first 100 chars as fingerprint
            if content_hash in seen_content:
                logger.debug(f"Skipping duplicate content: {title}")
                continue
            seen_content.add(content_hash)
            
            # Calculate space needed for this context
            context_header = f"--- Kaynak {i+1}: {title} ---\n"
            context_footer = f"URL: {url}\n---\n"
            
            # Estimate length
            header_length = len(context_header) // 4  # Approximate token count
            footer_length = len(context_footer) // 4  # Approximate token count
            content_max_length = min(len(content), (max_length - current_length - header_length - footer_length) * 4)
            
            if content_max_length < 200:  # Not enough space for meaningful content
                break
                
            # Truncate content if necessary
            if len(content) > content_max_length:
                content = content[:content_max_length] + "..."
                
            formatted_context = context_header + content + "\n" + context_footer
            formatted_contexts.append(formatted_context)
            
            # Update current length (approximate token count)
            current_length += (len(formatted_context) // 4)
            
            if current_length >= max_length:
                break
                
        return "".join(formatted_contexts)
      def build_prompt(self, user_query, contexts):
        """
        Kullanıcı sorgusu ve bağlamlardan gelişmiş bir LLM prompt'u oluştur.
        
        Modern RAG teknikleri (2025):
        1. Daha yapılandırılmış bağlam teslimi
        2. Açıkça belirtilmiş roller ve yönergeler
        3. Kaynak alıntılama yönergesi
        4. Yanıt format yapısı
        5. Düşünce zinciri (Chain-of-thought) teşviki
        6. Öz değerlendirme talimati
        """
        # Bağlamları hazırla
        formatted_contexts = self._prepare_contexts(contexts)
        
        # Dil belirleme
        language_instruction = "Türkçe olarak"  # Varsayılan Türkçe
        if self.language != "tr":
            language_instruction = "İngilizce olarak"
            
        # Gelişmiş çok aşamalı sorgulama yapısı
        prompt = f"""Siz Baldur's Gate 3 konusunda uzmanlaşmış bir yapay zeka asistanısınız.

### SORU:
{user_query}

### BAĞLAM BİLGİLERİ:
{formatted_contexts}

### TALİMATLAR:
1. Önce verilen bağlamları analiz edin ve soruyla en alakalı bilgileri belirleyin.
2. Kullanıcının sorusunu {language_instruction} ve sadece verilen bağlam bilgilerine dayanarak yanıtlayın.
3. Yanıtınızı yapılandırın:
   - İlk olarak, sorunun kısa ve net bir yanıtını verin
   - Ardından, gerekirse ek bağlam veya detaylar ekleyin
   - Son olarak, oyuncunun bu bilgiyi oyun içinde nasıl kullanabileceği hakkında 1-2 pratik öneri sunun

4. Eğer verilen bilgilerde doğrudan bir cevap yoksa, bağlamdaki en alakalı bilgileri kullanarak bir yanıt oluşturun ve bilginizin sınırlı olduğunu dürüstçe belirtin.
5. Eğer sorunun yanıtı bağlamlarda tamamen yoksa, "Bu konuda yeterli bilgiye sahip değilim" deyin ve alakalı olabilecek diğer bilgileri önerin.
6. Cevaplar net, doğru ve konu odaklı olmalı.
7. Eğer cevap İngilizce bir kaynaktan geliyorsa, bunu düzgün bir şekilde Türkçeye çevirin.
8. Verdiğiniz bilgilerin hangi kaynaktan geldiğini açıkça belirtin. Örneğin: "Kaynak 2'ye göre..."
9. Yanıtınızın sonunda, soruyu tam olarak cevaplayıp cevaplamadığınızı değerlendirin ve gerekirse ek araştırma için öneriler sunun.

### YANITINIZ:
"""
        
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
        
        Gelişmiş RAG akışı (2025):
        1. Sorgu ön işleme ve genişletme
        2. Hibrit (semantik + anahtar kelime) arama
        3. Dinamik bağlam seçimi
        4. Gelişmiş prompt yapılandırması
        5. Hata toleransı ve yedek mekanizmalar
        6. Yanıt sonrası işleme
        
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
            
            # 1. Sorgu ön işleme - basit normalizasyon
            cleaned_query = user_input.strip()
            
            # 2. Gelişmiş arama stratejisi - daha fazla sonuç alıp sonra filtrele
            initial_k = 8  # İlk aramada daha fazla sonuç al
            contexts = self.rag_search(cleaned_query, top_k=initial_k)
            
            # 3. Geri dönüş stratejisi - sonuç bulunamazsa
            if not contexts:
                # Daha basit anahtar kelimelerle yeniden dene
                import re
                keywords = re.findall(r'\b\w{4,}\b', cleaned_query)
                if keywords and len(keywords) >= 2:
                    fallback_query = ' '.join(keywords[:3])  # En uzun 3 kelimeyi kullan
                    logger.info(f"İlk arama başarısız, şununla yeniden deneniyor: '{fallback_query}'")
                    contexts = self.rag_search(fallback_query, top_k=initial_k)
            
            # 4. Yine sonuç yoksa bilgilendirici yanıt ver
            if not contexts:
                response = "Bu konu hakkında bilgi tabanımda yeterli bilgi bulunamadı. Lütfen sorunuzu farklı şekilde sorun veya daha genel bir konuyla ilgili bilgi isteyin."
                self.hud_queue.put(response)
                return response
            
            # 5. En alakalı olanları seç (örn. en iyi 5)
            best_contexts = contexts[:5]
            
            # 6. LLM promptunu oluştur
            prompt = self.build_prompt(cleaned_query, best_contexts)
            
            # 7. LLM'e gönder ve yanıtı al
            response = self.ask_llm(prompt)
            
            # 8. Yanıt sonrası işleme - formatla ve temizle
            # Fazla boşlukları temizle ve kaynak formatını düzelt
            response = response.replace("\n\n\n", "\n\n").strip()
            response = self.process_response_for_turkish(response)
            
            # 9. HUD'da göster (daha düzenli ve okunaklı formatla)
            formatted_response = f"""
📝 Soru: {user_input}

🔍 Yanıt: 
{response}
            """
            self.hud_queue.put(formatted_response)
            
            # 10. Metrik kaydetme - gelecekte analiz için
            # Burada gelecekteki iyileştirmeler için başarılı sorgu tamamlanma metriği kaydedilebilir
            
            return response
            
        except Exception as e:
            # Hata durumunda yedek yanıt stratejisi
            error_msg = f"Soru yanıtlanırken hata: {str(e)}"
            logger.error(error_msg)
            
            # Kullanıcıya daha yardımcı bir hata mesajı göster
            friendly_error = "Yanıt oluşturulurken teknik bir sorun oluştu. Lütfen birazdan tekrar deneyin veya sorunuzu farklı şekilde sorun."
            self.hud_queue.put(friendly_error)
            
            return friendly_error
    
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