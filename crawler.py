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

# Configure detailed logging
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
        # Hardcoded URL for testing
        self.test_url = "https://acdc.co.za/batteries-chargers-power-supplies-avrs-upss/26212-0-30vdc-0-20a-variable-power-supply-230vac"
        logger.debug(f"Initialized with test URL: {self.test_url}")

    def _create_session(self):
        """Create a session with retry strategy"""
        logger.debug("Creating session with retry strategy")
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
        logger.debug(f"Attempting to extract price from text: {text}")
        
        if not text:
            logger.debug("Empty price text received")
            return None
            
        try:
            # Remove currency symbol and clean
            price_text = text.replace('R', '').replace('EXCL VAT', '').strip()
            logger.debug(f"After initial cleaning: {price_text}")
            
            # Remove any non-digit characters except dots and commas
            price_text = re.sub(r'[^\d.,]', '', price_text)
            logger.debug(f"After removing non-digits: {price_text}")
            
            # Convert to proper decimal format
            price_text = price_text.replace(',', '.')
            logger.debug(f"After format conversion: {price_text}")
            
            if price_text:
                price = float(price_text)
                logger.debug(f"Successfully extracted price: {price}")
                return price
            
            logger.debug("No valid price text found")
            return None
            
        except Exception as e:
            logger.error(f"Price extraction error: {e}")
            logger.debug(f"Price extraction traceback: {traceback.format_exc()}")
            return None

    def get_price(self, sku="DF1730SL-20A"):
        """Get price from hardcoded test URL"""
        logger.debug(f"Getting price for SKU: {sku}")
        
        try:
            logger.info(f"Fetching test URL: {self.test_url}")
            logger.debug(f"Using headers: {self.headers}")
            
            response = self.session.get(self.test_url, headers=self.headers, timeout=30)
            logger.debug(f"Response status code: {response.status_code}")
            
            if response.status_code == 200:
                logger.debug("Successfully got page content")
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for exact price element from screenshots
                price_elem = soup.find('span', class_='span_head_c2')
                if price_elem:
                    logger.debug(f"Found span_head_c2 element: {price_elem}")
                    price = self._extract_price(price_elem.get_text())
                    if price:
                        logger.info(f"Found price via span_head_c2: R{price}")
                        return price
                else:
                    logger.debug("No span_head_c2 element found")
                
                # Backup: try price_tag_c6
                price_elem = soup.find('span', class_='price_tag_c6')
                if price_elem:
                    logger.debug(f"Found price_tag_c6 element: {price_elem}")
                    price = self._extract_price(price_elem.get_text())
                    if price:
                        logger.info(f"Found price via price_tag_c6: R{price}")
                        return price
                else:
                    logger.debug("No price_tag_c6 element found")
                
                # Log relevant HTML for debugging
                logger.debug("Relevant HTML sections:")
                for elem in soup.find_all(['span', 'div'], class_=['span_head_c2', 'price_tag_c6', 'price']):
                    logger.debug(f"Found price-related element: {elem}")
                
                logger.warning("No price found in any expected elements")
                return None
            
            logger.error(f"Failed to get page: {response.status_code}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting price: {e}")
            logger.debug(f"Price fetch traceback: {traceback.format_exc()}")
            return None

    def targeted_crawl(self, sku_list):
        """Crawl SKUs with hardcoded test URL"""
        logger.debug(f"Starting targeted crawl with SKUs: {sku_list}")
        results = {}
        total_skus = len(sku_list)
        
        for index, sku in enumerate(sku_list, 1):
            try:
                logger.info(f"Processing {index}/{total_skus}: {sku}")
                logger.debug(f"Starting price fetch for SKU: {sku}")
                
                price = self.get_price(sku)
                logger.debug(f"Price fetch result for {sku}: {price}")
                
                if price:
                    results[sku] = {
                        'price': price,
                        'timestamp': datetime.now().isoformat(),
                        'source': 'ACDC Dynamics'
                    }
                    logger.info(f"Successfully processed {sku}")
                    logger.debug(f"Added result for {sku}: {results[sku]}")
                else:
                    logger.warning(f"No price found for {sku}")
                
                # Random delay between requests
                delay = random.uniform(1, 2)
                logger.debug(f"Sleeping for {delay} seconds")
                time.sleep(delay)
                
            except Exception as e:
                logger.error(f"Error processing {sku}: {e}")
                logger.debug(f"SKU processing traceback: {traceback.format_exc()}")
                continue
        
        logger.info(f"Crawl completed. Found prices for {len(results)}/{total_skus} SKUs")
        logger.debug(f"Final results: {results}")
        return results

if __name__ == "__main__":
    # Test the crawler
    logger.info("Starting crawler test")
    crawler = ACDCCrawler()
    test_skus = ["DF1730SL-20A"]
    results = crawler.targeted_crawl(test_skus)
    logger.info(f"Test Results: {results}")
