import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time
import logging
import random
import traceback
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ACDCCrawler:
    def __init__(self):
        logger.debug("Initializing ACDCCrawler")
        self.session = self._create_session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        }
        self.base_url = "https://acdc.co.za"

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
        session.mount("http://", adapter)
        return session

    def _extract_price(self, text):
        """Extract price from text"""
        if not text:
            logger.debug("Empty price text received")
            return None
            
        try:
            logger.debug(f"Attempting to extract price from: {text}")
            # Remove currency symbol and clean
            price_text = text.replace('EXCL VAT', '').replace('EXCL. VAT', '').strip()
            price_text = price_text.replace('(', '').replace(')', '')
            price_text = price_text.replace('R', '').strip()
            
            logger.debug(f"After initial cleaning: {price_text}")
            
            # Remove any non-digit characters except dots and commas
            price_text = re.sub(r'[^\d.,]', '', price_text)
            
            # Convert to proper decimal format
            price_text = price_text.replace(',', '.')
            
            # If multiple decimals, keep only first one
            if price_text.count('.') > 1:
                parts = price_text.split('.')
                price_text = parts[0] + '.' + parts[1]
            
            if price_text:
                price = float(price_text)
                logger.info(f"Successfully extracted price: {price}")
                return price
            
            return None
            
        except Exception as e:
            logger.error(f"Price extraction error: {e}")
            logger.debug(f"Price extraction traceback: {traceback.format_exc()}")
            return None

    def get_price(self, sku):
        """Get price for SKU using search then product page"""
        try:
            # First try search URL with proper encoding
            encoded_sku = requests.utils.quote(sku)
            search_url = f"{self.base_url}/2-home?s={encoded_sku}&search-filter=1"
            logger.info(f"Trying search URL: {search_url}")
            
            response = self.session.get(search_url, headers=self.headers, timeout=30)
            logger.debug(f"Search response status: {response.status_code}")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # First try to find direct price in search results
                price_elem = soup.find('span', class_='product-price price_tag_c6')
                if price_elem:
                    price = self._extract_price(price_elem.get_text())
                    if price:
                        logger.info(f"Found price in search results: {price}")
                        return price

                # Try to find product link in search results
                product_elem = soup.find('a', class_='price_tag_c7', href=True)
                if not product_elem:
                    product_elem = soup.find('a', href=lambda x: x and sku.lower() in x.lower())
                    
                if product_elem:
                    product_url = product_elem['href']
                    if not product_url.startswith('http'):
                        product_url = f"{self.base_url}{product_url}"
                        
                    logger.info(f"Found product URL: {product_url}")
                    
                    # Get product page
                    product_response = self.session.get(product_url, headers=self.headers, timeout=30)
                    if product_response.status_code == 200:
                        product_soup = BeautifulSoup(product_response.content, 'html.parser')
                        
                        # Try all possible price locations
                        list_price = product_soup.find(string=re.compile(r'LIST PRICE:.*R.*'))
                        if list_price:
                            price = self._extract_price(list_price)
                            if price:
                                logger.info(f"Found list price: {price}")
                                return price
                        
                        excl_vat = product_soup.find('div', class_='product_header_con_c5')
                        if excl_vat:
                            price_text = excl_vat.find(string=re.compile(r'R\s*[\d,\.]+'))
                            if price_text:
                                price = self._extract_price(price_text)
                                if price:
                                    logger.info(f"Found excl VAT price: {price}")
                                    return price
                                
                        span_price = product_soup.find('span', class_='span_head_c2')
                        if span_price:
                            price = self._extract_price(span_price.get_text())
                            if price:
                                logger.info(f"Found span price: {price}")
                                return price
                
                logger.warning(f"No price found for {sku}")
                return None
                
            logger.error(f"Failed to get search page: {response.status_code}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting price for {sku}: {e}")
            logger.debug(f"Price fetch traceback: {traceback.format_exc()}")
            return None

    def targeted_crawl(self, sku_list):
        """Crawl specific SKUs and get their prices"""
        logger.info(f"Starting targeted crawl for {len(sku_list)} SKUs")
        results = {}
        total_skus = len(sku_list)
        
        for index, sku in enumerate(sku_list, 1):
            try:
                logger.info(f"Processing {index}/{total_skus}: {sku}")
                
                price = self.get_price(sku)
                if price:
                    results[sku] = {
                        'price': price,
                        'timestamp': datetime.now().isoformat(),
                        'source': 'ACDC Dynamics'
                    }
                    logger.info(f"Successfully got price for {sku}: R{price}")
                else:
                    logger.warning(f"No price found for {sku}")
                
                # Random delay between requests
                delay = random.uniform(1, 2)
                logger.debug(f"Waiting {delay} seconds before next request")
                time.sleep(delay)
                
            except Exception as e:
                logger.error(f"Error processing {sku}: {e}")
                logger.debug(f"SKU processing traceback: {traceback.format_exc()}")
                continue
        
        logger.info(f"Crawl completed. Found prices for {len(results)}/{total_skus} SKUs")
        return results

if __name__ == "__main__":
    # Test the crawler
    crawler = ACDCCrawler()
    test_skus = ["DF1730SL-20A"]
    results = crawler.targeted_crawl(test_skus)
    print("Test Results:", results)
