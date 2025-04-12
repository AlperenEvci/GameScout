# gamescout/capture/ocr_processor.py

import pytesseract
from PIL import Image
from config import settings
from utils.helpers import get_logger, clean_text

logger = get_logger(__name__)

# Configure Tesseract path if set in settings
if settings.TESSERACT_CMD:
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD
    logger.info(f"Using Tesseract path: {settings.TESSERACT_CMD}")
else:
    logger.warning("Tesseract path is not set!")

def extract_text_from_image(image: Image.Image) -> str:
    """
    Extracts text from a PIL Image object using Tesseract OCR.

    Args:
        image: The PIL Image object to process.

    Returns:
        The extracted text as a string, or an empty string if an error occurs or no text is found.
    """
    if image is None:
        logger.warning("Received None image for OCR processing.")
        return ""
    try:
        # Log image details for debugging
        logger.info(f"Processing image for OCR: Size={image.size}, Mode={image.mode}")
        
        # Preprocessing steps can be added here (e.g., grayscale, thresholding)
        # image = image.convert('L') # Example: Convert to grayscale
        # custom_config = r'--oem 3 --psm 6' # Example Tesseract config
        
        # Save a copy of the current image for debugging
        debug_path = "ocr_debug_image.png"
        image.save(debug_path)
        logger.info(f"Saved debug image to {debug_path}")
        
        text = pytesseract.image_to_string(image, lang=settings.OCR_LANGUAGE) #, config=custom_config)
        cleaned = clean_text(text)
        
        # Log full text for debugging
        logger.info(f"OCR extracted full text: {cleaned}")
        
        return cleaned
    except pytesseract.TesseractNotFoundError:
        logger.error("Tesseract Error: The Tesseract executable was not found or not configured correctly.")
        logger.error(f"Please ensure Tesseract is installed and the path '{settings.TESSERACT_CMD}' is correct (if set).")
        # Consider raising a specific exception or returning a special value
        return "TESSERACT_ERROR"
    except Exception as e:
        logger.error(f"Error during OCR processing: {e}", exc_info=True)
        return ""

if __name__ == '__main__':
    # Example usage: Load a test image and extract text
    print("Testing OCR processor...")
    try:
        # Create a dummy image or load one for testing
        # img = Image.new('RGB', (600, 150), color = 'white')
        # d = ImageDraw.Draw(img)
        # d.text((10,10), "Hello World from OCR Test", fill=(0,0,0))
        # img.save("test_ocr_input.png")

        test_image_path = "test_screenshot.png" # Assumes screen_capture created this
        img = Image.open(test_image_path)
        extracted = extract_text_from_image(img)
        print(f"Extracted text from '{test_image_path}':\n---\n{extracted}\n---")
    except FileNotFoundError:
        print(f"Error: Test image '{test_image_path}' not found. Run screen_capture.py first or provide a valid image.")
    except Exception as e:
        print(f"An error occurred during OCR test: {e}")
