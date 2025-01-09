import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time
import logging
import random
import traceback
from threading import Thread, Lock, BoundedSemaphore
from queue import Queue
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class RateLimiter:
    def __init__(self, max_per_minute):
        self.semaphore = BoundedSemaphore(max_per_minute)
        self.lock = Lock()
        self.last_release_time = time.time()
        self.interval = 60.0 / max_per_minute

    def acquire(self):
        with self.lock:
            current_time = time.time()
            elapsed = current_time - self.last_release_time
            if elapsed < self.interval:
                time.sleep(self.interval - elapsed)
        self.semaphore.acquire()

    def release(self):
        with self.lock:
            self.last_release_time = time.time()
        self.semaphore.release()

class ACDCCrawler:
    def __init__(self):
        logger.debug("Initializing ACDCCrawler")
        self.session = self._create_session()
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        }
        self.base_url = "https://acdc.co.za"
        self.result_lock = Lock()
        self.results = {}
        self.request_limiter = RateLimiter(30)  # 30 requests per minute
        self.sheets_limiter = RateLimiter(50)   # 50 sheet updates per minute

    def _create_session(self):
        """Create a session with retry strategy"""
        session = requests.Session()
        retry_strategy = Retry(
            total=5,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
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
            
            # Handle thousands separators and decimal points
            price_text = price_text.replace(' ', '')
            
            if ',' in price_text and '.' in price_text:
                price_text = price_text.replace(',', '')
            else:
                price_text = price_text.replace(',', '.')
            
            price_text = re.sub(r'[^\d.]', '', price_text)
            
            if price_text:
                try:
                    price = float(price_text)
                    logger.info(f"Successfully extracted price: {price}")
                    if 0 < price < 1000000:
                        return price
                    else:
                        logger.warning(f"Price outside reasonable range: {price}")
                        return None
                except ValueError:
                    logger.error(f"Could not convert price text to float: {price_text}")
                    return None
            
            return None
            
        except Exception as e:
            logger.error(f"Price extraction error: {e}")
            logger.debug(f"Price extraction traceback: {traceback.format_exc()}")
            return None

    def get_price(self, sku):
        """Get price for SKU using search then product page"""
        try:
            encoded_sku = requests.utils.quote(sku)
            search_url = f"{self.base_url}/2-home?s={encoded_sku}&search-filter=1"
            logger.info(f"Trying search URL: {search_url}")
            
            response = self.session.get(search_url, headers=self.headers, timeout=30)
            logger.debug(f"Search response status: {response.status_code}")
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                price_elem = soup.find('span', class_='product-price price_tag_c6')
                if price_elem:
                    price = self._extract_price(price_elem.get_text())
                    if price:
                        logger.info(f"Found price in search results: {price}")
                        return price

                product_elem = soup.find('a', class_='price_tag_c7', href=True)
                if not product_elem:
                    product_elem = soup.find('a', href=lambda x: x and sku.lower() in x.lower())
                    
                if product_elem:
                    product_url = product_elem['href']
                    if not product_url.startswith('http'):
                        product_url = f"{self.base_url}{product_url}"
                        
                    logger.info(f"Found product URL: {product_url}")
                    
                    product_response = self.session.get(product_url, headers=self.headers, timeout=30)
                    if product_response.status_code == 200:
                        product_soup = BeautifulSoup(product_response.content, 'html.parser')
                        
                        list_price_text = None
                        for text in product_soup.stripped_strings:
                            if 'LIST PRICE:' in text:
                                list_price_text = text
                                break
                        
                        if list_price_text:
                            price = self._extract_price(list_price_text)
                            if price:
                                logger.info(f"Found list price: {price}")
                                return price
                        
                        excl_vat = product_soup.find('div', class_='product_header_con_c5')
                        if excl_vat:
                            price_text = None
                            for text in excl_vat.stripped_strings:
                                if 'R' in text and any(c.isdigit() for c in text):
                                    price_text = text
                                    break
                            
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

    def get_price_with_rate_limit(self, sku):
        """Rate-limited price retrieval"""
        try:
            self.request_limiter.acquire()
            price = self.get_price(sku)
            return price
        finally:
            self.request_limiter.release()

    def process_sku(self, sku, batch_num, total_batches):
        """Process a single SKU with rate limiting"""
        try:
            logger.info(f"Processing SKU {sku} in batch {batch_num}/{total_batches}")
            price = self.get_price_with_rate_limit(sku)
            
            if price:
                with self.result_lock:
                    self.results[sku] = {
                        'price': price,
                        'timestamp': datetime.now().isoformat(),
                        'source': 'ACDC Dynamics'
                    }
                logger.info(f"Successfully got price for {sku}: R{price}")
            else:
                logger.warning(f"No price found for {sku}")
                
        except Exception as e:
            logger.error(f"Error processing {sku}: {e}")
            logger.debug(f"SKU processing traceback: {traceback.format_exc()}")

    def batch_crawl(self, sku_list, batch_size=5):
        """Process SKUs in batches with rate limiting"""
        logger.info(f"Starting batch crawl for {len(sku_list)} SKUs")
        self.results = {}
        total_batches = (len(sku_list) + batch_size - 1) // batch_size

        for batch_num in range(total_batches):
            if batch_num > 0:
                delay = random.uniform(2, 4)
                logger.debug(f"Batch complete. Waiting {delay} seconds before next batch")
                time.sleep(delay)

            start_idx = batch_num * batch_size
            end_idx = min(start_idx + batch_size, len(sku_list))
            batch = sku_list[start_idx:end_idx]
            
            logger.info(f"Processing batch {batch_num + 1}/{total_batches}")
            
            threads = []
            for sku in batch:
                thread = Thread(
                    target=self.process_sku,
                    args=(sku, batch_num + 1, total_batches)
                )
                thread.start()
                threads.append(thread)
            
            for thread in threads:
                thread.join()

        logger.info(f"Batch crawl completed. Found prices for {len(self.results)}/{len(sku_list)} SKUs")
        return self.results

    def targeted_crawl(self, sku_list):
        """Main crawl method with improved rate limiting"""
        return self.batch_crawl(sku_list)

if __name__ == "__main__":
    crawler = ACDCCrawler()
    test_skus = ["DF1730SL-20A", "TR2-D09305"]
    results = crawler.targeted_crawl(test_skus)
    print("Test Results:", results)
