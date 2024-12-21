import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import re
import time
import random
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import logging
from threading import Event

class ACDCScraper:
    def __init__(self, progress_callback=None, cancel_event=None):
        self.progress_callback = progress_callback
        self.cancel_event = cancel_event or Event()
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:100.0) Gecko/20100101 Firefox/100.0',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.75 Safari/537.36'
        ]
        self.session = self._create_session()
        
    def _create_session(self):
        session = requests.Session()
        retry_strategy = Retry(
            total=5,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10)
        session.mount("https://", adapter)
        session.mount("http://", adapter)
        return session

    def _emit_progress(self, message, current, total, status='processing'):
        if self.progress_callback:
            self.progress_callback(message, current, total, status)

    def scrape_products(self, start_page=1, end_page=50, chunk_size=10):
        """Scrape products with progress tracking and cancellation support"""
        base_url = 'https://acdc.co.za/2-home'
        all_products = []
        total_pages = end_page - start_page + 1
        pages_processed = 0

        for chunk_start in range(start_page, end_page + 1, chunk_size):
            if self.cancel_event.is_set():
                self._emit_progress("Sync cancelled", pages_processed, total_pages, 'info')
                break

            chunk_end = min(chunk_start + chunk_size - 1, end_page)
            self._emit_progress(f"Processing pages {chunk_start} to {chunk_end}", 
                              pages_processed, total_pages)

            chunk_products = []
            for page_num in range(chunk_start, chunk_end + 1):
                if self.cancel_event.is_set():
                    break

                try:
                    page_url = f'{base_url}?page={page_num}'
                    self._emit_progress(f"Scraping page {page_num}", pages_processed, total_pages)
                    
                    content = self._get_page_with_retry(page_url)
                    if not content:
                        continue

                    soup = BeautifulSoup(content, 'html.parser')
                    products = self._process_page(soup, page_num)
                    if products:
                        chunk_products.extend(products)
                        self._emit_progress(f"Found {len(products)} products on page {page_num}", 
                                          pages_processed, total_pages, 'success')

                    pages_processed += 1
                    if not self.cancel_event.is_set():
                        time.sleep(random.uniform(1.5, 3))

                except Exception as e:
                    self._emit_progress(f"Error on page {page_num}: {str(e)}", 
                                      pages_processed, total_pages, 'error')
                    continue

            if chunk_products:
                all_products.extend(chunk_products)
                self._save_chunk(chunk_products, chunk_start, chunk_end)

            if not self.cancel_event.is_set():
                time.sleep(random.uniform(5, 8))

        return all_products

    def _get_page_with_retry(self, url, max_retries=5, initial_delay=3):
        headers = {'User-Agent': random.choice(self.user_agents)}
        
        for attempt in range(max_retries):
            if self.cancel_event.is_set():
                return None

            try:
                response = self.session.get(url, headers=headers, timeout=30)
                response.raise_for_status()
                return response.content

            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    raise
                delay = initial_delay * (2 ** attempt) + random.uniform(0, 1)
                self._emit_progress(f"Retry {attempt + 1}/{max_retries} for {url}. Waiting {delay:.1f}s", 
                                  0, 1, 'info')
                time.sleep(delay)

    # [Previous helper methods remain the same]
    # _process_page, _extract_product_data, _clean_title, etc.

def scrape_acdc_products(start_page=1, end_page=50, progress_callback=None, cancel_event=None):
    """Wrapper function for compatibility"""
    scraper = ACDCScraper(progress_callback, cancel_event)
    return scraper.scrape_products(start_page, end_page)

def save_to_csv(products, filename=None):
    """Save products to CSV with timestamp"""
    if not filename:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'/tmp/acdc_products_{timestamp}.csv'
    
    df = pd.DataFrame(products)
    df.to_csv(filename, index=False)
    return filename
