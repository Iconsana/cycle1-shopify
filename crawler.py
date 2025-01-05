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

    def get_product_url(self, sku, title=None):
        """Generate correct ACDC product URL"""
        search_url = f"{self.base_url}/search?controller=search&s={sku}"
        
        try:
            # First get search page to find full product URL
            logger.info(f"Fetching search URL: {search_url}")
            response = self.session.get(search_url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Try to find the product link from the price tag
                price_link = soup.find('a', class_='price_tag_c7')
                if price_link and 'href' in price_link.attrs:
                    logger.info(f"Found product URL from price tag: {price_link['href']}")
                    return price_link['href']
                    
                # Try to find the link in product reference details
                ref_link = soup.find('div', class_='product_ref_details').find('a') if soup.find('div', class_='product_ref_details') else None
                if ref_link and 'href' in ref_link.attrs:
                    logger.info(f"Found product URL from reference: {ref_link['href']}")
                    return ref_link['href']
                    
                # Try to find any link containing the SKU
                any_link = soup.find('a', href=lambda x: x and sku.lower() in x.lower())
                if any_link:
                    logger.info(f"Found product URL from SKU: {any_link['href']}")
                    return any_link['href']
                
            logger.warning("Could not find product URL, using search URL")
            return search_url
            
        except Exception as e:
            logger.error(f"Error getting product URL: {e}")
            return search_url

    def get_price_from_url(self, url, sku):
        """Get price from a specific URL"""
        try:
            logger.info(f"Fetching URL: {url}")
            response = self.session.get(url, headers=self.headers, timeout=30)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                logger.debug("Successfully fetched page")
                
                # Method 1: Try price_tag_c6 with content attribute
                price_elem = soup.find('span', class_=['product-price', 'price_tag_c6'])
                if price_elem:
                    if 'content' in price_elem.attrs:
                        price = float(price_elem['content'])
                        logger.info(f"Found price from content attribute: {price}")
                        return price
                    else:
                        price = self._extract_price(price_elem.get_text())
                        if price:
                            logger.info(f"Found price from price_tag_c6: {price}")
                            return price
                
                # Method 2: Try span_head_c2
                price_elem = soup.find('span', class_='span_head_c2')
                if price_elem:
                    price = self._extract_price(price_elem.get_text())
                    if price:
                        logger.info(f"Found price from span_head_c2: {price}")
                        return price
                
                # Method 3: Try finding price near SKU text
                product_elem = soup.find(string=re.compile(sku, re.IGNORECASE))
                if product_elem:
                    parent = product_elem.find_parent('div')
                    if parent:
                        # Look for price in nearby elements
                        price_elems = parent.find_all(['span', 'div'], 
                            class_=['price', 'price_tag_c6', 'product-price', 'span_head_c2'])
                        for elem in price_elems:
                            price = self._extract_price(elem.get_text())
                            if price:
                                logger.info(f"Found price near SKU: {price}")
                                return price
                
                # Debug: Log what we found
                logger.debug("Price elements found on page:")
                for elem in soup.find_all(['span', 'div'], class_=['price', 'product-price', 'price_tag_c6', 'span_head_c2']):
                    logger.debug(f"Price element: {elem}")
                
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
                
                # Get the correct product URL
                product_url = self.get_product_url(sku)
                if product_url:
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
