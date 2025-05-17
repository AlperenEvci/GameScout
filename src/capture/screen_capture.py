# gamescout/capture/screen_capture.py
"""
Screen Capture Module for GameScout

This module is responsible for capturing screenshots of the game window or screen
using PyAutoGUI and PyGetWindow libraries. It can target specific windows by title
or capture predefined screen regions.
"""

import pyautogui
import pygetwindow as gw
from PIL import Image
from typing import Tuple, Optional
from config import settings
from src.utils.helpers import get_logger

# Initialize logger for this module
logger = get_logger(__name__)

# Type alias for screen regions
Region = Tuple[int, int, int, int]  # left, top, width, height

def get_window_region(window_title: str) -> Optional[Region]:
    """
    Get the region coordinates of a window by its exact title.
    
    Args:
        window_title: The exact title of the window to capture
        
    Returns:
        A tuple of (left, top, width, height) or None if window not found
    """
    try:
        # Get all windows and find the one with the exact title
        all_windows = gw.getAllWindows()
        
        # Find window with exact title match
        matching_window = next(
            (window for window in all_windows if window.title == window_title), 
            None
        )
                
        if not matching_window:
            logger.warning(f"No window found with exact title '{window_title}'")
            return None
            
        # Extract window position and size
        left, top = matching_window.left, matching_window.top
        width, height = matching_window.width, matching_window.height
        
        logger.debug(f"Found window '{matching_window.title}' at position ({left}, {top}) with size ({width}, {height})")
        return (left, top, width, height)
        
    except Exception as e:
        logger.error(f"Error getting window region: {e}", exc_info=True)
        return None

def take_screenshot() -> Optional[Image.Image]:
    """
    Takes a screenshot of the specified window or region.
    
    First attempts to capture a specific window if CAPTURE_WINDOW_TITLE is set.
    Falls back to the configured region or entire screen if window capture fails.

    Returns:
        A PIL Image object containing the screenshot, or None if capture fails
    """
    try:
        # If window capture is configured, try to capture the specific window
        if settings.CAPTURE_WINDOW_TITLE:
            logger.info(f"Attempting to capture window: '{settings.CAPTURE_WINDOW_TITLE}'")
            region = get_window_region(settings.CAPTURE_WINDOW_TITLE)
            
            if region:
                screenshot = pyautogui.screenshot(region=region)
                logger.debug(f"Screenshot taken of window '{settings.CAPTURE_WINDOW_TITLE}'")
                return screenshot
            else:
                logger.warning(
                    f"Window '{settings.CAPTURE_WINDOW_TITLE}' not found. "
                    "Falling back to configured region or full screen capture."
                )
        
        # Take screenshot of configured region (or entire screen if None)
        screenshot = pyautogui.screenshot(region=settings.CAPTURE_REGION)
        
        if settings.CAPTURE_REGION:
            logger.debug(f"Screenshot taken of configured region {settings.CAPTURE_REGION}")
        else:
            logger.debug("Screenshot taken of full screen")
            
        return screenshot
    
    except pyautogui.PyAutoGUIException as e:
        logger.error(f"PyAutoGUI error during screenshot: {e}")
        return None
    except Exception as e:
        logger.error(f"Error taking screenshot: {e}", exc_info=True)
        return None

def save_debug_screenshot(filename: str = "debug_screenshot.png") -> bool:
    """
    Takes a screenshot and saves it to disk for debugging purposes.
    
    Args:
        filename: Name of the file to save the screenshot as
        
    Returns:
        True if successful, False otherwise
    """
    try:
        screenshot = take_screenshot()
        if screenshot:
            screenshot.save(filename)
            logger.info(f"Debug screenshot saved to '{filename}'")
            return True
        return False
    except Exception as e:
        logger.error(f"Failed to save debug screenshot: {e}")
        return False

if __name__ == '__main__':
    # Example usage: Take a screenshot and save it
    print("Taking a test screenshot...")
    img = take_screenshot()
    if img:
        try:
            img.save("test_screenshot.png")
            print("Test screenshot saved as test_screenshot.png")
        except Exception as e:
            print(f"Error saving test screenshot: {e}")
    else:
        print("Failed to take test screenshot.")