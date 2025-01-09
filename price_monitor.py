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

    def wait_for_rate_limit(self):
        """Ensure minimum time between updates"""
        current_time = time.time()
        time_since_last_update = current_time - self.last_update_time
        if time_since_last_update < self.min_time_between_updates:
            sleep_time = self.min_time_between_updates - time_since_last_update
            logger.debug(f"Rate limiting: sleeping for {sleep_time:.2f} seconds")
            time.sleep(sleep_time)
        self.last_update_time = time.time()

    def get_skus_from_sheet(self):
        """Get list of SKUs from sheet"""
        try:
            result = self.sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range='A2:A'
            ).execute()
            
            if not result.get('values'):
                logger.warning("No SKUs found in sheet")
                return []
            
            skus = [row[0] for row in result['values'] if row]
            logger.info(f"Found {len(skus)} SKUs in sheet")
            return skus
            
        except Exception as e:
            logger.error(f"Error getting SKUs: {e}")
            logger.debug(f"Get SKUs traceback: {traceback.format_exc()}")
            return []

    def update_batch(self, batch_data, start_row):
        """Update a batch of rows in the sheet"""
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                self.wait_for_rate_limit()
                
                range_name = f'A{start_row}:G{start_row + len(batch_data) - 1}'
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

    def process_updates(self, price_data):
        """Process updates in batches"""
        results = defaultdict(int)
        results['errors'] = []
        
        try:
            all_updates = []
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            for sku, data in price_data.items():
                row_data = [
                    sku,                                    # Column A: SKU
                    str(data.get('price', 0)),             # Column B: Price
                    data.get('timestamp', timestamp),       # Column C: Timestamp
                    data.get('source', 'ACDC Dynamics'),    # Column D: Source
                    'Updated',                             # Column E: Status
                    '',                                    # Column F: Reserved
                    ''                                     # Column G: Reserved
                ]
                all_updates.append(row_data)

            # Process in batches
            for i in range(0, len(all_updates), self.batch_size):
                batch = all_updates[i:i + self.batch_size]
                start_row = 2 + i  # Start from row 2 (after header)
                
                if self.update_batch(batch, start_row):
                    results['updated'] += len(batch)
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

    def check_all_prices(self):
        """Main method to check and update all prices"""
        try:
            # Get SKUs from sheet
            skus = self.get_skus_from_sheet()
            if not skus:
                return {
                    'updated': 0,
                    'failed': 0,
                    'errors': ['No SKUs found in sheet']
                }

            # Get prices using crawler
            logger.info(f"Starting price check for {len(skus)} SKUs")
            price_data = self.crawler.targeted_crawl(skus)
            
            if not price_data:
                return {
                    'updated': 0,
                    'failed': len(skus),
                    'errors': ['No prices found']
                }
            
            # Process updates in batches
            results = self.process_updates(price_data)
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

if __name__ == "__main__":
    # Test the monitor
    SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID')
    if SPREADSHEET_ID:
        monitor = PriceMonitor(SPREADSHEET_ID)
        if monitor.test_connection():
            results = monitor.check_all_prices()
            print("Update Results:", results)
    else:
        print("SPREADSHEET_ID environment variable not set")
