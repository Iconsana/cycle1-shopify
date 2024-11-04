import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import re
import time
import logging
from typing import Optional, List, Dict

# Set up logging with more detail
logging.basicConfig(
    level=logging.DEBUG,  # Changed to DEBUG for more detail
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def extract_product_code(product_element):
    """Extract product code with enhanced debugging."""
    try:
        # Debug the product element structure
        logger.debug("Product HTML structure:")
        logger.debug(product_element.prettify())

        # Try multiple ways to find the product code
        # Method 1: Look for product code in product description
        description = product_element.find('div', class_='product-description')
        if description:
            logger.debug("Found product description div")
            text_content = description.get_text()
            logger.debug(f"Description text: {text_content}")
        else:
            logger.debug("No product description div found")

        # Method 2: Look for SKU/reference element
        sku_element = product_element.find(['span', 'div'], class_=['sku', 'reference'])
        if sku_element:
            logger.debug(f"Found SKU element: {sku_element.get_text()}")
            return sku_element.get_text().strip()

        # Method 3: Look in data attributes
        data_id = product_element.get('data-id-product')
        if data_id:
            logger.debug(f"Found product ID in data attribute: {data_id}")
            return f"ACDC-{data_id}"

        # Method 4: Try to find it in any text that matches pattern
        all_text = product_element.get_text()
        pattern = r'[A-Z0-9]{2,}[-]?[A-Z0-9]+(?=\s|$)'
        matches = re.finditer(pattern, all_text)
        for match in matches:
            potential_code = match.group()
            logger.debug(f"Found potential product code: {potential_code}")
            if len(potential_code) >= 4:  # Basic validation
                return potential_code

        logger.warning("No product code found through any method")
        return None

    except Exception as e:
        logger.error(f"Error in extract_product_code: {str(e)}", exc_info=True)
        return None

def scrape_acdc_products(start_page: int = 1, end_page: Optional[int] = None, max_pages: int = 4176):
    """
    Scrape products with enhanced debugging and error handling.
    """
    base_url = 'https://acdc.co.za/2-home'
    products = []
    current_page = start_page
    
    # Get total pages if end_page not specified
    if end_page is None:
        logger.info("Detecting total number of pages...")
        try:
            response = requests.get(base_url, headers={'User-Agent': 'Mozilla/5.0'})
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Debug pagination
            pagination = soup.find('div', class_='pagination')
            if pagination:
                logger.debug(f"Pagination HTML: {pagination.prettify()}")
            else:
                logger.debug("No pagination div found")
                
            end_page = max_pages
            
        except Exception as e:
            logger.error(f"Error accessing website: {e}")
            return products

    logger.info(f"Starting scrape from page {start_page} to {end_page}")

    while current_page <= end_page:
        page_url = f'{base_url}?page={current_page}'
        logger.info(f"Scraping page {current_page}")
        
        try:
            response = requests.get(
                page_url,
                headers={'User-Agent': 'Mozilla/5.0'},
                timeout=10
            )
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Debug the page structure
            logger.debug(f"Page title: {soup.title.string if soup.title else 'No title'}")
            
            # Try different product container classes
            product_containers = soup.find_all('article', class_='product-miniature')
            if not product_containers:
                logger.debug("No products found with class 'product-miniature', trying alternative classes...")
                product_containers = soup.find_all(['div', 'article'], class_=['product-container', 'product-item'])
            
            logger.info(f"Found {len(product_containers)} product containers on page {current_page}")
            
            for product in product_containers:
                try:
                    product_code = extract_product_code(product)
                    if not product_code:
                        continue

                    title_element = product.find(['h2', 'h3', 'h4'], class_=['h3', 'name', 'title'])
                    if title_element:
                        title_link = title_element.find('a')
                        raw_title = title_link.get_text(strip=True) if title_link else title_element.get_text(strip=True)
                    else:
                        logger.debug("No title element found, trying alternative selectors")
                        title_element = product.find('a', class_=['product-name', 'product-title'])
                        raw_title = title_element.get_text(strip=True) if title_element else "Unknown Product"

                    clean_product_title = clean_title(raw_title)
                    
                    price_element = product.find(['span', 'div'], class_=['product-price', 'price'])
                    if price_element:
                        original_price = clean_price(price_element.get_text(strip=True))
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
                        logger.info(f"Successfully scraped product: {product_code} - {clean_product_title}")
                
                except Exception as e:
                    logger.error(f"Error processing product on page {current_page}: {e}")
                    continue
            
            # Add delay between pages
            time.sleep(2)
            current_page += 1
            
        except Exception as e:
            logger.error(f"Error processing page {current_page}: {e}")
            current_page += 1
            continue

    logger.info(f"Scraping completed. Total products scraped: {len(products)}")
    return products

# Keep other functions (clean_price, clean_title, etc.) as they were...
