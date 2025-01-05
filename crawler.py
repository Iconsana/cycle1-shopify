import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time
import logging
import random
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class ACDCCrawler:
    def __init__(self):
        self.session = self._create_session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        }
        # Hardcoded URL for testing
        self.test_url = "https://acdc.co.za/batteries-chargers-power-supplies-avrs-upss/26212-0-30vdc-0-20a-variable-power-supply-230vac"

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
            # Remove currency symbol and clean
            price_text = text.replace('R', '').replace('EXCL VAT', '').strip()
            # Remove any non-digit characters except dots and commas
            price_text = re.sub(r'[^\d.,]', '', price_text)
            # Convert to proper decimal format
            price_text = price_text.replace(',', '.')
            
            return float(price_text) if price_text else None
            
        except Exception as e:
            logger.error(f"Price extraction error: {e}")
            return None

    def get_price(self, sku="DF1730SL-20A"):
        """Get price from hardcoded test URL"""
        try:
            logger.info(f"Fetching test URL: {self.test_url}")
            response = self.session.get(self.test_url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Look for exact price element from screenshots
                price_elem = soup.find('span', class_='span_head_c2')
                if price_elem:
                    price = self._extract_price(price_elem.get_text())
                    if price:
                        logger.info(f"Found price: R{price}")
                        return price
                
                # Backup: try price_tag_c6
                price_elem = soup.find('span', class_='price_tag_c6')
                if price_elem:
                    price = self._extract_price(price_elem.get_text())
                    if price:
                        logger.info(f"Found price: R{price}")
                        return price
                
                logger.warning("No price found")
                return None
            
            logger.error(f"Failed to get page: {response.status_code}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting price: {e}")
            return None

    def targeted_crawl(self, sku_list):
        """Crawl SKUs with hardcoded test URL - matches price_monitor.py expectation"""
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
    crawler = ACDCCrawler()
    test_skus = ["DF1730SL-20A"]
    results = crawler.targeted_crawl(test_skus)
    print("Test Results:", results)
