# gamescout/main.py

import time
import queue
import sys
from config import settings
from utils.helpers import get_logger
from capture import screen_capture, ocr_processor
from agent import decision_engine
from ui import hud_display
# from data import forum_scraper # Import if/when used in the main loop

logger = get_logger(settings.APP_NAME)

def check_dependencies():
    """Check if all required dependencies are available."""
    # Check if Tesseract is configured
    if not settings.TESSERACT_CMD:
        logger.error("Tesseract OCR not found! GameScout requires Tesseract OCR for text recognition.")
        print("\n==== Tesseract OCR Not Found ====")
        print("GameScout requires Tesseract OCR for text recognition. Please:")
        print("1. Download Tesseract OCR from: https://github.com/UB-Mannheim/tesseract/wiki")
        print("2. Install it (recommended path: C:\\Program Files\\Tesseract-OCR\\)")
        print("3. Restart GameScout")
        print("\nIf Tesseract is already installed in a custom location, update TESSERACT_CMD in config/settings.py")
        print("=================================\n")
        return False
        
    # Check if the Turkish language data is available
    if settings.OCR_LANGUAGE == 'tur':
        try:
            import pytesseract
            import tempfile
            from PIL import Image, ImageDraw
            
            # Create a temporary image with some Turkish text
            img = Image.new('RGB', (200, 50), color='white')
            d = ImageDraw.Draw(img)
            d.text((10, 10), "Test Türkçe", fill=(0, 0, 0))
            
            # Try to OCR it with Turkish language
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
            result = pytesseract.image_to_string(img, lang='tur')
            logger.info("Turkish language support verified.")
        except Exception as e:
            logger.error(f"Turkish language data may not be installed: {e}")
            print("\n==== Turkish Language Data Not Found ====")
            print("GameScout is configured to use Turkish OCR, but the language data may not be installed.")
            print("To install Turkish language data:")
            print("1. Download Turkish data from: https://github.com/tesseract-ocr/tessdata/")
            print("2. Place 'tur.traineddata' file in the Tesseract 'tessdata' folder")
            print("   (Usually C:\\Program Files\\Tesseract-OCR\\tessdata\\)")
            print("3. Restart GameScout")
            print("\nAlternatively, you can change OCR_LANGUAGE back to 'eng' in config/settings.py")
            print("===========================================\n")
            return False
            
    return True

def main_loop():
    """The main execution loop for GameScout."""
    logger.info(f"Starting {settings.APP_NAME} v{settings.VERSION}")
    
    # Check dependencies before starting
    if not check_dependencies():
        logger.error("Critical dependency missing. Exiting.")
        return

    # Thread-safe queue for communication between main loop and HUD thread
    hud_update_queue = queue.Queue()

    # Initialize components
    game_state = decision_engine.GameState()
    hud = hud_display.HudWindow(hud_update_queue)
    hud.start() # Start the HUD thread

    try:
        # Initial message
        hud_update_queue.put("GameScout Initializing...")

        while True:
            start_time = time.time()
            logger.debug("--- Main Loop Iteration Start ---")

            # 1. Capture Screen
            screenshot = screen_capture.take_screenshot()

            if screenshot:
                # 2. Process OCR
                ocr_text = ocr_processor.extract_text_from_image(screenshot)

                if ocr_text == "TESSERACT_ERROR":
                    logger.error("Tesseract error detected. Stopping application.")
                    hud_update_queue.put("ERROR: Tesseract not found or configured. Exiting.")
                    break # Exit loop on critical error

                if ocr_text:
                    # 3. Update Game State
                    game_state.update_from_ocr(ocr_text) # Basic update for now
                    logger.debug(f"Current Game State: {game_state}")

                    # 4. Generate Recommendations (Agent Logic)
                    recommendations = decision_engine.generate_recommendations(game_state)

                    # 5. Format and Send to HUD
                    hud_text = f"Bölge: {game_state.current_region or 'Bilinmiyor'}\n\n"
                    
                    # Yakındaki önemli noktaları ekle
                    if game_state.nearby_points_of_interest:
                        hud_text += "Yakındaki Önemli Noktalar:\n"
                        for i, poi in enumerate(game_state.nearby_points_of_interest[:3]):
                            hud_text += f"• {poi['name']}\n"
                        hud_text += "\n"
                    
                    # Bölgedeki görevleri ekle
                    if game_state.region_quests:
                        hud_text += "Bölge Görevleri:\n"
                        for i, quest in enumerate(game_state.region_quests[:2]):
                            hud_text += f"• {quest['name']}\n"
                        hud_text += "\n"
                    
                    # Önerileri ekle
                    hud_text += "Öneriler:\n" + "\n".join(f"• {rec}" for rec in recommendations)
                    hud_update_queue.put(hud_text)
                else:
                    logger.debug("No text found in screenshot.")
                    # Optionally send a "Scanning..." message to HUD or keep the last one
                    # hud_update_queue.put(f"Region: {game_state.current_region or 'Unknown'}\n\nScanning...")


            else:
                logger.warning("Failed to capture screenshot this cycle.")
                hud_update_queue.put("Error capturing screen...")


            # Calculate time taken and sleep accordingly
            end_time = time.time()
            elapsed_time = end_time - start_time
            sleep_time = max(0, settings.SCREENSHOT_INTERVAL_SECONDS - elapsed_time)
            logger.debug(f"Loop iteration took {elapsed_time:.2f}s. Sleeping for {sleep_time:.2f}s.")
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Shutting down...")
    except Exception as e:
        logger.critical(f"An unexpected error occurred in the main loop: {e}", exc_info=True)
        try:
            # Try to inform the user via HUD before exiting
             hud_update_queue.put(f"CRITICAL ERROR: {e}\nExiting.")
             time.sleep(1) # Give HUD time to potentially display
        except Exception:
            pass # Ignore errors during shutdown notification
    finally:
        logger.info("Stopping HUD thread...")
        hud.stop()
        hud.join(timeout=2) # Wait for HUD thread to finish
        logger.info(f"{settings.APP_NAME} finished.")


if __name__ == "__main__":
    main_loop()