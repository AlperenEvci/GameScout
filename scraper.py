#!/usr/bin/env python3
# scraper.py - Fetches content from Baldur's Gate 3 Wiki and saves it as structured data - Parallel version

import os
import re
import json
import time
import random
import logging
import requests
import concurrent.futures
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("scraping.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Constants
BASE_URL = "https://baldursgate3.wiki.fextralife.com"
CATEGORIES = {
    "classes": "/Classes",
    "spells": "/Spells",
    "companions": "/Companions",
    "weapons": "/Weapons",
    "quests": "/Quests",
    "locations": "/Maps",
    "races": "/Races",
    "feats": "/Feats",
    "items": "/Equipment"
}

OUTPUT_RAW_DIR = "data/wiki_raw"
OUTPUT_PROCESSED_DIR = "data/wiki_processed"

# Parallelization settings
MAX_WORKERS = 4  # Kaç paralel işçi çalıştırılacağı
MAX_CONNECTIONS_PER_HOST = 3  # Her host için maksimum bağlantı sayısı
REQUEST_DELAY_MIN = 0.5  # Paralel işlemde minimum gecikme süresi
REQUEST_DELAY_MAX = 1.5  # Paralel işlemde maksimum gecikme süresi

# Ensure output directories exist
os.makedirs(OUTPUT_RAW_DIR, exist_ok=True)
os.makedirs(OUTPUT_PROCESSED_DIR, exist_ok=True)

# Create a session object for connection pooling
session = requests.Session()
adapter = requests.adapters.HTTPAdapter(pool_connections=MAX_CONNECTIONS_PER_HOST, 
                                       pool_maxsize=MAX_CONNECTIONS_PER_HOST, 
                                       max_retries=3)
session.mount('http://', adapter)
session.mount('https://', adapter)


def get_soup(url, retries=3, delay=2):
    """Fetch a URL and return a BeautifulSoup object."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept-Language': 'en-US,en;q=0.9',
    }
    
    for attempt in range(retries):
        try:
            logger.debug(f"Fetching URL: {url}")  # Debug level to reduce log clutter in parallel mode
            response = session.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            
            # Save the raw HTML
            page_id = url.split('/')[-1]
            if not page_id:
                page_id = "index"
            
            raw_file_path = os.path.join(OUTPUT_RAW_DIR, f"{page_id}.html")
            with open(raw_file_path, 'w', encoding='utf-8') as f:
                f.write(response.text)
            
            return BeautifulSoup(response.text, 'html.parser')
        
        except requests.exceptions.RequestException as e:
            wait_time = delay * (attempt + 1) + random.uniform(0, 2)
            logger.error(f"Error fetching {url}: {e}. Retrying in {wait_time:.2f}s. Attempt {attempt+1}/{retries}")
            time.sleep(wait_time)
    
    logger.error(f"Failed to retrieve {url} after {retries} attempts")
    return None


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


def extract_page_content(soup, url, category):
    """Extract the main content from a wiki page."""
    if not soup:
        return None
    
    try:
        # Page title
        title = soup.title.string.split('|')[0].strip() if soup.title else os.path.basename(url)
        
        # Main content - focusing on different potential content containers
        content_section = soup.select_one('div#wiki-content') or soup.select_one('div.wiki_content') or soup.select_one('div.container')
        
        if not content_section:
            logger.warning(f"Could not find content section for {url}")
            return None
            
        # Extract meaningful text, ignoring navigation, etc.
        paragraphs = []
        for elem in content_section.select('p, h1, h2, h3, h4, h5, table, ul, ol, dl'):
            text = clean_text(elem.get_text())
            if text and len(text) > 15:  # Skip short snippets
                paragraphs.append(text)
        
        # Skip pages with too little content
        if not paragraphs or sum(len(p) for p in paragraphs) < 100:
            logger.warning(f"Not enough content found for {url}")
            return None
        
        # Extract tags (e.g., class name, spell school, weapon type)
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
        
        return result
    
    except Exception as e:
        logger.error(f"Error extracting content from {url}: {str(e)}")
        return None


def get_links_from_category(soup, base_url):
    """Extract links to individual entries from a category page."""
    links = []
    
    if not soup:
        return links
        
    # Look for tables and lists containing links to entries
    for table in soup.select('table.wiki_table'):
        for a in table.select('a'):
            href = a.get('href')
            if href and not href.startswith('#') and not href.startswith('http'):
                full_url = urljoin(base_url, href)
                links.append(full_url)
    
    # Also check lists
    for list_item in soup.select('ul li, ol li'):
        for a in list_item.select('a'):
            href = a.get('href')
            if href and not href.startswith('#') and not href.startswith('http'):
                full_url = urljoin(base_url, href)
                links.append(full_url)
                
    # Also check div.wiki-content div links
    for div in soup.select('div.wiki_content, div.well'):
        for a in div.select('a'):
            href = a.get('href')
            if href and not href.startswith('#') and not href.startswith('http'):
                full_url = urljoin(base_url, href)
                links.append(full_url)
    
    # Remove duplicates while preserving order
    seen = set()
    unique_links = []
    for link in links:
        if link not in seen:
            seen.add(link)
            unique_links.append(link)
            
    return unique_links


def process_entry(args):
    """Process a single wiki entry (for parallel execution)."""
    i, link, total, category_name = args
    
    try:
        # Skip external links
        if urlparse(link).netloc and urlparse(link).netloc != urlparse(BASE_URL).netloc:
            return {"success": False, "reason": "external_link"}
            
        # Generate a simple filename based on the URL path
        page_id = link.split('/')[-1]
        if not page_id:
            return {"success": False, "reason": "invalid_page_id"}
            
        output_file = os.path.join(OUTPUT_PROCESSED_DIR, f"{category_name}_{page_id}.json")
        
        # Skip if already processed
        if os.path.exists(output_file):
            logger.debug(f"[{i+1}/{total}] Skipping already processed: {page_id}")
            return {"success": True, "skipped": True, "title": page_id}
            
        # Add a random delay to be nice to the server - shorter than sequential version
        time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))
        
        # Get the page content
        page_soup = get_soup(link)
        if not page_soup:
            return {"success": False, "reason": "fetch_failed"}
            
        # Extract content
        entry_data = extract_page_content(page_soup, link, category_name)
        
        if not entry_data:
            logger.warning(f"Could not extract content from {link}")
            return {"success": False, "reason": "extract_failed"}
            
        # Save processed data
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(entry_data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"[{i+1}/{total}] Processed: {entry_data['title']}")
        return {"success": True, "skipped": False, "title": entry_data['title']}
        
    except Exception as e:
        logger.error(f"Error processing {link}: {str(e)}")
        return {"success": False, "reason": str(e)}


def process_category(category_name, category_path):
    """Process a wiki category and all its entries using parallel processing."""
    category_url = BASE_URL + category_path
    logger.info(f"Processing category: {category_name} from {category_url}")
    
    # Get the category page
    category_soup = get_soup(category_url)
    if not category_soup:
        logger.error(f"Failed to retrieve category page: {category_url}")
        return 0
    
    # Get links to individual entries
    entry_links = get_links_from_category(category_soup, BASE_URL)
    logger.info(f"Found {len(entry_links)} links in category {category_name}")
    
    # Skip if no links found
    if not entry_links:
        return 0
        
    # Prepare arguments for parallel processing
    args_list = [(i, link, len(entry_links), category_name) for i, link in enumerate(entry_links)]
    
    successful_count = 0
    skipped_count = 0
    
    # Process entries in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {executor.submit(process_entry, args): args[1] for args in args_list}
        
        for future in concurrent.futures.as_completed(future_to_url):
            url = future_to_url[future]
            try:
                result = future.result()
                if result and result.get("success", False):
                    if result.get("skipped", False):
                        skipped_count += 1
                    else:
                        successful_count += 1
            except Exception as e:
                logger.error(f"Exception processing {url}: {str(e)}")
    
    logger.info(f"Category {category_name} completed - Processed: {successful_count}, Skipped: {skipped_count}, Total: {len(entry_links)}")
    return successful_count


def main():
    """Main function to scrape all categories."""
    start_time = time.time()
    total_processed = 0
    
    logger.info(f"Starting BG3 wiki scraper (Parallel version with {MAX_WORKERS} workers)")
    
    for category_name, category_path in CATEGORIES.items():
        category_start = time.time()
        processed = process_category(category_name, category_path)
        category_duration = time.time() - category_start
        
        logger.info(f"Completed category {category_name}: {processed} entries in {category_duration:.2f}s")
        total_processed += processed
        
        # Be nice to the server between categories
        time.sleep(random.uniform(2, 4))  # Slightly shorter delay between categories
    
    total_duration = time.time() - start_time
    logger.info(f"Scraping completed. Total processed: {total_processed} entries in {total_duration:.2f}s")


if __name__ == "__main__":
    main()