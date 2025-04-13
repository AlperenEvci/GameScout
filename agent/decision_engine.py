# gamescout/agent/decision_engine.py

from config import settings
from utils.helpers import get_logger
import random
import time
from data import map_data  # Yeni map_data modülünü içe aktar
from data.map_data import get_nearby_points_of_interest, get_quests_for_region
from data.web_search import search_game_content, get_region_information
from llm.api_client import LLMAPIClient

logger = get_logger(__name__)

class GameState:
    """Represents the current perceived state of the game."""
    def __init__(self):
        self.current_region: str | None = None
        self.active_quests: list[str] = []
        self.character_class: str = settings.DEFAULT_CHARACTER_CLASS
        self.last_ocr_text: str = ""
        self.detected_keywords: list[str] = []
        self.last_tip_time = 0
        self.recent_tips = []  # Store recently shown tips to avoid repetition
        self.last_location_check_time = 0  # En son konum bilgisi güncellenme zamanı
        self.nearby_points_of_interest = []  # Yakındaki önemli noktalar
        self.region_quests = []  # Bölgedeki görevler
        # Add more state variables as needed (e.g., player health, level, inventory items)

    def update_from_ocr(self, text: str):
        """Updates the game state based on OCR text analysis."""
        self.last_ocr_text = text
        logger.debug("Updating game state from OCR text...")
        
        # Log the length of the OCR text for debugging
        text_length = len(text.strip())
        logger.info(f"Received OCR text of length: {text_length} characters")
        
        if text_length == 0:
            logger.warning("Received empty OCR text - no game state update possible")
            return
            
        # --- Add logic to parse region, quests, etc. from text ---
        # Clear previous detected keywords
        self.detected_keywords = []
        
        # Region detection
        previous_region = self.current_region
        
        if "Entering region:" in text:
            try:
                self.current_region = text.split("Entering region:")[1].split("\n")[0].strip()
                logger.info(f"Detected region change: {self.current_region}")
            except IndexError:
                logger.warning("Could not parse region name after 'Entering region:'.")
        
        # Try alternative text that might be in the game
        elif "location:" in text.lower():
            try:
                self.current_region = text.lower().split("location:")[1].split("\n")[0].strip()
                logger.info(f"Detected location: {self.current_region}")
            except IndexError:
                logger.warning("Could not parse location name.")
        
        # BG3-specific region detection
        bg3_regions = ["Ravaged Beach", "Emerald Grove", "Blighted Village", "Moonrise Towers", 
                       "Underdark", "Grymforge", "Shadowfell", "Gauntlet of Shar", "Githyanki Creche",
                       "Last Light Inn", "Wyrm's Rock", "Shadow-Cursed Lands", "Baldur's Gate"]
        
        for region in bg3_regions:
            if region.lower() in text.lower():
                self.current_region = region
                logger.info(f"Detected BG3 region: {self.current_region}")
                break
        
        # Konum değiştiyse veya uzun süre geçtiyse harita bilgilerini güncelle
        current_time = time.time()
        if (self.current_region != previous_region or 
            current_time - self.last_location_check_time > 300):  # 5 dakikada bir güncelle
            
            self.update_location_data()
            self.last_location_check_time = current_time
        
        # Extract interesting keywords from the text
        interesting_keywords = [
            "quest", "mission", "objective", "enemy", "gold", "weapon", "armor", 
            "character", "health", "magic", "skill", "battle", "dialog", "choice",
            "companion", "camp", "rest", "spell", "attack", "defend", "loot", "chest",
            "trap", "lock", "stealth", "hidden", "secret", "map", "journal", "party",
            "inventory", "level up", "ability", "saving throw", "roll", "dice"
        ]
        
        for keyword in interesting_keywords:
            if keyword in text.lower():
                logger.info(f"Detected keyword '{keyword}' in OCR text")
                self.detected_keywords.append(keyword)
        
        # Add quest detection logic, etc.
        if "new quest" in text.lower() or "quest updated" in text.lower() or "journal updated" in text.lower():
            logger.info("Quest activity detected")
            self.detected_keywords.append("quest_update")
            
    def update_location_data(self):
        """Mevcut bölge için harita verilerini günceller."""
        if not self.current_region:
            logger.debug("No current region detected, skipping location data update")
            return
            
        logger.info(f"Updating location data for region: {self.current_region}")
        
        # Bölge için önemli noktaları getir
        self.nearby_points_of_interest = map_data.get_nearby_points_of_interest(self.current_region)
        logger.debug(f"Found {len(self.nearby_points_of_interest)} points of interest")
        
        # Bölgeye ait görevleri getir
        self.region_quests = map_data.get_quests_for_region(self.current_region)
        logger.debug(f"Found {len(self.region_quests)} quests for this region")

    def add_recent_tip(self, tip):
        """Track recently shown tips to avoid repetition"""
        self.recent_tips.append(tip)
        # Keep only the last 10 tips to avoid growing the list indefinitely
        if len(self.recent_tips) > 10:
            self.recent_tips.pop(0)

    def was_recently_shown(self, tip):
        """Check if a tip was recently shown"""
        return tip in self.recent_tips

    def __str__(self):
        return (f"GameState(Region: {self.current_region}, "
                f"Quests: {len(self.active_quests)}, "
                f"Class: {self.character_class}, "
                f"Keywords: {self.detected_keywords}, "
                f"POIs: {len(self.nearby_points_of_interest)})")


