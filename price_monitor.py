import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
import time
from datetime import datetime
import logging
import json
import traceback
from crawler import ACDCCrawler
from collections import defaultdict

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class PriceMonitor:
    def __init__(self, spreadsheet_id):
        logger.debug(f"Initializing PriceMonitor with spreadsheet_id: {spreadsheet_id}")
        self.spreadsheet_id = spreadsheet_id
        self.crawler = ACDCCrawler()
        
        # Batch and rate limiting settings
        self.batch_size = 30  # Update 30 rows at a time
        self.min_time_between_updates = 2  # Minimum seconds between batch updates
        self.last_update_time = 0
        
        try:
            credentials_json = os.environ.get('GOOGLE_CREDENTIALS')
            if not credentials_json:
                raise ValueError("GOOGLE_CREDENTIALS environment variable not set")
                
            credentials_info = json.loads(credentials_json)
            self.credentials = service_account.Credentials.from_service_account_info(
                credentials_info,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            self.service = build('sheets', 'v4', credentials=self.credentials)
            self.sheet = self.service.spreadsheets()
            logger.info("Successfully initialized Google Sheets connection")
            
        except Exception as e:
            logger.error(f"Initialization error: {e}")
            logger.debug(f"Initialization traceback: {traceback.format_exc()}")
            raise

    def calculate_variant_price(self, acdc_price, markup_percentage):
        """Calculate variant price with markup and VAT"""
        try:
            markup_multiplier = 1 + (markup_percentage / 100)
            base_price = float(acdc_price) * markup_multiplier  # Apply markup
            variant_price = base_price * 1.15  # Add 15% VAT
            return round(variant_price, 2)
        except Exception as e:
            logger.error(f"Error calculating variant price: {e}")
            return 0

    def wait_for_rate_limit(self):
        """Ensure minimum time between updates"""
        current_time = time.time()
        time_since_last_update = current_time - self.last_update_time
        if time_since_last_update < self.min_time_between_updates:
            sleep_time = self.min_time_between_updates - time_since_last_update
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        self.last_update_time = time.time()

    def get_skus_and_data(self):
        """Get SKUs and their current data from sheet"""
        try:
            result = self.sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range='A2:C'  # Get SKU and Current Price columns
            ).execute()
            
            if not result.get('values'):
                logger.warning("No SKUs found in sheet")
                return {}
            
            sku_data = {}
            for row in result['values']:
                if len(row) >= 1:  # Ensure at least SKU exists
                    sku = row[0]
                    title = row[1] if len(row) > 1 else ''
                    current_price = float(row[2]) if len(row) > 2 and row[2] else 0
                    sku_data[sku] = {
                        'title': title,
                        'current_price': current_price
                    }
            
            logger.info(f"Found {len(sku_data)} SKUs with data in sheet")
            return sku_data
            
        except Exception as e:
            logger.error(f"Error getting SKUs and data: {e}")
            logger.debug(f"Get SKUs traceback: {traceback.format_exc()}")
            return {}

    def update_batch(self, batch_data, start_row):
        """Update a batch of rows in the sheet"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                self.wait_for_rate_limit()
                
                range_name = f'A{start_row}:H{start_row + len(batch_data) - 1}'  # Updated to include Variant Price
                body = {'values': batch_data}
                
                logger.debug(f"Updating range: {range_name} with {len(batch_data)} rows")
                
                self.sheet.values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_name,
                    valueInputOption='USER_ENTERED',
                    body=body
                ).execute()
                
                logger.info(f"Successfully updated batch of {len(batch_data)} rows")
                return True
                
            except Exception as e:
                if 'RATE_LIMIT_EXCEEDED' in str(e):
                    wait_time = retry_delay * (2 ** attempt)
                    logger.warning(f"Rate limit exceeded, waiting {wait_time} seconds before retry")
                    time.sleep(wait_time)
                    continue
                    
                logger.error(f"Batch update error (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    return False
                    
                time.sleep(retry_delay * (2 ** attempt))
        
        return False

    def process_updates(self, price_data, sku_data, markup_percentage):
        """Process updates in batches"""
        results = defaultdict(int)
        results['errors'] = []
        
        try:
            all_updates = []
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            for sku, data in price_data.items():
                existing_data = sku_data.get(sku, {})
                current_price = existing_data.get('current_price', 0)
                title = existing_data.get('title', '')
                new_price = data.get('price', 0)
                price_difference = round(current_price - new_price, 2) if current_price and new_price else 0
                variant_price = self.calculate_variant_price(new_price, markup_percentage)
                
                row_data = [
                    sku,                    # A: SKU
                    title,                  # B: Title
                    str(current_price),     # C: Current Price
                    str(new_price),         # D: ACDC Price
                    str(price_difference),  # E: Price Difference
                    timestamp,              # F: Last Checked
                    'ACDC Dynamic Updated', # G: Status
                    str(variant_price)      # H: Variant Price
                ]
                all_updates.append(row_data)
                logger.debug(f"Prepared update for SKU {sku}: Current: {current_price}, New: {new_price}, Variant: {variant_price}")

            # Process in batches
            for i in range(0, len(all_updates), self.batch_size):
                batch = all_updates[i:i + self.batch_size]
                start_row = 2 + i  # Start from row 2 (after header)
                
                if self.update_batch(batch, start_row):
                    results['updated'] += len(batch)
                    logger.info(f"Successfully updated batch {i//self.batch_size + 1}")
                else:
                    results['failed'] += len(batch)
                    batch_skus = [row[0] for row in batch]
                    error_msg = f"Failed to update batch with SKUs: {', '.join(batch_skus)}"
                    results['errors'].append(error_msg)
                    logger.error(error_msg)

            return dict(results)
            
        except Exception as e:
            logger.error(f"Process updates error: {e}")
            logger.debug(f"Process updates traceback: {traceback.format_exc()}")
            results['errors'].append(str(e))
            return dict(results)

    def check_all_prices(self, markup_percentage=40):
        """Main method to check and update all prices"""
        try:
            # Get SKUs and current data from sheet
            sku_data = self.get_skus_and_data()
            if not sku_data:
                logger.error("No SKUs found in sheet")
                return {
                    'updated': 0,
                    'failed': 0,
                    'errors': ['No SKUs found in sheet']
                }

            # Get prices using crawler
            logger.info(f"Starting price check for {len(sku_data)} SKUs")
            price_data = self.crawler.targeted_crawl(list(sku_data.keys()))
            
            if not price_data:
                logger.error("No prices found by crawler")
                return {
                    'updated': 0,
                    'failed': len(sku_data),
                    'errors': ['No prices found']
                }
            
            # Process updates in batches with markup
            results = self.process_updates(price_data, sku_data, markup_percentage)
            logger.info(f"Price check completed: {results}")
            return results
            
        except Exception as e:
            logger.error(f"Price check error: {e}")
            logger.debug(f"Price check traceback: {traceback.format_exc()}")
            return {
                'updated': 0,
                'failed': 0,
                'errors': [str(e)]
            }

    def test_connection(self):
        """Test connection to Google Sheets"""
        try:
            result = self.sheet.get(spreadsheetId=self.spreadsheet_id).execute()
            logger.info(f"Successfully connected to sheet: {result['properties']['title']}")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            logger.debug(f"Connection test traceback: {traceback.format_exc()}")
            return False
