# gamescout/utils/helpers.py

import logging
from config import settings # Corrected import path

# --- Logging Setup ---
logging.basicConfig(
    level=settings.LOG_LEVEL,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(settings.LOG_FILE),
        logging.StreamHandler() # Also print logs to console
    ]
)

def get_logger(name):
    """Creates and returns a logger instance."""
    return logging.getLogger(name)

# --- Other Potential Helpers ---

def clean_text(text):
    """Basic text cleaning function."""
    if not text:
        return ""
    # Remove extra whitespace, newlines, etc.
    cleaned = ' '.join(text.split())
    return cleaned

# Add more utility functions as the project grows
# e.g., file operations, data validation, etc.