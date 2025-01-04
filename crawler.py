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
            logger.debug(f"Raw price text: {text}")
            
            # Remove currency symbol, VAT text and spaces
            price_text = text.strip()
            price_text = re.sub(r'\(.*?\)', '', price_text)  # Remove anything in parentheses
            price_text = price_text.replace('EXCL. VAT', '')
            price_text = price_text.replace('EXCL VAT', '')
            price_text = price_text.replace('R', '')
            price_text = price_text.strip()
            
            logger.debug(f"After cleaning text: {price_text}")
            
            # Extract numbers
            price_match = re.search(r'[\d,]+\.?\d*', price_text)
            if price_match:
                price_text = price_match.group()
                logger.debug(f"Matched price text: {price_text}")
                
                # Convert to proper decimal format
                price_text = price_text.replace(',', '.')
                price = float(price_text)
                logger.debug(f"Final extracted price: {price}")
                return price
            
            logger.debug("No valid price pattern found")
            return None
            
        except Exception as e:
            logger.error(f"Price extraction error: {e}")
            return None

    def get_price_from_url(self, url, sku):
        """Get price from a specific URL"""
        try:
            logger.info(f"Fetching URL: {url}")
            response = self.session.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                logger.debug(f"Page content length: {len(response.content)}")

                # Log the entire relevant section for debugging
                price_sections = soup.find_all(['span', 'div'], class_=['price_tag_c6', 'span_head_c2', 'price'])
                logger.debug(f"Found {len(price_sections)} price sections")
                for section in price_sections:
                    logger.debug(f"Price section HTML: {section}")

                # Method 1: Try product page price (span_head_c2)
                price_elem = soup.find('span', class_='span_head_c2')
                if price_elem:
                    logger.debug(f"Found span_head_c2: {price_elem}")
                    price = self._extract_price(price_elem.get_text())
                    if price:
                        return price

                # Method 2: Try search results price (price_tag_c6)
                price_elem = soup.find('span', class_='price_tag_c6')
                if price_elem:
                    logger.debug(f"Found price_tag_c6: {price_elem}")
                    price = self._extract_price(price_elem.get_text())
                    if price:
                        return price

                # Method 3: Look for any price near the SKU
                product_section = soup.find(string=re.compile(sku, re.IGNORECASE))
                if product_section:
                    parent = product_section.find_parent()
                    if parent:
                        price_text = parent.find(string=re.compile(r'R\s*[\d,]+\.?\d*'))
                        if price_text:
                            logger.debug(f"Found price near SKU: {price_text}")
                            price = self._extract_price(price_text)
                            if price:
                                return price

                logger.warning(f"No price found for {sku}")
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
                
                # Try search URL first
                search_url = f"{self.base_url}/search?controller=search&s={sku}"
                price = self.get_price_from_url(search_url, sku)
                
                if not price:
                    # Try direct product URL as backup
                    product_url = f"{self.base_url}/product/{sku.lower()}"
                    price = self.get_price_from_url(product_url, sku)
                
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
