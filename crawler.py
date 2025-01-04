import requests
from bs4 import BeautifulSoup
import re
from datetime import datetime
import time
import logging
import random
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

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
        try:
            # Remove 'EXCL. VAT' and other text, keep numbers, dots, and commas
            price_text = re.sub(r'[^\d,.]', '', text.replace('EXCL. VAT', ''))
            # Convert to proper decimal format
            price_text = price_text.replace(',', '.')
            # If multiple decimals, keep only the first one
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
            return re.sub(r'[^A-Z0-9-]', '', sku.upper())
        return None

    def get_price_from_url(self, url, sku):
        """Get price from a specific URL"""
        try:
            response = self.session.get(url, headers=self.headers, timeout=30)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Try to find price in stock table first
                stock_table = soup.find('table')
                if stock_table:
                    for row in stock_table.find_all('tr'):
                        if 'EDENVALE' in row.get_text():
                            cols = row.find_all('td')
                            if len(cols) >= 3:
                                price_text = cols[2].get_text().strip()
                                price = self._extract_price(price_text)
                                if price:
                                    logger.info(f"Found price for {sku} in stock table: R{price}")
                                    return price

                # Fallback to main price display
                price_elem = (
                    soup.find('span', class_='price') or 
                    soup.find('div', class_='product-price-and-shipping').find('span', class_='price')
                )
                if price_elem:
                    price = self._extract_price(price_elem.get_text())
                    if price:
                        logger.info(f"Found price for {sku} in main price: R{price}")
                        return price

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
                direct_url = f"https://acdc.co.za/product/{clean_sku.lower()}"
                price = self.get_price_from_url(direct_url, clean_sku)
                
                # If direct URL fails, try search
                if not price:
                    search_url = f"https://acdc.co.za/search?controller=search&s={clean_sku}"
                    price = self.get_price_from_url(search_url, clean_sku)
                
                if price:
                    results[clean_sku] = {
                        'price': price,
                        'timestamp': datetime.now().isoformat(),
                        'source': 'ACDC Dynamics'
                    }
                    logger.info(f"Successfully processed {clean_sku}")
                else:
                    logger.warning(f"No price found for {clean_sku}")
                
                # Random delay between requests
                time.sleep(random.uniform(1, 2))
                
            except Exception as e:
                logger.error(f"Error processing {sku}: {e}")
                continue
        
        logger.info(f"Crawl completed. Found prices for {len(results)}/{total_skus} SKUs")
        return results

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Test crawler with some SKUs
    crawler = ACDCCrawler()
    test_skus = [
        "LEDT8-A4FR-DL",
        "HS-B22-10W-DL"
    ]
    results = crawler.targeted_crawl(test_skus)
    
    # Print results
    for sku, data in results.items():
        print(f"SKU: {sku}")
        print(f"Price: R{data['price']}")
        print(f"Timestamp: {data['timestamp']}")
        print("---")
