# gamescout/capture/ocr_processor.py
"""
OCR Processing Module for GameScout

This module handles text extraction from screenshots using the Tesseract OCR engine.
It processes images captured from screen_capture.py and extracts text content that
can be used to determine the game state.
"""

import pytesseract
from PIL import Image
from typing import Optional
from config import settings
from src.utils.helpers import get_logger, clean_text

# Initialize logger
logger = get_logger(__name__)

# Configure Tesseract path if provided
if settings.TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
    logger.info(f"Using Tesseract path: {settings.TESSERACT_CMD}")
else:
    logger.warning("Tesseract path not configured!")

def preprocess_image(image: Image.Image) -> Image.Image:
    """
    Apply preprocessing steps to improve OCR accuracy.
    
    This can include operations like converting to grayscale,
    adjusting contrast, applying thresholds, etc.
    
    Args:
        image: The PIL Image to preprocess
        
    Returns:
        The preprocessed PIL Image
    """
    # Currently using minimal processing, but can be expanded as needed
    # Consider image processing techniques to improve OCR quality:
    # - Convert to grayscale
    # - Resize for better recognition
    # - Apply thresholding or other filters
    
    # Example preprocessing (uncomment to use):
    # image = image.convert('L')  # Convert to grayscale
    # image = image.resize((image.width * 2, image.height * 2))  # Resize for better recognition
    
    return image

def extract_text_from_image(image: Optional[Image.Image]) -> str:
    """
    Extract text from a PIL Image object using Tesseract OCR.

    Args:
        image: The PIL Image object to process
        
    Returns:
        Extracted text as a string, or an empty string if an error occurs or no text is found.
        Returns "TESSERACT_ERROR" if Tesseract is not properly configured.
    """
    if image is None:
        logger.warning("Received None image for OCR processing.")
        return ""
    
    try:
        # Log image details for debugging
        logger.info(f"Processing image for OCR: Size={image.size}, Mode={image.mode}")
        
        # Apply preprocessing (optional)
        processed_image = preprocess_image(image)
        
        # Save a copy of the current image for debugging
        debug_path = "ocr_debug_image.png"
        processed_image.save(debug_path)
        logger.info(f"Debug image saved to {debug_path}")
        
        # Optional Tesseract configuration
        # custom_config = r'--oem 3 --psm 6'  # Example: Page segmentation mode 6 (block of text)
        
        # Extract text using Tesseract
        text = pytesseract.image_to_string(
            processed_image, 
            lang=settings.OCR_LANGUAGE
            # config=custom_config  # Uncomment to use custom configuration
        )
        
        # Clean the extracted text
        cleaned = clean_text(text)
        
        # Log full text for debugging
        if cleaned:
            logger.info(f"OCR extracted text (first 100 chars): {cleaned[:100]}...")
            logger.debug(f"Full OCR text: {cleaned}")
        else:
            logger.info("No text extracted from image")
            
        return cleaned
        
    except pytesseract.TesseractNotFoundError:
        logger.error("Tesseract Error: Tesseract executable not found or not properly configured.")
        logger.error(f"Please ensure Tesseract is installed and the path '{settings.TESSERACT_CMD}' (if set) is correct.")
        # Return a special value to indicate this specific error
        return "TESSERACT_ERROR"
    except Exception as e:
        logger.error(f"Error during OCR processing: {e}", exc_info=True)
        return ""

if __name__ == '__main__':
    # Example usage: Load a test image and extract text
    print("Testing OCR processor...")
    try:
        # Create a dummy test image with text
        # from PIL import ImageDraw
        # img = Image.new('RGB', (600, 150), color='white')
        # d = ImageDraw.Draw(img)
        # d.text((10,10), "Hello World from OCR Test", fill=(0,0,0))
        # img.save("test_ocr_input.png")

        test_image_path = "test_screenshot.png"  # Assumes screen_capture.py created this
        img = Image.open(test_image_path)
        extracted = extract_text_from_image(img)
        print(f"Text extracted from '{test_image_path}':\n---\n{extracted}\n---")
    except FileNotFoundError:
        print(f"Error: Test image '{test_image_path}' not found. Run screen_capture.py first or provide a valid image.")
    except Exception as e:
        print(f"An error occurred during OCR testing: {e}")
