import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time
import logging
import random
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

logging.basicConfig(level=logging.DEBUG)  # Set to DEBUG for development
logger = logging.getLogger(__name__)

class ACDCCrawler:
    def __init__(self):
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
            return None
        try:
            logger.debug(f"Extracting price from: {text}")
            
            # Remove currency symbol, VAT text and spaces
            price_text = text.strip()
            price_text = price_text.replace('EXCL. VAT', '')
            price_text = price_text.replace('EXCL VAT', '')
            price_text = price_text.replace('(', '').replace(')', '')
            price_text = price_text.replace('R', '')
            price_text = price_text.strip()
            
            # Remove any non-digit characters except dots and commas
            price_text = re.sub(r'[^\d.,]', '', price_text)
            
            # Convert to proper decimal format (handle both comma and dot)
            price_text = price_text.replace(',', '.')
            
            # If multiple decimals, keep only first one
            if price_text.count('.') > 1:
                parts = price_text.split('.')
                price_text = parts[0] + '.' + parts[1]
            
            if price_text:
                price = float(price_text)
                logger.debug(f"Extracted price: {price}")
                return price
            return None
        
        except Exception as e:
            logger.error(f"Price extraction error: {e}")
            return None

    def _clean_sku(self, sku):
        """Clean and standardize SKU format"""
        if sku:
            # Remove any accidental double slashes
            sku = re.sub(r'/+', '/', sku)
            # Remove trailing/leading slashes and spaces
            sku = sku.strip('/ ')
            # Replace slashes with dashes for URL
            sku = sku.replace('/', '-')
            # Convert to uppercase
            sku = sku.upper()
            logger.debug(f"Cleaned SKU: {sku}")
            return sku
        return None

    def get_price_from_url(self, url, sku):
        """Get price from a specific URL"""
        try:
            logger.info(f"Fetching URL: {url}")
            response = self.session.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                logger.info(f"Successfully fetched page for {sku}")

                # Method 1: Try price_tag_c6 class (search results)
                price_elem = soup.find('span', class_=['price_tag_c6', 'product-price'])
                if price_elem:
                    price = self._extract_price(price_elem.get_text())
                    if price:
                        logger.info(f"Found price (Method 1) for {sku}: R{price}")
                        return price

                # Method 2: Try span_head_c2 class (product page)
                price_elem = soup.find('span', class_='span_head_c2')
                if price_elem:
                    price = self._extract_price(price_elem.get_text())
                    if price:
                        logger.info(f"Found price (Method 2) for {sku}: R{price}")
                        return price

                # Method 3: Try finding price in product header
                price_elem = soup.find('div', class_='product_header_con_c5')
                if price_elem:
                    # Look for any price text
                    price_text = price_elem.find(string=re.compile(r'R\s*[\d,]+\.?\d*'))
                    if price_text:
                        price = self._extract_price(price_text)
                        if price:
                            logger.info(f"Found price (Method 3) for {sku}: R{price}")
                            return price

                # Method 4: Try finding in product miniature
                product_containers = soup.find_all('article', class_='product-miniature')
                for container in product_containers:
                    if sku.lower() in str(container).lower():
                        # Check for price span
                        price_span = container.find('span', class_='price')
                        if price_span:
                            price = self._extract_price(price_span.get_text())
                            if price:
                                logger.info(f"Found price (Method 4) for {sku}: R{price}")
                                return price

                logger.warning(f"No price found for {sku} on page")
                return None
            
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
                
                # Try search URL first
                search_url = f"{self.base_url}/search?controller=search&s={clean_sku}"
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
    # Configure logging for testing
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test the crawler
    crawler = ACDCCrawler()
    test_skus = ["DF1730SL-20A"]
    results = crawler.targeted_crawl(test_skus)
    print("Test Results:", results)
