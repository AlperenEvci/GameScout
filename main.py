#!/usr/bin/env python3
# gamescout/main.py
"""
GameScout: An AI assistant for gaming that uses screen capture, OCR, and RAG techniques
to provide contextual information and assistance to players.

This is the main entry point for the application, handling initialization,
dependency checking, and the core processing loop.
"""

import time
import queue
import sys
import os
import threading
from config import settings
from src.utils.helpers import get_logger
from src.capture import screen_capture, ocr_processor
from src.rag import decision_engine
from src.rag.assistant import RAGAssistant
from src.ui import hud_display
from scripts.cache_all_regions import cache_all_regions
# Import forum_scraper only when needed to improve startup time
# from data import forum_scraper

# Initialize logger
logger = get_logger(settings.APP_NAME)

# Global RAG Assistant instance
rag_assistant = None

def check_dependencies():
    """
    Verifies all required dependencies are properly configured.
    
    Checks for:
    - Tesseract OCR installation
    - Language data availability
    - Map data cache completeness
    
    Returns:
        bool: True if all dependencies are satisfied, False otherwise
    """
    # Check if Tesseract is properly configured
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
        
    # Check if Turkish language data is available when configured
    if settings.OCR_LANGUAGE == 'tur':
        try:
            import pytesseract
            import tempfile
            from PIL import Image, ImageDraw
            
            # Create a temporary image with Turkish text
            img = Image.new('RGB', (200, 50), color='white')
            d = ImageDraw.Draw(img)
            d.text((10, 10), "Test Türkçe", fill=(0, 0, 0))
            
            # Try OCR with Turkish language
            pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
            result = pytesseract.image_to_string(img, lang='tur')
            logger.info("Turkish language support verified.")
        except Exception as e:
            logger.error(f"Turkish language data may not be installed: {e}")
            print("\n==== Turkish Language Data Not Found ====")
            print("GameScout is configured to use Turkish OCR, but the language data may not be installed.")
            print("To install Turkish language data:")
            print("1. Download the Turkish data from: https://github.com/tesseract-ocr/tessdata/")
            print("2. Place 'tur.traineddata' file in the Tesseract 'tessdata' folder")
            print("   (Usually C:\\Program Files\\Tesseract-OCR\\tessdata\\)")
            print("3. Restart GameScout")
            print("\nAlternatively, you can change OCR_LANGUAGE to 'eng' in config/settings.py")
            print("===========================================\n")
            return False
    
    # Check map data cache and generate missing files
    check_map_data_cache()        
            
    return True

def check_map_data_cache():
    """
    Verifies all region cache files exist and are valid.
    
    Creates or updates any missing or outdated cache files.
    """
    from data.map_data import GAME_REGIONS, get_cached_filename, is_cache_valid
    
    logger.info("Checking map data cache...")
    cache_dir = os.path.join(os.path.dirname(__file__), "cache")
    
    # Ensure cache directory exists
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
        logger.info("Cache directory created.")
    
    # Check for missing or outdated regions
    missing_regions = []
    for region_name in GAME_REGIONS:
        cache_file = get_cached_filename(region_name)
        if not os.path.exists(cache_file) or not is_cache_valid(cache_file):
            missing_regions.append(region_name)
    
    # Generate missing cache files if needed
    if missing_regions:
        num_missing = len(missing_regions)
        logger.info(f"{num_missing} region(s) have missing or outdated cache files.")
        print(f"\nCaching map data for {num_missing} region(s)...")
        
        # Start cache process and inform user
        cached, failed = cache_all_regions()
        
        if failed:
            logger.warning(f"{len(failed)} region(s) could not be cached: {', '.join(failed)}")
            print(f"Warning: {len(failed)} region(s) could not be cached.")
        else:
            logger.info("All map data successfully cached.")
            print("All map data successfully cached!")
    else:
        logger.info("All region cache files are up to date.")

def process_command_input(hud_update_queue):
    """
    Processes user commands from the terminal.
    
    Allows users to interact with the RAG assistant by typing questions
    about the game in the command line.
    
    Args:
        hud_update_queue: Thread-safe queue for passing updates to the HUD
    """
    global rag_assistant
    
    print("\nGameScout RAG Assistant ready! Command line for game-related questions.")
    print("Type 'quit', 'exit', or 'q' to exit.\n")
    
    while True:
        try:
            user_input = input("Question > ")
            
            if user_input.lower() in ["quit", "exit", "q"]:
                print("Shutting down RAG Assistant...")
                break
                
            if not user_input.strip():
                continue
                
            if rag_assistant and rag_assistant.is_initialized:
                # Send query to RAG Assistant
                logger.info(f"Sending user question: {user_input}")
                response = rag_assistant.ask_game_ai(user_input)
                print(f"\nAnswer: {response}\n")
            else:
                print("RAG Assistant has not been initialized yet or failed to initialize.")
                
        except KeyboardInterrupt:
            print("\nShutting down RAG Assistant...")
            break
        except Exception as e:
            logger.error(f"Error processing question: {str(e)}")
            print(f"Error: {str(e)}")

