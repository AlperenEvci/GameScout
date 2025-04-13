# gamescout/llm/api_client.py

import requests
import json
import os
from config import settings
from utils.helpers import get_logger

logger = get_logger(__name__)

class LLMAPIClient:
    """Client for interacting with LLM APIs (OpenAI, Gemini, etc.)"""
    
    def __init__(self):
        """Initialize the LLM API client with settings from config."""
        self.api_key = settings.LLM_API_KEY
        self.api_endpoint = settings.LLM_API_ENDPOINT
        self.model = settings.LLM_MODEL
        self.provider = settings.LLM_PROVIDER
        self.max_retries = 2
        self.timeout = 10  # seconds
        
        if not self.api_key and self.provider != "none":
            logger.warning("LLM API key not configured. Dynamic recommendations will be disabled.")
    
    def is_available(self):
        """Check if the LLM API is configured and available."""
        return self.api_key and self.provider.lower() != "none"
    
    def get_recommendation(self, game_state, prompt_type="general"):
        """
        Get recommendations from the LLM based on the current game state.
        
        Args:
            game_state: Current GameState object with location, class, etc.
            prompt_type: Type of prompt to use ("general", "combat", "exploration", etc.)
            
        Returns:
            List of recommendation strings, or empty list if API is unavailable/fails
        """
        if not self.is_available():
            logger.info("LLM API not configured. Returning empty recommendations.")
            return []
            
        # Build a prompt based on game state and prompt type
        prompt = self._build_prompt(game_state, prompt_type)
        
        # Call appropriate provider method based on settings
        if self.provider.lower() == "openai":
            return self._call_openai_api(prompt)
        elif self.provider.lower() == "gemini":
            return self._call_gemini_api(prompt)
        elif self.provider.lower() == "azure":
            return self._call_azure_openai_api(prompt)
        else:
            logger.error(f"Unsupported LLM provider: {self.provider}")
            return []
    
    def _build_prompt(self, game_state, prompt_type):
        """Build a prompt for the LLM based on the game state."""
        base_prompt = settings.LLM_PROMPT_TEMPLATE
        
        # Replace placeholder variables in template
        prompt = base_prompt.replace("{region}", game_state.current_region or "Unknown")
        prompt = prompt.replace("{character_class}", game_state.character_class or "Unknown")
        
        # Add detected keywords
        keywords = ", ".join(game_state.detected_keywords) if game_state.detected_keywords else "None"
        prompt = prompt.replace("{keywords}", keywords)
        
        # Add nearby points of interest
        pois = []
        for poi in game_state.nearby_points_of_interest:
            pois.append(f"{poi['name']}: {poi.get('description', '')}")
        poi_text = "\n".join(pois) if pois else "None"
        prompt = prompt.replace("{points_of_interest}", poi_text)
        
        # Add nearby quests
        quests = []
        for quest in game_state.region_quests:
            quests.append(f"{quest['name']}: {quest.get('description', '')}")
        quest_text = "\n".join(quests) if quests else "None"
        prompt = prompt.replace("{quests}", quest_text)
        
        # Add the prompt type-specific instructions
        if prompt_type == "combat":
            prompt += "\nBu savaş durumu için taktiksel öneriler ver."
        elif prompt_type == "exploration":
            prompt += "\nBu bölgedeki değerli eşyalar ve keşif önerileri ver."
        elif prompt_type == "social":
            prompt += "\nNPC'lerle etkileşim için öneriler ver."
        
        logger.debug(f"Built LLM prompt: {prompt[:100]}...")
        return prompt
    
    def _call_openai_api(self, prompt):
        """Call the OpenAI API with the given prompt."""
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": settings.LLM_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                "temperature": settings.LLM_TEMPERATURE,
                "max_tokens": settings.LLM_MAX_TOKENS
            }
            
            response = requests.post(
                self.api_endpoint,
                headers=headers,
                data=json.dumps(data),
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                result = response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    content = result["choices"][0]["message"]["content"]
                    # Parse the content into individual recommendations
                    recommendations = self._parse_recommendations(content)
                    logger.info(f"Received {len(recommendations)} recommendations from LLM")
                    return recommendations
                else:
                    logger.error("Unexpected response format from OpenAI API")
            else:
                logger.error(f"OpenAI API error: {response.status_code}, {response.text}")
        
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}", exc_info=True)
        
        return []  # Return empty list on error
    
    def _call_gemini_api(self, prompt):
        """Call the Google Gemini API with the given prompt."""
        try:
            headers = {
                "Content-Type": "application/json"
            }
            
            # Gemini API format for newer models
            data = {
                "contents": [
                    {
                        "parts": [
                            {"text": settings.LLM_SYSTEM_PROMPT + "\n\n" + prompt}
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": settings.LLM_TEMPERATURE,
                    "maxOutputTokens": settings.LLM_MAX_TOKENS,
                    "topP": 0.95,
                    "topK": 40
                }
            }
            
            # Add API key as URL parameter
            url = f"{self.api_endpoint}?key={self.api_key}"
            
            # Daha ayrıntılı hata ayıklama bilgileri
            logger.info(f"Sending request to Gemini API: {url[:60]}...")
            logger.debug(f"Request data: {json.dumps(data)[:200]}...")
            
            response = requests.post(
                url,
                headers=headers,
                data=json.dumps(data),
                timeout=self.timeout
            )
            
            logger.info(f"Gemini API response status: {response.status_code}")
            
            if response.status_code == 200:
                result = response.json()
                logger.debug(f"Response JSON keys: {list(result.keys())}")
                
                if "candidates" in result and len(result["candidates"]) > 0:
                    content = result["candidates"][0]["content"]["parts"][0]["text"]
                    recommendations = self._parse_recommendations(content)
                    logger.info(f"Received {len(recommendations)} recommendations from Gemini")
                    return recommendations
                else:
                    logger.error(f"Unexpected response format from Gemini API: {result}")
                    if "error" in result:
                        logger.error(f"Gemini API error details: {result['error']}")
            else:
                # Tam hata metni - güvenli bir uzunlukta göster
                error_text = response.text[:500] + "..." if len(response.text) > 500 else response.text
                logger.error(f"Gemini API error: {response.status_code}, {error_text}")
        
        except Exception as e:
            logger.error(f"Error calling Gemini API: {e}", exc_info=True)
        
        return []  # Return empty list on error
    
    def _call_azure_openai_api(self, prompt):
        """Call the Azure OpenAI API with the given prompt."""
        # Implementation for Azure OpenAI API (similar to OpenAI but with Azure-specific endpoint)
        logger.warning("Azure OpenAI implementation is a placeholder. Using default OpenAI implementation.")
        return self._call_openai_api(prompt)
    
    def _parse_recommendations(self, content):
        """Parse the LLM response into individual recommendation strings."""
        recommendations = []
        
        # Try to split by common separators
        lines = content.split("\n")
        for line in lines:
            line = line.strip()
            # Skip empty lines and headers
            if not line or line.startswith("#") or line.lower().startswith("öneriler"):
                continue
                
            # Remove list markers like "1.", "-", "*", etc.
            cleaned_line = line
            if line.startswith(("- ", "* ", "> ")):
                cleaned_line = line[2:].strip()
            elif len(line) > 2 and line[0].isdigit() and line[1] == ".":
                cleaned_line = line[2:].strip()
                
            if cleaned_line and len(cleaned_line) > 5:  # Require some minimum length
                recommendations.append(cleaned_line)
        
        # If we couldn't parse properly, just return the whole text as one recommendation
        if not recommendations and content.strip():
            recommendations.append(content.strip())
            
        return recommendations[:5]  # Limit to max 5 recommendations


# Example usage if run directly
if __name__ == "__main__":
    from agent.decision_engine import GameState
    
    # Create test game state
    test_state = GameState()
    test_state.current_region = "Emerald Grove"
    test_state.character_class = "Wizard"
    test_state.detected_keywords = ["chest", "magic", "trap"]
    
    # Create client and get recommendations
    client = LLMAPIClient()
    if client.is_available():
        print("Testing LLM API...")
        recommendations = client.get_recommendation(test_state)
        print("\nReceived Recommendations:")
        for i, rec in enumerate(recommendations, 1):
            print(f"{i}. {rec}")
    else:
        print("LLM API not configured. Set LLM_API_KEY and LLM_PROVIDER in settings.py")