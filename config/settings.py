# gamescout/config/settings.py

import os
import shutil

# --- General Settings ---
APP_NAME = "GameScout"
VERSION = "0.1.0"

# --- Screen Capture & OCR ---
SCREENSHOT_INTERVAL_SECONDS = 5  # How often to capture the screen

# Set the path to Tesseract - automatically tries to find it if possible
def find_tesseract_path():
    # Default paths to check
    default_paths = [
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe',
        # Add custom paths here if needed
    ]
    
    # First check the default installation paths
    for path in default_paths:
        if os.path.isfile(path):
            return path
    
    # Then try to find it in PATH
    tesseract_path = shutil.which('tesseract')
    if tesseract_path:
        return tesseract_path
        
    return None

TESSERACT_CMD = find_tesseract_path()
OCR_LANGUAGE = 'eng'  # Changed from 'eng' to 'tur' for Turkish language support
# Optional: Define specific screen region for capture (left, top, width, height)
CAPTURE_REGION = None # Set to None to capture the primary monitor

# Set this to the title of the window you want to capture
# If set, GameScout will try to capture this window instead of using CAPTURE_REGION
CAPTURE_WINDOW_TITLE = "Baldur's Gate 3 (1920x1080) - (Vulkan) - (6 + 6 WT)"  # Exact window title for capture

# --- Data Scraping ---
# Target forum URLs (add more as needed)
FORUM_URLS = {

    "fextralife_bg3": "https://baldursgate3.wiki.fextralife.com/Baldur's+Gate+3+Wiki",
    # Add more specific pages if needed
}
SCRAPER_USER_AGENT = f"{APP_NAME}/{VERSION} (GameScout Application)" # Be polite to websites

# --- Agent Settings ---
# Placeholder for character class or other agent logic triggers
DEFAULT_CHARACTER_CLASS = "Wizard"

# --- UI Settings ---
HUD_UPDATE_INTERVAL_MS = 1000 # How often the HUD refreshes
HUD_WIDTH = 400  # Increased from 300 for better visibility
HUD_HEIGHT = 300  # Increased from 200 for better visibility
HUD_TRANSPARENCY = 0.9  # Increased from 0.7 for better visibility (less transparent)

# --- Logging ---
LOG_FILE = "gamescout.log"
LOG_LEVEL = "INFO" # DEBUG, INFO, WARNING, ERROR, CRITICAL

# --- Utility Functions ---
def get_tesseract_path():
    """Returns the configured Tesseract path or None."""
    return TESSERACT_CMD

# Add more configuration loading logic if needed (e.g., from environment variables or files)