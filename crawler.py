import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time
import logging
import random
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

logger = logging.getLogger(__name__)

class ACDCCrawler:
    def __init__(self):
        self.session = self._create_session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        }

    def _create_session(self):
        """Create a session with retry strategy"""
        session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        return session

    def _extract_price(self, text):
        """Extract price from text"""
        try:
            price_match = re.search(r'R\s*([\d,]+\.?\d*)', text)
            if price_match:
                return float(price_match.group(1).replace(',', ''))
            return None
        except Exception as e:
            logger.error(f"Price extraction error: {e}")
            return None

    def _clean_sku(self, sku):
        """Clean and standardize SKU format"""
        if sku:
            return re.sub(r'[^A-Z0-9-]', '', sku.upper())
        return None

    def crawl_acdc_products(self, category_url="https://acdc.co.za/2-home"):
        """Crawl ACDC products systematically"""
        try:
            logger.info(f"Starting category crawl: {category_url}")
            products_data = {}  # Use dict with SKU as key for faster lookups
            page = 1
            
            while True:
                page_url = f"{category_url}?page={page}"
                logger.info(f"Crawling page {page}: {page_url}")
                
                try:
                    response = self.session.get(page_url, headers=self.headers, timeout=30)
                    response.raise_for_status()
                    soup = BeautifulSoup(response.content, 'html.parser')
                    
                    # Check if page exists
                    products = soup.find_all('article', class_='product-miniature')
                    if not products:
                        logger.info(f"No more products found on page {page}")
                        break
                    
                    for product in products:
                        try:
                            # Extract SKU and product link
                            product_link = product.find('a', href=True)['href']
                            # Get SKU from URL or product description
                            sku_match = re.search(r'/([A-Za-z0-9-]+)\.html$', product_link)
                            
                            if sku_match:
                                sku = self._clean_sku(sku_match.group(1))
                                if not sku:
                                    continue
                                
                                # Get product details page
                                logger.info(f"Processing SKU: {sku}")
                                product_response = self.session.get(
                                    product_link, 
                                    headers=self.headers, 
                                    timeout=30
                                )
                                product_soup = BeautifulSoup(product_response.content, 'html.parser')
                                
                                # Initialize product data
                                price_data = {
                                    'sku': sku,
                                    'url': product_link,
                                    'prices': {},
                                    'stock': {},
                                    'last_updated': datetime.now().isoformat()
                                }
                                
                                # Extract location-based prices and stock
                                stock_table = product_soup.find('table')  # Adjust selector as needed
                                if stock_table:
                                    rows = stock_table.find_all('tr')
                                    for row in rows[1:]:  # Skip header row
                                        cols = row.find_all('td')
                                        if len(cols) >= 2:
                                            location = cols[0].get_text().strip()
                                            stock = cols[1].get_text().strip()
                                            price_data['stock'][location] = stock
                                            
                                            # Try to get price
                                            if len(cols) >= 3:
                                                price = self._extract_price(cols[2].get_text())
                                                if price:
                                                    price_data['prices'][location] = price
                                
                                # Fallback to main product price if no location prices found
                                if not price_data['prices']:
                                    price_elem = product_soup.find('span', class_='price')
                                    if price_elem:
                                        price = self._extract_price(price_elem.get_text())
                                        if price:
                                            price_data['prices']['default'] = price
                                
                                products_data[sku] = price_data
                                logger.info(f"Successfully processed {sku}")
                                
                                # Random delay between product requests
                                time.sleep(random.uniform(1, 2))
                                
                        except Exception as e:
                            logger.error(f"Error processing product: {e}")
                            continue
                    
                    page += 1
                    # Random delay between pages
                    time.sleep(random.uniform(2, 3))
                    
                except requests.RequestException as e:
                    logger.error(f"Error fetching page {page}: {e}")
                    break
                
            logger.info(f"Crawl completed. Processed {len(products_data)} products")
            return products_data
            
        except Exception as e:
            logger.error(f"Crawl error: {e}")
            return None

    def get_product_price(self, sku):
        """Get price for a specific SKU"""
        try:
            search_url = f"https://acdc.co.za/search?controller=search&s={sku}"
            response = self.session.get(search_url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                products = soup.find_all('article', class_='product-miniature')
                
                for product in products:
                    product_sku = self._clean_sku(product.get('data-sku', ''))
                    if product_sku == self._clean_sku(sku):
                        price_elem = product.find('span', class_='price')
                        if price_elem:
                            return self._extract_price(price_elem.get_text())
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting price for SKU {sku}: {e}")
            return None

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test crawler
    crawler = ACDCCrawler()
    test_products = crawler.crawl_acdc_products()
    
    if test_products:
        logger.info(f"Successfully crawled {len(test_products)} products")
        # Print first product as example
        first_sku = next(iter(test_products))
        logger.info(f"Example product data for SKU {first_sku}:")
        logger.info(test_products[first_sku])
