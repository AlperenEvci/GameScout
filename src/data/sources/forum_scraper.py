# gamescout/data/forum_scraper.py

import requests
from bs4 import BeautifulSoup
from config import settings
from utils.helpers import get_logger
import re
from typing import List, Dict, Optional, Union, Tuple

logger = get_logger(__name__)

def fetch_url_content(url: str) -> str | None:
    """Fetches the HTML content of a given URL."""
    headers = {'User-Agent': settings.SCRAPER_USER_AGENT}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        logger.debug(f"Successfully fetched content from {url}")
        return response.text
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching URL {url}: {e}")
        return None

def extract_wiki_content(url: str) -> Dict[str, Union[str, List[str], Dict[str, str]]]:
    """
    Extracts structured content from a wiki page URL.
    
    Returns a dictionary with:
    - title: The page title
    - summary: The main content summary
    - sections: List of sections and their content
    - infobox: Dictionary of structured data from infoboxes (if available)
    - links: List of relevant links found in the page
    """
    content = fetch_url_content(url)
    if not content:
        logger.error(f"Failed to fetch content from wiki page: {url}")
        return {
            "title": "",
            "summary": "",
            "sections": [],
            "infobox": {},
            "links": []
        }
    
    soup = BeautifulSoup(content, 'html.parser')
    
    # Extract title
    title = ""
    title_tag = soup.find('title')
    if title_tag:
        title = title_tag.text.strip()
    else:
        # Try to find main heading if title tag not found
        h1 = soup.find('h1')
        if h1:
            title = h1.text.strip()
    
    # Extract summary (typically the first paragraph)
    summary = ""
    main_content = soup.find(id='mw-content-text') or soup.find(id='bodyContent') or soup.find('main') or soup
    first_para = main_content.find('p')
    if first_para:
        summary = first_para.text.strip()
    
    # Extract sections
    sections = []
    headings = main_content.find_all(['h2', 'h3'])
    for heading in headings:
        section_title = heading.text.strip()
        # Remove edit links or other typical wiki formatting
        section_title = re.sub(r'\[edit\]|\[.*?\]', '', section_title).strip()
        
        # Get content until next heading
        section_content = []
        current = heading.next_sibling
        while current and not current.name in ['h2', 'h3']:
            if current.name == 'p' and current.text.strip():
                section_content.append(current.text.strip())
            current = current.next_sibling
        
        if section_title and section_content:
            sections.append({
                "title": section_title,
                "content": "\n".join(section_content)
            })
    
    # Extract infobox data (typically in tables with class 'infobox' or similar)
    infobox = {}
    infobox_table = soup.find('table', class_=lambda x: x and ('infobox' in x or 'wikitable' in x))
    if infobox_table:
        rows = infobox_table.find_all('tr')
        for row in rows:
            header = row.find(['th', 'td', 'div', 'span'], class_='infobox-label')
            data = row.find(['td', 'div', 'span'], class_='infobox-data')
            
            if header and data:
                key = header.text.strip()
                value = data.text.strip()
                infobox[key] = value
    
    # Extract relevant links
    links = []
    for a in main_content.find_all('a', href=True):
        link_text = a.text.strip()
        href = a['href']
        
        # Only include internal wiki links or external links that seem relevant
        if link_text and (href.startswith('/') or href.startswith('http')):
            # Convert relative URLs to absolute
            if href.startswith('/'):
                # Extract base URL from the original URL
                base_url = '/'.join(url.split('/')[:3])  # http://domain.com
                href = base_url + href
            
            links.append({
                "text": link_text,
                "url": href
            })
    
    # Limit links to top 10 to avoid too much data
    links = links[:10]
    
    return {
        "title": title,
        "summary": summary,
        "sections": sections,
        "infobox": infobox,
        "links": links
    }

def search_forums(query: str) -> dict[str, list[str]]:
    """
    Searches configured forums for a given query.
    NOTE: This is a placeholder. Actual implementation requires specific
          parsing logic for each target website (Reddit, Fextralife, etc.)
          which can be complex and fragile due to website structure changes.
          Consider using official APIs if available.
    """
    logger.info(f"Searching forums for query: '{query}'")
    results = {}

    # Example for a generic search (replace with site-specific logic)
    for site_name, base_url in settings.FORUM_URLS.items():
        logger.debug(f"Searching {site_name}...")
        # This is highly simplified. Real scraping needs specific URL construction
        # and parsing based on each site's structure.
        # search_url = f"{base_url}/search?q={query}" # Example search URL pattern
        # content = fetch_url_content(search_url)
        # if content:
        #     soup = BeautifulSoup(content, 'html.parser')
        #     # --- Add specific parsing logic here ---
        #     # Find relevant links, titles, snippets based on HTML tags/classes
        #     found_items = ["Placeholder result 1", "Placeholder result 2"] # Replace with actual parsed data
        #     results[site_name] = found_items
        #     logger.debug(f"Found {len(found_items)} potential results on {site_name}")
        # else:
        #     results[site_name] = []
        results[site_name] = [f"Scraping logic for {site_name} not implemented yet."] # Placeholder

    return results

def extract_wiki_pages(urls: List[str]) -> Dict[str, Dict]:
    """
    Extracts content from a list of wiki page URLs.
    
    Args:
        urls: List of wiki page URLs to extract content from
        
    Returns:
        Dictionary mapping each URL to its extracted content
    """
    logger.info(f"Extracting content from {len(urls)} wiki pages")
    results = {}
    
    for url in urls:
        logger.debug(f"Processing wiki page: {url}")
        page_content = extract_wiki_content(url)
        results[url] = page_content
        logger.debug(f"Extracted {len(page_content['sections'])} sections and {len(page_content['infobox'])} infobox items")
    
    return results


if __name__ == '__main__':
    # Example usage: Extract content from a wiki page
    test_wiki_url = "https://baldursgate3.wiki.fextralife.com/Cleric"
    print(f"Running wiki extraction test for URL: '{test_wiki_url}'")
    wiki_content = extract_wiki_content(test_wiki_url)
    
    print(f"\nExtracted Wiki Content from: {wiki_content['title']}")
    print(f"\nSummary:\n{wiki_content['summary']}")
    
    print("\nSections:")
    for section in wiki_content['sections']:
        print(f"\n--- {section['title']} ---")
        print(section['content'][:150] + '...' if len(section['content']) > 150 else section['content'])
    
    print("\nInfobox Data:")
    for key, value in wiki_content['infobox'].items():
        print(f"- {key}: {value}")
    
    print("\nRelevant Links:")
    for link in wiki_content['links']:
        print(f"- {link['text']}: {link['url']}")
