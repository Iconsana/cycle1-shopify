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
        self.result_lock = Lock()  # For thread-safe updates to results
        self.results = {}
        
        # Rate limiters
        self.request_limiter = RateLimiter(30)  # 30 requests per minute
        self.sheets_limiter = RateLimiter(50)   # 50 sheet updates per minute

    def _create_session(self):
        """Create a session with retry strategy"""
        session = requests.Session()
        retry_strategy = Retry(
            total=5,  # Increased from 3 to 5
            backoff_factor=2,  # Increased for more spacing between retries
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def get_price_with_rate_limit(self, sku):
        """Rate-limited price retrieval"""
        try:
            self.request_limiter.acquire()
            price = self.get_price(sku)
            return price
        finally:
            self.request_limiter.release()

    def batch_crawl(self, sku_list, batch_size=5):
        """Process SKUs in batches with rate limiting"""
        logger.info(f"Starting batch crawl for {len(sku_list)} SKUs")
        self.results = {}
        total_batches = (len(sku_list) + batch_size - 1) // batch_size

        for batch_num in range(total_batches):
            if batch_num > 0:
                # Add delay between batches
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
            
            # Wait for all threads in this batch
            for thread in threads:
                thread.join()

        logger.info(f"Batch crawl completed. Found prices for {len(self.results)}/{len(sku_list)} SKUs")
        return self.results

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

    def targeted_crawl(self, sku_list):
        """Main crawl method with improved rate limiting"""
        return self.batch_crawl(sku_list)

if __name__ == "__main__":
    # Test the crawler
    crawler = ACDCCrawler()
    test_skus = ["DF1730SL-20A", "TR2-D09305"]
    results = crawler.targeted_crawl(test_skus)
    print("Test Results:", results)