def main_loop():
    """
    Main execution loop for GameScout.
    
    Handles initialization of all components, runs the screen capture and
    processing loop, and manages the HUD and command input threads.
    """
    global rag_assistant
    
    logger.info(f"{settings.APP_NAME} v{settings.VERSION} starting up")
    
    # Check dependencies before starting
    if not check_dependencies():
        logger.error("Critical dependency missing. Exiting.")
        return

    # Create thread-safe queue for communication between main loop and HUD thread
    hud_update_queue = queue.Queue()

    # Initialize components
    game_state = decision_engine.GameState()
    hud = hud_display.HudWindow(hud_update_queue)
    hud.start()  # Start HUD thread

    # Initialize RAG Assistant
    try:
        rag_assistant = RAGAssistant()
        if not rag_assistant.initialize():
            logger.error("RAG Assistant failed to initialize.")
            rag_assistant = None
        else:
            logger.info("RAG Assistant successfully initialized.")
    except Exception as e:
        logger.error(f"Error initializing RAG Assistant: {str(e)}")
        rag_assistant = None

    # Set character class
    game_state.character_class = settings.DEFAULT_CHARACTER_CLASS
    logger.info(f"Character class set to '{game_state.character_class}'.")

    # Start command line query thread
    command_thread = threading.Thread(
        target=process_command_input,
        args=(hud_update_queue,),
        daemon=True
    )
    command_thread.start()

    try:
        # Initial message
        hud_update_queue.put("Starting GameScout...")
        
        # Show startup message with character class and RAG status
        rag_status = "READY" if rag_assistant and rag_assistant.is_initialized else "DISABLED"
        hud_update_queue.put(f"GameScout Ready!\nCharacter Class: {game_state.character_class}\nRegion: Searching...\nRAG Assistant: {rag_status}")
        time.sleep(2)  # Brief pause to display startup message

        # Main processing loop
        while True:
            start_time = time.time()
            logger.debug("--- Main Loop Iteration Start ---")

            # Step 1: Capture the screen
            screenshot = screen_capture.take_screenshot()

            if screenshot:
                # Step 2: Process with OCR
                ocr_text = ocr_processor.extract_text_from_image(screenshot)

                if ocr_text == "TESSERACT_ERROR":
                    logger.error("Tesseract error detected. Stopping application.")
                    hud_update_queue.put("ERROR: Tesseract not found or not properly configured. Exiting.")
                    break  # Exit loop on critical error

                if ocr_text:
                    # Step 3: Update game state
                    game_state.update_from_ocr(ocr_text)
                    logger.debug(f"Current Game State: {game_state}")

                    # Step 4: Generate recommendations (Agent logic)
                    recommendations = decision_engine.generate_recommendations(game_state)

                    # Step 5: Format and send to HUD
                    hud_text = f"Region: {game_state.current_region or 'Unknown'}\n"
                    hud_text += f"Class: {game_state.character_class}\n\n"
                    
                    # Add nearby points of interest
                    if game_state.nearby_points_of_interest:
                        hud_text += "Nearby Points of Interest:\n"
                        for i, poi in enumerate(game_state.nearby_points_of_interest[:3]):
                            hud_text += f"• {poi['name']}\n"
                        hud_text += "\n"
                    
                    # Add region quests
                    if game_state.region_quests:
                        hud_text += "Region Quests:\n"
                        for i, quest in enumerate(game_state.region_quests[:2]):
                            hud_text += f"• {quest['name']}\n"
                        hud_text += "\n"
                    
                    # Add recommendations
                    if recommendations:
                        hud_text += "Recommendations:\n" + "\n".join(f"• {rec}" for rec in recommendations)
                    else:
                        hud_text += "Recommendations: None available at this time."
                        
                    # Show RAG status
                    rag_status = "READY" if rag_assistant and rag_assistant.is_initialized else "DISABLED"
                    hud_text += f"\n\nRAG Assistant: {rag_status}"
                    if rag_assistant and rag_assistant.is_initialized:
                        hud_text += "\nUse command line to ask questions."
                    
                    hud_update_queue.put(hud_text)
                else:
                    logger.debug("No text found in screenshot.")
                    # Optionally send a "Scanning..." message to HUD or preserve last message
                    # hud_update_queue.put(f"Region: {game_state.current_region or 'Unknown'}\n\nScanning...")

            else:
                logger.warning("Failed to capture screenshot this cycle.")
                hud_update_queue.put("Screen capture error...")

            # Calculate elapsed time and sleep accordingly
            end_time = time.time()
            elapsed_time = end_time - start_time
            sleep_time = max(0, settings.SCREENSHOT_INTERVAL_SECONDS - elapsed_time)
            logger.debug(f"Loop iteration took {elapsed_time:.2f}s. Sleeping for {sleep_time:.2f}s.")
            time.sleep(sleep_time)

    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received. Shutting down...")
    except Exception as e:
        logger.critical(f"Unexpected error in main loop: {e}", exc_info=True)
        try:
            # Try to inform user through HUD before exiting
             hud_update_queue.put(f"CRITICAL ERROR: {e}\nExiting.")
             time.sleep(1)  # Give HUD time to potentially display
        except Exception:
            pass  # Ignore errors during shutdown notification
    finally:
        # Clean shutdown
        if rag_assistant:
            logger.info("Shutting down RAG Assistant...")
            rag_assistant.shutdown()
            
        logger.info("Stopping HUD thread...")
        hud.stop()
        hud.join(timeout=2)  # Wait for HUD thread to complete
        logger.info(f"{settings.APP_NAME} completed.")


if __name__ == "__main__":
    main_loop()