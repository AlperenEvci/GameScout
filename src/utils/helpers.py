# gamescout/utils/helpers.py
"""
Utility Helper Functions for GameScout

This module provides common utility functions used throughout the application,
including logging configuration, text processing, and other helper functions.
"""

import logging
import re
import os
from typing import Dict, Any, Optional

# --- Logging Configuration ---
def configure_logging(log_file=None, log_level=None) -> None:
    """
    Configure the global logging settings for the application.
    
    Creates log directory if it doesn't exist and sets up the root logger
    with appropriate handlers and formatting.
    
    Args:
        log_file: Path to the log file. If None, defaults to "gamescout.log"
        log_level: Logging level. If None, defaults to "INFO"
    """
    # Default values to avoid circular imports
    if log_file is None:
        log_file = "gamescout.log"
    
    if log_level is None:
        log_level = "INFO"
        
    # Ensure log directory exists
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir)
    
    # Configure the root logger
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()  # Also print logs to console
        ]
    )

# Only configure basic logging initially
logging.basicConfig(level="INFO", format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def get_logger(name: str) -> logging.Logger:
    """
    Creates and returns a logger instance with the specified name.
    
    Args:
        name: The name for the logger, typically __name__ of the calling module
        
    Returns:
        A configured logger instance
    """
    return logging.getLogger(name)

# This will be called from main.py after all imports are complete
def setup_logging():
    """
    Set up proper logging with settings from config.
    This should be called from main.py after all modules are imported.
    """
    try:
        from config import settings
        configure_logging(settings.LOG_FILE, settings.LOG_LEVEL)
    except (ImportError, AttributeError):
        # Fallback if settings import fails
        configure_logging()

# --- Text Processing ---

def clean_text(text: str) -> str:
    """
    Performs basic text cleaning operations.
    
    Removes extra whitespace, normalizes line breaks, and handles
    common OCR-related text issues.
    
    Args:
        text: The input text to clean
        
    Returns:
        The cleaned text
    """
    if not text:
        return ""
        
    # Remove extra whitespace
    cleaned = ' '.join(text.split())
    
    # Optional: Replace common OCR mistakes
    # cleaned = cleaned.replace("0", "O")  # Example: Replace misrecognized zeros
    
    return cleaned

def extract_patterns(text: str, pattern_dict: Dict[str, str]) -> Dict[str, Any]:
    """
    Extract information from text using regex patterns.
    
    Args:
        text: The text to extract information from
        pattern_dict: Dictionary of {key: regex_pattern}
        
    Returns:
        Dictionary of {key: matched_value} for successful matches
    """
    results = {}
    
    for key, pattern in pattern_dict.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            # If the pattern contains a capture group, use that. Otherwise, use the whole match
            value = match.group(1) if match.lastindex else match.group(0)
            results[key] = value.strip()
    
    return results

# --- File Operations ---

def ensure_directory(directory_path: str) -> bool:
    """
    Ensures a directory exists, creating it if necessary.
    
    Args:
        directory_path: Path to the directory to create
        
    Returns:
        True if the directory exists or was created successfully, False otherwise
    """
    try:
        if not os.path.exists(directory_path):
            os.makedirs(directory_path)
            return True
        return True
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Error creating directory {directory_path}: {e}")
        return False

def safe_file_read(file_path: str, default: Optional[str] = None) -> Optional[str]:
    """
    Safely reads a file with error handling.
    
    Args:
        file_path: Path to the file to read
        default: Default value to return if file cannot be read
        
    Returns:
        File contents as string or default value if file cannot be read
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read()
    except Exception as e:
        logger = get_logger(__name__)
        logger.error(f"Error reading file {file_path}: {e}")
        return default

# Add more utility functions as the project grows