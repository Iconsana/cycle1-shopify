import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time
import logging

logger = logging.getLogger(__name__)

class ACDCCrawler:
    def crawl_acdc_products(self, category_url="https://acdc.co.za/2-home"):
    """Crawl ACDC products systematically"""
    try:
        logger.info(f"Starting category crawl: {category_url}")
        products_data = {}  # Use dict with SKU as key for faster lookups
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        }
        
        # Get total pages from category
        response = requests.get(category_url, headers=headers, timeout=30)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all products on current page
        products = soup.find_all('article', class_='product-miniature')
        
        for product in products:
            try:
                # Extract SKU and product link
                product_link = product.find('a', href=True)['href']
                sku_match = re.search(r'/([A-Za-z0-9-]+)\.html$', product_link)
                
                if sku_match:
                    sku = sku_match.group(1).upper()
                    
                    # Get product details page
                    product_response = requests.get(product_link, headers=headers, timeout=30)
                    product_soup = BeautifulSoup(product_response.content, 'html.parser')
                    
                    # Extract all necessary data
                    price_data = {
                        'sku': sku,
                        'url': product_link,
                        'prices': {},
                        'stock': {},
                        'last_updated': datetime.now().isoformat()
                    }
                    
                    # Get prices for all locations
                    stock_table = product_soup.find('table', class_='stock-table')  # Adjust class
                    if stock_table:
                        for row in stock_table.find_all('tr')[1:]:  # Skip header
                            cols = row.find_all('td')
                            if len(cols) >= 3:
                                location = cols[0].get_text().strip()
                                stock = cols[1].get_text().strip()
                                price_data['stock'][location] = stock
                                
                                # Extract price if available
                                price_text = cols[2].get_text().strip()
                                if price_text:
                                    try:
                                        price = float(re.sub(r'[^\d.]', '', price_text))
                                        price_data['prices'][location] = price
                                    except ValueError:
                                        logger.warning(f"Could not parse price for {sku} at {location}")
                    
                    products_data[sku] = price_data
                    logger.info(f"Processed {sku} successfully")
                    
            except Exception as e:
                logger.error(f"Error processing product: {e}")
                continue
                
            time.sleep(1)  # Respect rate limits
            
        return products_data
        
    except Exception as e:
        logger.error(f"Crawl error: {e}")
        return None
