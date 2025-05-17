#!/usr/bin/env python3
# process_html_to_json.py - Converts raw HTML files to processed JSON documents

import os
import re
import json
import logging
import concurrent.futures
from bs4 import BeautifulSoup
from pathlib import Path
from urllib.parse import urlparse, unquote

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("processing.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
BASE_URL = "https://baldursgate3.wiki.fextralife.com"
INPUT_DIR = "data/wiki_raw"
OUTPUT_DIR = "data/wiki_processed"
MAX_WORKERS = 8  # Paralel işlem sayısı

# Map of HTML files to categories
CATEGORY_PATTERNS = {
    "classes": ["Classes", "Class", "Subclass"],
    "spells": ["Spell", "Cantrip", "Magic"],
    "companions": ["Companion", "Ally", "NPC", "Character"],
    "weapons": ["Weapon", "Sword", "Axe", "Bow", "Dagger", "Mace", "Flail", "Hammer"],
    "quests": ["Quest", "Mission", "Task"],
    "locations": ["Location", "Map", "Region", "Area"],
    "races": ["Race", "Species", "Origin"],
    "feats": ["Feat", "Ability"],
    "items": ["Item", "Equipment", "Gear", "Potion", "Scroll"]
}

# Ensure output directory exists
os.makedirs(OUTPUT_DIR, exist_ok=True)


def clean_text(text):
    """Clean and normalize text content."""
    if not text:
        return ""
    
    # Replace multiple whitespace with a single space
    text = re.sub(r'\s+', ' ', text)
    # Remove HTML entities
    text = re.sub(r'&[a-zA-Z]+;', ' ', text)
    # Remove URLs
    text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)
    
    return text.strip()


def determine_category(file_name, soup):
    """Determine the category of an HTML file based on its name and content."""
    file_name_lower = file_name.lower()
    title = soup.title.string if soup.title else ""
    title_lower = title.lower() if title else ""
    
    # Check file name and title against category patterns
    for category, patterns in CATEGORY_PATTERNS.items():
        for pattern in patterns:
            if pattern.lower() in file_name_lower or pattern.lower() in title_lower:
                return category
                
    # Check meta keywords if exists
    meta_keywords = soup.find("meta", {"name": "keywords"})
    if meta_keywords:
        keywords_content = meta_keywords.get("content", "").lower()
        for category, patterns in CATEGORY_PATTERNS.items():
            for pattern in patterns:
                if pattern.lower() in keywords_content:
                    return category
    
    # Check content for category hints
    content_text = soup.get_text().lower()
    category_scores = {}
    
    for category, patterns in CATEGORY_PATTERNS.items():
        score = 0
        for pattern in patterns:
            pattern_lower = pattern.lower()
            count = content_text.count(pattern_lower)
            score += count
        category_scores[category] = score
    
    # If any category has significant matches, use it
    max_score = max(category_scores.values()) if category_scores else 0
    if max_score > 2:  # Threshold for considering a category match
        for category, score in category_scores.items():
            if score == max_score:
                return category
    
    # Default to "misc" if no category is determined
    return "misc"


def extract_page_content(file_path):
    """Extract the main content from an HTML file and determine its category."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
            
        soup = BeautifulSoup(content, 'html.parser')
        file_name = os.path.basename(file_path)
        
        # Page title
        title = soup.title.string.split('|')[0].strip() if soup.title else Path(file_path).stem
        
        # Extract category
        category = determine_category(file_name, soup)
        
        # Extract URL for the page (if we can reconstruct it)
        page_id = Path(file_path).stem
        url = f"{BASE_URL}/{unquote(page_id)}"
        
        # Main content - focusing on different potential content containers
        content_section = (
            soup.select_one('div#wiki-content-block') or 
            soup.select_one('div#main-content') or
            soup.select_one('div#sub-main') or
            soup.select_one('div#wiki-content') or 
            soup.select_one('div.wiki_content') or 
            soup.select_one('div.container') or
            soup.select_one('div.page-content')
        )
        
        if not content_section:
            logger.warning(f"Could not find content section for {file_path}")
            return None
            
        # Extract meaningful text, ignoring navigation, etc.
        paragraphs = []
        for elem in content_section.select('p, h1, h2, h3, h4, h5, table, ul, ol, dl'):
            text = clean_text(elem.get_text())
            if text and len(text) > 15:  # Skip short snippets
                paragraphs.append(text)
        
        # Skip pages with too little content
        if not paragraphs or sum(len(p) for p in paragraphs) < 100:
            logger.warning(f"Not enough content found for {file_path}")
            return None
        
        # Extract tags
        tags = [category]
        # Add title as a tag (removes special chars)
        tags.append(re.sub(r'[^a-zA-Z0-9\s]', '', title).strip().lower())
        
        # Add additional tags based on content and headers
        headers = [h.get_text().strip().lower() for h in content_section.select('h1, h2, h3')]
        for header in headers:
            header_clean = re.sub(r'[^a-zA-Z0-9\s]', '', header).strip()
            if header_clean and len(header_clean) < 30:
                tags.append(header_clean)
        
        result = {
            "title": title,
            "url": url,
            "content": "\n\n".join(paragraphs),
            "tags": list(set(tag for tag in tags if tag))  # Remove duplicates
        }
        
        return file_path, result, category
    
    except Exception as e:
        logger.error(f"Error processing {file_path}: {str(e)}")
        return None


def process_file(file_path):
    """Process a single HTML file and save its JSON content."""
    try:
        result = extract_page_content(file_path)
        if not result:
            return {"file": file_path, "success": False, "reason": "extraction_failed"}
        
        file_path, entry_data, category = result
        
        # Generate output filename
        page_id = Path(file_path).stem
        output_file = os.path.join(OUTPUT_DIR, f"{category}_{page_id}.json")
        
        # Save processed data
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(entry_data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"Processed: {entry_data['title']} -> {output_file}")
        return {"file": file_path, "success": True, "title": entry_data['title']}
        
    except Exception as e:
        logger.error(f"Error processing {file_path}: {str(e)}")
        return {"file": file_path, "success": False, "reason": str(e)}


def main():
    """Main function to process all HTML files."""
    # Get all HTML files
    html_files = []
    for root, _, files in os.walk(INPUT_DIR):
        for file in files:
            if file.endswith('.html'):
                html_files.append(os.path.join(root, file))
    
    if not html_files:
        logger.error(f"No HTML files found in {INPUT_DIR}")
        return
    
    logger.info(f"Found {len(html_files)} HTML files to process")
    
    # Process files in parallel
    successful = 0
    failed = 0
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_file = {executor.submit(process_file, file): file for file in html_files}
        
        for future in concurrent.futures.as_completed(future_to_file):
            file = future_to_file[future]
            try:
                result = future.result()
                if result and result.get("success"):
                    successful += 1
                else:
                    failed += 1
            except Exception as e:
                logger.error(f"Exception processing {file}: {str(e)}")
                failed += 1
    
    # Final stats
    logger.info(f"Processing completed: {successful} successful, {failed} failed")
    logger.info(f"JSON files saved to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()