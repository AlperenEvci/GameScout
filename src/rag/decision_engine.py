"""
Decision Engine Module for GameScout

This module analyzes captured game information and generates contextual recommendations.
It maintains the current game state, tracks detected regions, and provides relevant tips
to the player based on their situation and character class.
"""

from config import settings
from src.utils.helpers import get_logger
import random
import time
import re
import sys
import os
import logging
from pathlib import Path
from src.data.sources.map_data import get_nearby_points_of_interest, get_quests_for_region
from src.data.sources.web_search import search_game_content, get_region_information
from src.llm.api_client import LLMAPIClient

# Add project root to Python path for imports
project_root = Path(__file__).parent.parent.parent
if project_root not in sys.path:
    sys.path.append(str(project_root))

# Try to import BG3KnowledgeBase from retriever module
try:
    from src.rag.retriever import BG3KnowledgeBase
except ImportError:
    BG3KnowledgeBase = None

logger = get_logger(__name__)

# Initialize the BG3 Knowledge Base
bg3_kb = None
if BG3KnowledgeBase is not None:
    bg3_kb = BG3KnowledgeBase()
    try:
        kb_init_success = bg3_kb.initialize()
        if kb_init_success:
            logger.info("Baldur's Gate 3 Knowledge Base initialized successfully")
        else:
            logger.warning("Failed to initialize Baldur's Gate 3 Knowledge Base")
            bg3_kb = None
    except Exception as e:
        logger.error(f"Error initializing BG3 Knowledge Base: {str(e)}")
        bg3_kb = None
else:
    logger.info("BG3 Knowledge Base module not found, RAG features will be disabled")

class GameState:
    """
    Represents the current detected state of the game.
    
    This class maintains information about the player's current region,
    character class, quests, and other relevant game state information
    extracted from OCR processing.
    """
    def __init__(self):
        # Current region information
        self.current_region = None
        self.previous_region = None
        self.last_region_change = 0
        
        # Character information
        self.character_class = None
        self.character_level = None
        
        # Location and environment
        self.nearby_points_of_interest = []
        self.region_quests = []
        
        # State tracking
        self.last_tip_time = 0
        self.last_tip_category = None
        self.recent_tips = []
        self.max_recent_tips = 10
        
        # Detected keywords from OCR
        self.detected_keywords = []
        self.keyword_timeouts = {}
    
    def update_from_ocr(self, text: str):
        """
        Updates the game state based on OCR text.
        
        Args:
            text: The OCR text to analyze
        """
        if not text:
            return
            
        # Clean and standardize text
        text = self._clean_ocr_text(text)
        
        # Region detection
        try:
            # First try to use settings.GAME_REGIONS
            game_regions = settings.GAME_REGIONS
            if not game_regions:
                # Fallback to importing directly if settings import failed
                from src.data.sources.map_data import GAME_REGIONS
                game_regions = GAME_REGIONS
                
            for region_name in game_regions:
                if self._fuzzy_region_match(text, region_name):
                    if self.current_region != region_name:
                        self.previous_region = self.current_region
                        self.current_region = region_name
                        self.last_region_change = time.time()
                        logger.info(f"Region changed: {self.current_region}")
                        
                        # Update location data for the new region
                        self.update_location_data()
                    break
        except (AttributeError, ImportError) as e:
            logger.error(f"Error accessing game regions: {e}")
            # Continue execution even if region detection fails
                
        # Check for quest updates
        if "quest" in text.lower() and "update" in text.lower():
            if "quest_update" not in self.detected_keywords:
                self.detected_keywords.append("quest_update")
                logger.info("Quest update detected")
    
    def _clean_ocr_text(self, text):
        """
        Cleans OCR text by removing control characters, standardizing whitespace, 
        and fixing common OCR mistakes.
        
        Args:
            text: The raw OCR text
            
        Returns:
            Cleaned text
        """
        # Remove ANSI color and format codes
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        text = ansi_escape.sub('', text)
        
        # Remove terminal-specific control characters (e.g., ^M, ^G, etc.)
        text = re.sub(r'[\x00-\x1F\x7F]', '', text)
        
        # Replace multiple whitespace, tabs, and newlines with a single space
        text = re.sub(r'\s+', ' ', text)
        
        # Fix common OCR errors
        ocr_fixes = {
            "0uest": "Quest",
            "0ame": "Game",
            # Add other common OCR errors here
        }
        
        for old, new in ocr_fixes.items():
            text = text.replace(old, new)
        
        return text.strip()
    
    def _fuzzy_region_match(self, text, region_name):
        """
        Performs fuzzy word matching to check if a region name appears in text.
        
        Args:
            text: The text to check
            region_name: The region name to look for
            
        Returns:
            Boolean indicating if the region name was found
        """
        text = text.lower()
        words = region_name.lower().split()
        
        # Count matches
        matches = 0
        for word in words:
            if word in text:
                matches += 1
        
        # Using a simplified similarity measure instead of Levenshtein distance
        match_ratio = matches / len(words)
        return match_ratio >= 0.6
    
    def update_location_data(self):
        """
        Updates location data for the current region.
        """
        if not self.current_region:
            return
            
        logger.info(f"Updating location data for region: {self.current_region}")
        self.nearby_points_of_interest = get_nearby_points_of_interest(self.current_region)
        self.region_quests = get_quests_for_region(self.current_region)
        
        logger.debug(f"Found {len(self.nearby_points_of_interest)} POIs and {len(self.region_quests)} quests")
    
    def add_recent_tip(self, tip):
        """
        Adds a tip to the recent tips list, maintaining max size.
        
        Args:
            tip: The tip to add
        """
        if tip not in self.recent_tips:
            self.recent_tips.append(tip)
            
        # Maintain maximum size
        if len(self.recent_tips) > self.max_recent_tips:
            self.recent_tips.pop(0)
    
    def was_recently_shown(self, tip):
        """
        Checks if a tip was recently shown.
        
        Args:
            tip: The tip to check
            
        Returns:
            Boolean indicating if the tip was recently shown
        """
        return tip in self.recent_tips

