#!/usr/bin/env python3
# llm/api_client.py - LLM API istemcisi

import os
import json
import requests
import logging
from pathlib import Path
from utils.helpers import get_logger

# Proje kök dizinini import için ekleyin
import sys
sys.path.append(str(Path(__file__).parent.parent))

from config import settings

logger = get_logger(__name__)

class LLMAPIClient:
    """
    Çeşitli LLM API'lerini (OpenAI, DeepSeek, Gemini vb.) kullanmak için istemci.
    LLM bazlı önerilerin üretilmesi için kullanılır.
    """
    
    def __init__(self):
        """API seçeneklerini yapılandırma dosyasından yükle."""
        self.api_type = settings.LLM_API_TYPE
        self.api_key = settings.LLM_API_KEY
        self.api_model = settings.LLM_API_MODEL
        self.api_endpoint = settings.LLM_API_ENDPOINT
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.temperature = settings.LLM_TEMPERATURE
        self.language = "tr"  # Varsayılan dil olarak Türkçe

    def is_available(self):
        """API'nin kullanıma hazır olup olmadığını kontrol et."""
        # En azından API türü ve anahtarı olmalı
        return bool(self.api_type and self.api_key)
    
    def get_base_prompt(self, game_state, category="general"):
        """Oyun durumuna göre temel prompt oluşturur."""
        # Basit durum formatı
        state_desc = f"Bölge: {game_state.current_region if game_state.current_region else 'Bilinmiyor'}, "
        state_desc += f"Karakter Sınıfı: {game_state.character_class}, "
        
        if game_state.nearby_points_of_interest:
            poi_names = [poi['name'] for poi in game_state.nearby_points_of_interest[:3]]
            state_desc += f"Yakındaki Önemli Yerler: {', '.join(poi_names)}, "
            
        if game_state.detected_keywords:
            state_desc += f"Tespit Edilen Anahtar Kelimeler: {', '.join(game_state.detected_keywords)}, "
        
        # Oyuncu için ipuçları ve öneriler oluşturacak prompt
        prompt = f"""
        Sen bir Baldur's Gate 3 oyun asistanısın. Oyuncunun oyun deneyimini artırmak için 
        yararlı ipuçları ve öneriler sunuyorsun. Aşağıdaki oyun durum bilgilerine dayanarak
        oyuncuya yardımcı olacak {self.language} dilinde 3 yararlı öneri veya ipucu oluştur.
        Yanıtların kısa, öz ve doğrudan yararlı olmalı.
        
        Mevcut oyun durumu:
        {state_desc}
        
        İstenilen öneri kategorisi: {category}
        
        Öneriler veya ipuçları (her biri en fazla 150 karakter):
        """
        
        return prompt
    
    def get_rag_prompt(self, user_query, contexts):
        """RAG için prompt oluştur."""
        prompt = f"""
        Kullanıcının Sorusu: {user_query}
        
        Aşağıdaki bağlamları kullanarak kullanıcının sorusuna {self.language} dilinde yanıt ver. 
        Eğer verilen bilgiler İngilizce ise, bunları doğru bir şekilde {self.language} diline çevirerek cevap ver.
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
    
    def set_language(self, language_code):
        """Yanıt dilini ayarla (tr: Türkçe, en: İngilizce)."""
        self.language = language_code
        logger.info(f"LLM yanıt dili şu şekilde ayarlandı: {language_code}")
    
    def call_openai(self, prompt):
        """OpenAI API'sini çağır."""
        import openai
        
        openai.api_key = self.api_key
        
        try:
            completion = openai.ChatCompletion.create(
                model=self.api_model or "gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "Sen bir Baldur's Gate 3 oyun asistanısın. Türkçe cevaplar ver."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=self.max_tokens or 300,
                temperature=self.temperature or 0.7
            )
            
            return completion.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"OpenAI API çağrısı başarısız: {str(e)}")
            return None
    
    def call_deepseek(self, prompt):
        """DeepSeek API'sini çağır."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": self.api_model or "deepseek-chat",
            "messages": [
                {"role": "system", "content": "Sen bir Baldur's Gate 3 oyun asistanısın. Türkçe cevaplar ver."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": self.max_tokens or 300,
            "temperature": self.temperature or 0.7
        }
        
        try:
            response = requests.post(
                self.api_endpoint or "https://api.deepseek.com/v1/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            response.raise_for_status()
            
            response_data = response.json()
            return response_data["choices"][0]["message"].content.strip()
            
        except Exception as e:
            logger.error(f"DeepSeek API çağrısı başarısız: {str(e)}")
            return None
            
    def call_gemini(self, prompt):
        """Google Gemini API'sini çağır."""
        try:
            import google.generativeai as genai
            
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(
                self.api_model or "gemini-pro", 
                generation_config={"temperature": self.temperature or 0.7, "max_output_tokens": self.max_tokens or 300}
            )
            
            system_instruction = "Sen bir Baldur's Gate 3 oyun asistanısın. Türkçe cevaplar ver."
            
            response = model.generate_content(
                [system_instruction, prompt]
            )
            
            return response.text.strip()
            
        except Exception as e:
            logger.error(f"Gemini API çağrısı başarısız: {str(e)}")
            return None
    
    def process_response_for_turkish(self, response):
        """LLM yanıtındaki olası bozuk Türkçe karakterleri düzelt."""
        if not response or self.language != "tr":
            return response
            
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
    
    def get_recommendation(self, game_state, category="general"):
        """
        Oyun durumuna dayalı olarak LLM'den önerileri alır.
        
        Args:
            game_state: Oyun durum nesnesi
            category: Öneri kategorisi (general, combat, exploration, vb.)
        
        Returns:
            list: Yanıt listesi veya boş liste (hata durumunda)
        """
        if not self.is_available():
            logger.warning("LLM API yapılandırılmamış, öneriler devre dışı")
            return []
            
        try:
            # Prompt oluştur
            prompt = self.get_base_prompt(game_state, category)
            
            # API türüne göre çağrı yap
            response = None
            
            if self.api_type.lower() == "openai":
                response = self.call_openai(prompt)
            elif self.api_type.lower() == "deepseek":
                response = self.call_deepseek(prompt)
            elif self.api_type.lower() == "gemini":
                response = self.call_gemini(prompt)
            else:
                logger.error(f"Desteklenmeyen API türü: {self.api_type}")
                return []
                
            if not response:
                logger.warning("LLM API'den yanıt alınamadı")
                return []
                
            # Türkçe karakter düzeltmesi
            response = self.process_response_for_turkish(response)
                
            # Yanıtı satırlara ayır ve filtrele
            lines = [line.strip() for line in response.split("\n") if line.strip()]
            
            # İpucu/Öneri formatı kontrolü
            recommendations = []
            for line in lines:
                # Numaralandırma, tire veya yıldızla başlayan satırları al
                if (line.startswith(("1.", "2.", "3.", "-", "*", "•")) or 
                    any(line.lower().startswith(kw) for kw in ["ipucu:", "öneri:", "tavsiye:"])):
                    # Öneri başlangıcı olabilecek öğeleri temizle
                    cleaned = line
                    for prefix in ["1.", "2.", "3.", "-", "*", "•", "ipucu:", "öneri:", "tavsiye:"]:
                        if cleaned.lower().startswith(prefix):
                            cleaned = cleaned[len(prefix):].strip()
                            break
                    recommendations.append(cleaned)
            
            # Eğer düzgün ipuçları bulunamadıysa, tüm yanıtı kullan
            if not recommendations and lines:
                recommendations = [r for r in lines if len(r) > 10 and len(r) < 200]
                
            # En fazla 3 öneri döndür
            return recommendations[:3]
            
        except Exception as e:
            logger.error(f"Öneri alınırken hata: {str(e)}")
            return []
    
    def get_rag_response(self, user_query, contexts):
        """
        Kullanıcı sorgusuna ve bağlamlara dayanarak LLM'den RAG yanıtı alır.
        
        Args:
            user_query: Kullanıcı sorgusur
            contexts: Bilgi tabanından alınan ilgili bağlamlar
            
        Returns:
            str: LLM yanıtı veya hata mesajı
        """
        if not self.is_available():
            return "LLM API yapılandırılmamış. Ayarlarınızı kontrol edin."
            
        try:
            # RAG promptu oluştur
            prompt = self.get_rag_prompt(user_query, contexts)
            
            # API türüne göre çağrı yap
            response = None
            
            if self.api_type.lower() == "openai":
                response = self.call_openai(prompt)
            elif self.api_type.lower() == "deepseek":
                response = self.call_deepseek(prompt)
            elif self.api_type.lower() == "gemini":
                response = self.call_gemini(prompt)
            else:
                return f"Desteklenmeyen API türü: {self.api_type}"
                
            if not response:
                return "LLM'den yanıt alınamadı."
                
            # Türkçe karakter düzeltmesi
            response = self.process_response_for_turkish(response)
            
            return response
            
        except Exception as e:
            logger.error(f"RAG yanıtı alınırken hata: {str(e)}")
            return f"Hata oluştu: {str(e)}"


# Test - Örnek kullanım
if __name__ == "__main__":
    from agent.decision_engine import GameState
    
    # Test için basit bir GameState nesnesi oluştur
    gs = GameState()
    gs.current_region = "Emerald Grove"
    gs.character_class = "Wizard"
    gs.detected_keywords = ["görev", "savaş", "büyü"]
    
    # LLM API istemcisini başlat
    client = LLMAPIClient()
    
    # Dil tercihi
    client.set_language("tr")  # Türkçe yanıtlar için
    
    # API yapılandırılmışsa öneriler al
    if client.is_available():
        print("\nGenel öneriler:")
        recommendations = client.get_recommendation(gs, "general")
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec}")
            
        print("\nSavaş önerileri:")
        combat_recommendations = client.get_recommendation(gs, "combat")
        for i, rec in enumerate(combat_recommendations, 1):
            print(f"{i}. {rec}")
    else:
        print("LLM API yapılandırılmamış. API türünü ve anahtarınızı ayarlayın.")