# gamescout/capture/screen_capture.py

import pyautogui
import pygetwindow as gw
from PIL import Image
from config import settings
from utils.helpers import get_logger

logger = get_logger(__name__)

def get_window_region(window_title):
    """
    Get the region (left, top, width, height) of a window by its exact title.
    
    Args:
        window_title: The exact title of the window to capture
        
    Returns:
        A tuple of (left, top, width, height) or None if the window is not found
    """
    try:
        # Get all windows and find the one with the exact title
        all_windows = gw.getAllWindows()
        
        # Find the window with the exact title match
        matching_window = None
        for window in all_windows:
            if window.title == window_title:
                matching_window = window
                break
                
        if not matching_window:
            logger.warning(f"No window found with exact title '{window_title}'")
            return None
            
        # Get the window position and size
        left, top = matching_window.left, matching_window.top
        width, height = matching_window.width, matching_window.height
        
        logger.debug(f"Found window '{matching_window.title}' at position ({left}, {top}) with size ({width}, {height})")
        return (left, top, width, height)
        
    except Exception as e:
        logger.error(f"Error getting window region: {e}", exc_info=True)
        return None

def take_screenshot() -> Image.Image | None:
    """
    Takes a screenshot of the specified region or the primary monitor.

    Returns:
        A PIL Image object of the screenshot, or None if an error occurs.
    """
    try:
        # Check if a specific window should be captured
        if settings.CAPTURE_WINDOW_TITLE:
            logger.info(f"Attempting to capture window: '{settings.CAPTURE_WINDOW_TITLE}'")
            # Get the region of the specified window
            region = get_window_region(settings.CAPTURE_WINDOW_TITLE)
            
            # If the window was found, use its region for the screenshot
            if region:
                screenshot = pyautogui.screenshot(region=region)
                logger.debug(f"Screenshot taken of window '{settings.CAPTURE_WINDOW_TITLE}'")
                return screenshot
            else:
                # Fall back to the configured region if the window isn't found
                logger.warning(f"Window '{settings.CAPTURE_WINDOW_TITLE}' not found. Using configured region instead.")
        
        # Use the configured region (or entire screen if None)
        screenshot = pyautogui.screenshot(region=settings.CAPTURE_REGION)
        logger.debug("Screenshot taken successfully.")
        return screenshot
    except Exception as e:
        logger.error(f"Error taking screenshot: {e}", exc_info=True)
        return None

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