# BG3 tips database organized by category
BG3_TIPS = {
    "general": [
        "Tip: Remember to save your game regularly.",
        "Tip: Use stealth to scout ahead and avoid dangerous encounters.",
        "Tip: Position your party before initiating combat for tactical advantage.",
        "Tip: Check your surroundings for hidden treasures and secret paths.",
        "Tip: Pay attention to environmental hazards you can use in combat.",
        "Tip: Talk to NPCs multiple times as they may have new dialogue options.",
        "Tip: Use height advantage for better attack rolls.",
        "Tip: Characters in shadows have advantage on stealth checks.",
        "Tip: Long rest to recover spell slots and abilities.",
        "Tip: You can use Shove to push enemies into hazards or off ledges.",
        "Tip: Prepare different spells after a long rest to adapt to new challenges.",
        "Tip: Distribute healing potions among all party members.",
        "Tip: Remember that passive skills work automatically - no need to activate them.",
        "Tip: Pick up movable objects by holding left-click on them.",
        "Tip: Some locks can be broken if lockpicking fails.",
    ],
    "combat": [
        "Combat Tip: Use high ground for advantage on attacks.",
        "Combat Tip: Consider using consumables like scrolls and potions during tough fights.",
        "Combat Tip: Target enemy spellcasters first to disrupt their casting.",
        "Combat Tip: Use Disengage to avoid opportunity attacks.",
        "Combat Tip: Check enemy resistances to choose effective damage types.",
        "Combat Tip: Use Help action to give advantage to your allies.",
        "Combat Tip: Flanking an enemy gives advantage on attack rolls.",
        "Combat Tip: Remember you can jump during combat to reposition.",
        "Combat Tip: Use Dodge for defensive positioning.",
        "Combat Tip: AOE spells can hit multiple targets but watch friendly fire.",
    ],
    "exploration": [
        "Exploration Tip: Look for hidden buttons and levers in dungeons.",
        "Exploration Tip: Use your highest Perception character to spot hidden treasures.",
        "Exploration Tip: Check bookshelves and containers for lore and items.",
        "Exploration Tip: Watch for discolored floor tiles which might hide traps.",
        "Exploration Tip: Some walls can be destroyed to reveal hidden areas.",
        "Exploration Tip: Use Jump to reach seemingly inaccessible areas.",
        "Exploration Tip: Take notes about locked doors to return later with keys.",
        "Exploration Tip: Some chests are trapped - use a high Perception character to check.",
        "Exploration Tip: Combine Find Familiar with scouting to safely explore.",
        "Exploration Tip: Look above you - treasures and paths can be up high.",
    ],
    "social": [
        "Social Tip: Your character's background affects some dialogue options.",
        "Social Tip: High Charisma helps with persuasion and intimidation.",
        "Social Tip: Different companions may have special dialogue with certain NPCs.",
        "Social Tip: Certain items can unlock special dialogue options.",
        "Social Tip: Character race and class can affect how NPCs respond to you.",
        "Social Tip: Insight can help determine if an NPC is being truthful.",
        "Social Tip: Some dialogue choices permanently affect your relationship with companions.",
        "Social Tip: Different approaches to quests can lead to different rewards.",
        "Social Tip: Pay attention to approval/disapproval indicators during companion dialogue.",
        "Social Tip: Some decisions might close off certain quest paths permanently.",
    ],
    "class_specific": {
        "Wizard": [
            "Wizard Tip: Look for spell scrolls to add to your spellbook.",
            "Wizard Tip: Remember to prepare different spells after a long rest.",
            "Wizard Tip: Consider using ritual spells to save spell slots.",
            "Wizard Tip: Position yourself away from melee combat.",
            "Wizard Tip: Use your familiar for scouting dangerous areas.",
        ],
        "Fighter": [
            "Fighter Tip: Second Wind can provide emergency healing in combat.",
            "Fighter Tip: Action Surge gives you an extra action - use it wisely.",
            "Fighter Tip: Consider the Sentinel feat for controlling the battlefield.",
            "Fighter Tip: Position yourself to protect squishier party members.",
            "Fighter Tip: You can use heavy weapons effectively due to your proficiency.",
        ],
        "Cleric": [
            "Cleric Tip: Remember to prepare your spells after a long rest.",
            "Cleric Tip: Your Channel Divinity recharges on a short rest.",
            "Cleric Tip: Domain spells are always prepared and don't count against your limit.",
            "Cleric Tip: Balance offensive, defensive, and healing spells.",
            "Cleric Tip: Turn Undead can help control crowds of undead enemies.",
        ],
        "Rogue": [
            "Rogue Tip: Use Cunning Action to disengage after attacking.",
            "Rogue Tip: Stealth before combat to get a surprise attack bonus.",
            "Rogue Tip: Look for opportunities to gain Sneak Attack damage.",
            "Rogue Tip: You excel at disarming traps and picking locks.",
            "Rogue Tip: Use Expertise to become exceptionally good at key skills.",
        ],
        "Ranger": [
            "Ranger Tip: Mark enemies as your Favored Enemy for bonuses.",
            "Ranger Tip: Use your animal companion for tactical advantages.",
            "Ranger Tip: You can track creatures effectively in their Favored Terrain.",
            "Ranger Tip: Hunter's Mark increases your damage output.",
            "Ranger Tip: Consider using ranged weapons to attack from safety.",
        ],
        "Druid": [
            "Druid Tip: Wild Shape can be used for combat or exploration.",
            "Druid Tip: Concentration spells continue working while Wild Shaped.",
            "Druid Tip: You can speak with animals to gain information.",
            "Druid Tip: Consider the terrain when casting area effect spells.",
            "Druid Tip: Prepare different spells when you expect different challenges.",
        ],
        "Paladin": [
            "Paladin Tip: Use Divine Smite on critical hits for maximum damage.",
            "Paladin Tip: Your aura gives nearby allies bonuses to saving throws.",
            "Paladin Tip: Lay on Hands can cure diseases as well as heal.",
            "Paladin Tip: Consider your oath when making moral choices.",
            "Paladin Tip: Your high Charisma helps with social interactions.",
        ],
        "Bard": [
            "Bard Tip: Bardic Inspiration can help allies succeed at critical moments.",
            "Bard Tip: You can learn spells from any class with Magical Secrets.",
            "Bard Tip: Jack of All Trades gives you bonuses to all skill checks.",
            "Bard Tip: Your high Charisma makes you excellent at social encounters.",
            "Bard Tip: Save your reaction for Cutting Words to prevent enemy successes.",
        ],
        "Sorcerer": [
            "Sorcerer Tip: Metamagic allows you to customize your spells.",
            "Sorcerer Tip: Convert sorcery points to spell slots when needed.",
            "Sorcerer Tip: Careful Spell helps avoid hitting allies with AOE spells.",
            "Sorcerer Tip: Twinned Spell effectively doubles single-target spells.",
            "Sorcerer Tip: Your Charisma powers your magic and social skills.",
        ],
        "Warlock": [
            "Warlock Tip: Your spell slots recharge on a short rest.",
            "Warlock Tip: Eldritch Invocations can be changed when leveling up.",
            "Warlock Tip: Hex increases your damage against a specific target.",
            "Warlock Tip: Your Pact Boon defines your playstyle - choose wisely.",
            "Warlock Tip: Eldritch Blast can be enhanced with invocations.",
        ],
        "Monk": [
            "Monk Tip: Spend Ki points wisely - they recharge on a short rest.",
            "Monk Tip: Patient Defense gives disadvantage to attacks against you.",
            "Monk Tip: Flurry of Blows gives extra attacks for Ki points.",
            "Monk Tip: You can deflect missiles and potentially throw them back.",
            "Monk Tip: Stunning Strike can disable powerful enemies temporarily.",
        ],
        "Barbarian": [
            "Barbarian Tip: Rage gives damage resistance and bonus damage.",
            "Barbarian Tip: Reckless Attack grants advantage but makes you vulnerable.",
            "Barbarian Tip: Danger Sense gives advantage on Dexterity saving throws.",
            "Barbarian Tip: Your unarmored defense works best with high Constitution.",
            "Barbarian Tip: Fast Movement helps you reach enemies quickly.",
        ]
    },
    "region_specific": {
        "Ravaged Beach": [
            "Region Tip: Search the shipwreck thoroughly for useful items.",
            "Region Tip: The nautiloid has many secrets to discover.",
            "Region Tip: Help injured survivors for information and rewards.",
            "Region Tip: Beware of brain tadpoles - they cause illithid infection.",
        ],
        "Emerald Grove": [
            "Region Tip: The druids might have important information about the tadpoles.",
            "Region Tip: Help Halsin to gain a powerful ally.",
            "Region Tip: The goblin leaders can be dealt with in multiple ways.",
            "Region Tip: The tieflings' situation offers multiple resolution paths.",
        ],
        "Blighted Village": [
            "Region Tip: Check the windmill for a hidden cellar entrance.",
            "Region Tip: The gnolls are dangerous but have valuable loot.",
            "Region Tip: Look for hidden treasures in abandoned houses.",
            "Region Tip: The Zhentarim have a presence here - choose interactions carefully.",
        ],
        "Underdark": [
            "Region Tip: The mushrooms in the Underdark have various effects.",
            "Region Tip: The myconid colony offers unique quests and allies.",
            "Region Tip: Watch for duergar patrols who might be hostile.",
            "Region Tip: Some passages are hidden and require careful searching.",
        ],
        "Moonrise Towers": [
            "Region Tip: The Absolute's followers are numerous here - approach carefully.",
            "Region Tip: Look for hidden passages in the complex structure.",
            "Region Tip: Different factions here can be played against each other.",
        ],
        "Baldur's Gate": [
            "Region Tip: The city has many districts, each with unique quests.",
            "Region Tip: Various guilds offer faction quests with different rewards.",
            "Region Tip: Street urchins often know valuable information about the city.",
            "Region Tip: Watch for pickpockets in crowded areas.",
        ]
    },
    "keyword_triggered": {
        "quest": [
            "Quest Tip: Check your journal for detailed quest objectives.",
            "Quest Tip: Some quests have time-sensitive components.",
            "Quest Tip: Side quests can provide valuable rewards and experience.",
            "Quest Tip: Different quest solutions may affect your companions differently.",
        ],
        "battle": [
            "Battle Tip: Consider using food buffs before difficult encounters.",
            "Battle Tip: Some enemies have specific weaknesses you can exploit.",
            "Battle Tip: Environmental effects can turn the tide of battle.",
            "Battle Tip: Position your ranged attackers on high ground.",
        ],
        "trap": [
            "Trap Tip: Characters with high perception can spot traps more easily.",
            "Trap Tip: Some traps can be disarmed, others must be avoided.",
            "Trap Tip: Use Find Traps spell if you suspect dangerous areas.",
            "Trap Tip: Send expendable summons ahead if you suspect traps.",
        ],
        "chest": [
            "Chest Tip: Some locked chests can be broken open if lockpicking fails.",
            "Chest Tip: Check for traps before opening valuable-looking chests.",
            "Chest Tip: Some chests require specific keys found elsewhere.",
            "Chest Tip: Not all valuable items are in obvious containers.",
        ],
        "spell": [
            "Spell Tip: Area effect spells can hit allies - position carefully.",
            "Spell Tip: Some spells interact with the environment in unique ways.",
            "Spell Tip: Counter-spell can prevent enemy casters from using powerful spells.",
            "Spell Tip: Concentration spells end if you take significant damage.",
        ]
    }
}


