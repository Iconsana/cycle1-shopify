import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import re
import time
import logging
from typing import Optional, List, Dict

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_total_pages(soup: BeautifulSoup) -> Optional[int]:
    """Extract the total number of pages from pagination."""
    try:
        # Find pagination links
        pagination = soup.find('div', class_='pagination')
        if pagination:
            # Find all page numbers
            page_links = pagination.find_all('a', class_='js-search-link')
            page_numbers = [
                int(re.search(r'page=(\d+)', link.get('href', '')).group(1))
                for link in page_links
                if 'page=' in link.get('href', '')
            ]
            if page_numbers:
                return max(page_numbers)
    except Exception as e:
        logger.error(f"Error getting total pages: {e}")
    return None

def make_request(url: str, max_retries: int = 3, delay: int = 2) -> Optional[requests.Response]:
    """Make HTTP request with retry logic and rate limiting."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    }
    
    for attempt in range(max_retries):
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            logger.error(f"Attempt {attempt + 1}/{max_retries} failed for {url}: {e}")
            if attempt < max_retries - 1:
                sleep_time = delay * (attempt + 1)  # Exponential backoff
                logger.info(f"Waiting {sleep_time} seconds before retry...")
                time.sleep(sleep_time)
            continue
    return None

def scrape_acdc_products(start_page: int = 1, end_page: Optional[int] = None) -> List[Dict]:
    """
    Scrape products from ACDC website with pagination support.
    
    Args:
        start_page: Page number to start scraping from
        end_page: Optional page number to stop at. If None, will scrape all pages
    """
    base_url = 'https://acdc.co.za/2-home'
    products = []
    current_page = start_page
    
    # Get total pages if end_page not specified
    if end_page is None:
        logger.info("Detecting total number of pages...")
        response = make_request(base_url)
        if response:
            soup = BeautifulSoup(response.content, 'html.parser')
            end_page = get_total_pages(soup)
            if not end_page:
                logger.warning("Could not detect total pages, defaulting to page 4176")
                end_page = 4176
        else:
            logger.error("Failed to access the website")
            return products
    
    logger.info(f"Starting scrape from page {start_page} to {end_page}")
    total_products = 0
    
    while current_page <= end_page:
        page_url = f'{base_url}?page={current_page}'
        logger.info(f"Scraping page {current_page}/{end_page}")
        
        response = make_request(page_url)
        if not response:
            logger.error(f"Failed to retrieve page {current_page}, skipping...")
            current_page += 1
            continue
            
        soup = BeautifulSoup(response.content, 'html.parser')
        product_containers = soup.find_all('article', class_='product-miniature')
        
        if not product_containers:
            logger.warning(f"No products found on page {current_page}")
            # If we get multiple empty pages, we might have reached the end
            if current_page > 3:
                logger.info("Multiple empty pages detected, ending scrape...")
                break
        
        page_products = 0
        for product in product_containers:
            try:
                product_code = extract_product_code(product)
                if not product_code:
                    continue

                title_element = product.find('h2', class_='h3').find('a')
                raw_title = title_element.get_text(strip=True) if title_element else ""
                clean_product_title = clean_title(raw_title)
                
                price_span = product.find('span', class_='product-price')
                if price_span:
                    original_price = clean_price(price_span.get_text(strip=True))
                    marked_up_price = round(original_price * 1.1, 2)
                    
                    product_data = {
                        'Handle': product_code.lower(),
                        'Title': clean_product_title,
                        'Body (HTML)': create_clean_description(product_code, clean_product_title),
                        'Vendor': 'ACDC',
                        'Product Category': 'Electrical & Electronics',
                        'Type': 'Electrical Components',
                        'Tags': f'ACDC, {product_code}',
                        'Published': 'TRUE',
                        'Option1 Name': 'Title',
                        'Option1 Value': 'Default Title',
                        'Variant SKU': product_code,
                        'Variant Grams': '0',
                        'Variant Inventory Tracker': 'shopify',
                        'Variant Inventory Qty': '100',
                        'Variant Inventory Policy': 'deny',
                        'Variant Fulfillment Service': 'manual',
                        'Variant Price': str(marked_up_price),
                        'Variant Compare At Price': str(original_price),
                        'Variant Requires Shipping': 'TRUE',
                        'Variant Taxable': 'TRUE',
                        'Status': 'active'
                    }
                    
                    products.append(product_data)
                    page_products += 1
                    total_products += 1
                    
                    if total_products % 100 == 0:
                        logger.info(f"Milestone: {total_products} products scraped")
                
            except Exception as e:
                logger.error(f"Error processing product on page {current_page}: {e}")
                continue
        
        logger.info(f"Scraped {page_products} products from page {current_page}")
        
        # Add delay between pages to avoid overwhelming the server
        time.sleep(1)
        current_page += 1
    
    logger.info(f"Scraping completed. Total products scraped: {total_products}")
    return products

if __name__ == "__main__":
    # Example usage with progress tracking
    try:
        # Scrape first 10 pages as a test
        products = scrape_acdc_products(start_page=1, end_page=10)
        if products:
            filename = save_to_shopify_csv(products)
            logger.info(f"Products saved to {filename}")
        else:
            logger.warning("No products were scraped")
    except KeyboardInterrupt:
        logger.info("Scraping interrupted by user")
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