# BG3 tips database organized by categories
tips_database = {
    "combat": [
        "Tip: Use high ground for advantage in combat.",
        "Tip: Consider using consumables like scrolls and potions for tough battles.",
        "Tip: Check enemy resistances to select effective damage types.",
        "Tip: Use Disengage to avoid opportunity attacks.",
        "Tip: Pushing enemies off ledges deals fall damage.",
        "Tip: Use the environment like exploding barrels for additional damage.",
        "Tip: Remember to use your bonus action every turn.",
    ],
    "exploration": [
        "Tip: Use stealth to scout and avoid dangerous encounters.",
        "Tip: Look for hidden buttons and levers.",
        "Tip: Some walls can be destroyed to reveal secret areas.",
        "Tip: Use Jump to reach otherwise inaccessible areas.",
        "Tip: Note locked doors to return to later with keys.",
        "Tip: Some chests are trapped - use a high Perception character to check.",
        "Tip: Look for colorful floor tiles that might hide traps.",
    ],
    "social": [
        "Tip: Character backgrounds affect dialogue options.",
        "Tip: Watch for approval indicators in companion dialogue.",
        "Tip: Different skills can unlock unique conversation paths.",
        "Tip: Some NPCs respond better to certain races or classes.",
        "Tip: Stealing items can cause NPC reputation penalties.",
        "Tip: Use Speak with Dead on corpses for additional information.",
        "Tip: Some dialogue options are restricted by Intelligence or Charisma.",
    ],
}

def get_contextual_tips(game_state):
    """
    Generates contextual tips based on the current game state.
    
    Args:
        game_state: Current GameState object
        
    Returns:
        List of recommendation strings
    """
    recommendations = []
    
    # Limit frequency of tips
    current_time = time.time()
    time_since_last = current_time - game_state.last_tip_time
    
    # No more than 1 tip every 2 minutes
    if time_since_last < 120:
        logger.debug(f"Too soon for new tip, waiting {120 - time_since_last:.2f}sec")
        return recommendations
    
    # Select tip category - avoid repeating the last category
    categories = list(tips_database.keys())
    if game_state.last_tip_category and len(categories) > 1:
        categories.remove(game_state.last_tip_category)
    
    category = random.choice(categories)
    
    # Get a random tip from the category that hasn't been shown recently
    category_tips = tips_database[category]
    available_tips = [tip for tip in category_tips if not game_state.was_recently_shown(tip)]
    
    if available_tips:
        selected_tip = random.choice(available_tips)
        recommendations.append(selected_tip)
        game_state.add_recent_tip(selected_tip)
        game_state.last_tip_time = current_time
        game_state.last_tip_category = category
    
    return recommendations

def generate_recommendations(game_state):
    """
    Generates recommendations based on current game state.
    This is the main agent logic that provides contextual tips.
    
    Args:
        game_state: Current GameState object
        
    Returns:
        List of recommendation strings
    """
    logger.debug(f"Generating recommendations for state: {game_state}")
    
    # Start with contextual tips
    recommendations = get_contextual_tips(game_state)
    
    # If the region is known, add region-specific tips
    if game_state.current_region and bg3_kb:
        # Limit frequency of knowledge base queries
        current_time = time.time()
        time_since_last = current_time - game_state.last_tip_time
        
        # No more than 1 knowledge query every 3 minutes
        if time_since_last >= 180:  # 3 minutes
            try:
                query = f"What should a {game_state.character_class} know about {game_state.current_region}?"
                kb_results = bg3_kb.search(query, top_k=3)
                
                if kb_results and len(kb_results) > 0:
                    # Process only the most relevant result
                    # The search method returns dictionaries with content field
                    recommendation = f"Tip: {kb_results[0]['content'].strip()}"
                    recommendations.append(recommendation)
                    game_state.last_tip_time = current_time
            except Exception as e:
                logger.error(f"Error querying knowledge base: {str(e)}")
    
    return recommendations

def main():
    """
    Simple test function to demonstrate the decision engine.
    """
    print("GameScout Decision Engine Test")
    print("==============================")
    
    # Create game state
    game_state = GameState()
    
    # Simulate some text finding
    test_text = "Entering region: Moonrise Towers\nSome other irrelevant text.\nJournal Updated"
    game_state.update_from_ocr(test_text)
    
    # Generate recommendations
    print("\nContextual Recommendations:")
    for _ in range(3):
        recommendations = get_contextual_tips(game_state)
        for rec in recommendations:
            print(f"- {rec}")
        time.sleep(0.5)  # Simulate time passing
        
if __name__ == "__main__":
    main()