def generate_recommendations(game_state: GameState) -> list[str]:
    """
    Generates recommendations based on the current game state.
    This is the core 'agent' logic.
    """
    logger.debug(f"Generating recommendations for state: {game_state}")
    recommendations = []
    recommendations_generated_this_cycle = False # Bu döngüde öneri üretilip üretilmediğini takip et

    # Zaman kontrolü
    current_time = time.time()
    time_since_last = current_time - game_state.last_tip_time
    logger.debug(f"Time since last recommendation attempt: {time_since_last:.2f}s")

    # 6 dakikalık bekleme süresi geçti mi kontrol et
    if time_since_last >= 360:
        logger.info("Cooldown period passed. Attempting to generate new recommendations.")
        
        # --- LLM-based recommendations (New) ---
        llm_success = False
        llm_client = LLMAPIClient()  # Initialize the LLMAPIClient instance
        try:
            # ... (existing LLM client setup) ...
            if llm_client.is_available():
                logger.info("Requesting recommendations from LLM API...")
                llm_recommendations = llm_client.get_recommendation(game_state)
                
                if llm_recommendations:
                    logger.info(f"Using {len(llm_recommendations)} LLM-generated recommendations")
                    recommendations = [f"AI: {rec}" for rec in llm_recommendations]
                    llm_success = True
                    recommendations_generated_this_cycle = True # Öneri üretildi
                else:
                    logger.warning("LLM API returned no recommendations, falling back to hardcoded tips")
            else:
                logger.debug("LLM API not configured, using hardcoded tips")
        except ImportError:
            logger.warning("LLM module not found, falling back to hardcoded tips")
        except Exception as e:
            logger.error(f"Error getting LLM recommendations: {e}", exc_info=True)
        
        # --- LLM başarısız olduysa veya kullanılmadıysa yerleşik ipuçlarına dön --- 
        if not llm_success:
            logger.debug("Generating hardcoded tips as LLM was not successful or not configured.")
            # --- Konum bazlı öneriler --- 
            if game_state.current_region and game_state.nearby_points_of_interest:
                for poi in game_state.nearby_points_of_interest:
                    poi_tip = f"Nearby Location: {poi['name']} - {poi['description']}"
                    if not game_state.was_recently_shown(poi_tip):
                        recommendations.append(poi_tip)
                        game_state.add_recent_tip(poi_tip)
                        recommendations_generated_this_cycle = True
                        break # Sadece bir tane ekle
            
            # --- Bölge görevleri --- 
            if not recommendations_generated_this_cycle and game_state.region_quests:
                 for quest in game_state.region_quests:
                    quest_tip = f"Region Quest: {quest['name']}"
                    if quest.get('description'):
                        quest_tip += f" - {quest['description']}"
                    if not game_state.was_recently_shown(quest_tip):
                        recommendations.append(quest_tip)
                        game_state.add_recent_tip(quest_tip)
                        recommendations_generated_this_cycle = True
                        break # Sadece bir tane ekle

            # --- Diğer yerleşik ipuçları (Region, Class, Keyword, General) --- 
            # ... (Mevcut yerleşik ipucu mantığınız buraya gelecek) ...
            # Örnek: Genel ipucu ekleme
            if not recommendations_generated_this_cycle:
                tip_categories = ["general", "combat", "exploration", "social"]
                category = random.choice(tip_categories)
                category_tips = BG3_TIPS[category]
                for _ in range(5):
                    tip = random.choice(category_tips)
                    if not game_state.was_recently_shown(tip):
                        recommendations.append(tip)
                        game_state.add_recent_tip(tip)
                        recommendations_generated_this_cycle = True
                        break
                # Eğer 5 denemede yeni ipucu bulunamazsa yine de bir tane ekle
                if not recommendations_generated_this_cycle and category_tips:
                     tip = random.choice(category_tips)
                     if tip not in recommendations:
                         recommendations.append(tip)
                         game_state.add_recent_tip(tip)
                         recommendations_generated_this_cycle = True

        # --- Son öneri zamanını SADECE bu döngüde öneri üretildiyse güncelle --- 
        if recommendations_generated_this_cycle:
            logger.info("Updating last recommendation time.")
            game_state.last_tip_time = current_time
        else:
            logger.info("No new recommendations generated in this cycle.")

    else:
        logger.debug(f"Cooldown active. Skipping recommendation generation. Time remaining: {360 - time_since_last:.2f}s")
        return [] # Bekleme süresindeyken boş liste döndür

    # Önerileri sınırla
    recommendations = recommendations[:3]
    logger.info(f"Generated {len(recommendations)} recommendations this cycle.")
    return recommendations


if __name__ == '__main__':
    # Example usage: Create a state and generate recommendations
    print("Testing Decision Engine...")
    current_state = GameState()
    # Simulate finding some text
    test_text = "Entering region: Moonrise Towers\nSome other irrelevant text.\nJournal Updated"
    current_state.update_from_ocr(test_text)
    current_state.character_class = "Cleric" # Simulate class detection

    print(f"Current State: {current_state}")
    recs = generate_recommendations(current_state)

    print("\nGenerated Recommendations:")
    for rec in recs:
        print(f"- {rec}")
