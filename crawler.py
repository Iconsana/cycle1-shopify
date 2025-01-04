import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time
import logging
import random
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

logging.basicConfig(level=logging.INFO)
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
        if not text:
            return None
        try:
            # Remove 'EXCL. VAT' and 'R', keep numbers and decimal
            price_text = text.replace('EXCL. VAT', '').replace('R', '').strip()
            # Remove any non-digit characters except dots and commas
            price_text = re.sub(r'[^\d.,]', '', price_text)
            # Convert to proper decimal format
            price_text = price_text.replace(',', '.')
            # If multiple decimals, keep only first one
            if price_text.count('.') > 1:
                parts = price_text.split('.')
                price_text = parts[0] + '.' + parts[1]
            return float(price_text) if price_text else None
        except Exception as e:
            logger.error(f"Price extraction error: {e}")
            return None

    def _clean_sku(self, sku):
        """Clean and standardize SKU format"""
        if sku:
            # Remove any accidental double slashes
            sku = re.sub(r'/+', '/', sku)
            # Remove trailing/leading slashes
            sku = sku.strip('/')
            # Replace slashes with dashes for URL
            sku = sku.replace('/', '-')
            # Remove any spaces
            sku = sku.replace(' ', '')
            # Convert to uppercase
            sku = sku.upper()
            return sku
        return None

    def get_price_from_url(self, url, sku):
        """Get price from a specific URL"""
        try:
            logger.info(f"Fetching URL: {url}")
            response = self.session.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # First check if we're on a product page
                sku_elem = soup.find('p', class_='details_page_tag_text_c1')
                if sku_elem and sku.upper() in sku_elem.text.upper():
                    # Try to find LIST PRICE
                    price_text = None
                    list_price_text = soup.find(string=re.compile(r'LIST PRICE:.*', re.IGNORECASE))
                    if list_price_text:
                        price_text = list_price_text.strip()
                    
                    if price_text:
                        price = self._extract_price(price_text)
                        if price:
                            logger.info(f"Found price for {sku} on product page: R{price}")
                            return price
                
                # If not found on product page, check search results
                products = soup.find_all('article', class_='product-miniature')
                for product in products:
                    product_sku = product.find('p', class_='details_page_tag_text_c1')
                    if product_sku and sku.upper() in product_sku.text.upper():
                        price_elem = product.find('span', class_='price')
                        if price_elem:
                            price = self._extract_price(price_elem.text)
                            if price:
                                logger.info(f"Found price for {sku} in search results: R{price}")
                                return price
                
                logger.warning(f"No price found for {sku} on page")
                return None
            else:
                logger.error(f"Failed to get page: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting price from URL for {sku}: {e}")
            return None

    def targeted_crawl(self, sku_list):
        """Crawl only specific SKUs"""
        results = {}
        total_skus = len(sku_list)
        
        for index, sku in enumerate(sku_list, 1):
            try:
                logger.info(f"Processing {index}/{total_skus}: {sku}")
                clean_sku = self._clean_sku(sku)
                
                # Try direct product URL first
                search_url = f"https://acdc.co.za/search?controller=search&s={clean_sku}"
                price = self.get_price_from_url(search_url, clean_sku)
                
                if price:
                    results[sku] = {
                        'price': price,
                        'timestamp': datetime.now().isoformat(),
                        'source': 'ACDC Dynamics'
                    }
                    logger.info(f"Successfully processed {sku}")
                else:
                    logger.warning(f"No price found for {sku}")
                
                # Random delay between requests
                time.sleep(random.uniform(1, 2))
                
            except Exception as e:
                logger.error(f"Error processing {sku}: {e}")
                continue
        
        logger.info(f"Crawl completed. Found prices for {len(results)}/{total_skus} SKUs")
        return results

if __name__ == "__main__":
    # Test the crawler
    logging.basicConfig(level=logging.INFO)
    crawler = ACDCCrawler()
    test_skus = ["DF1730SL-20A"]
    results = crawler.targeted_crawl(test_skus)
    print("Test Results:", results)
