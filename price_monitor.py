from google.oauth2 import service_account
from googleapiclient.discovery import build
import pandas as pd
from bs4 import BeautifulSoup
import requests
import time
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PriceMonitor:
    def __init__(self, credentials_file, spreadsheet_id):
        self.spreadsheet_id = spreadsheet_id
        self.credentials = service_account.Credentials.from_service_account_file(
            credentials_file,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )
        self.service = build('sheets', 'v4', credentials=self.credentials)
        self.sheet = self.service.spreadsheets()

    def read_products(self):
        """Read products from Google Sheet"""
        try:
            result = self.sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range='A2:G'  # Skip header row
            ).execute()
            values = result.get('values', [])
            logger.info(f"Read {len(values)} products from sheet")
            return values
        except Exception as e:
            logger.error(f"Error reading from sheet: {e}")
            return []

    def get_acdc_price(self, sku, title):
        """Scrape price from ACDC website"""
        try:
            # Search URL with SKU
            search_url = f"https://acdc.co.za/search?controller=search&s={sku}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(search_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            products = soup.select(".product-miniature")
            
            for product in products:
                # Find product by SKU
                product_sku = product.select_one(".product-reference")
                if product_sku and sku.lower() in product_sku.text.strip().lower():
                    price_elem = product.select_one(".price")
                    if price_elem:
                        price_text = price_elem.text.strip()
                        # Convert price text to float
                        price = float(price_text.replace('R', '').replace(',', '').strip())
                        return price
            
            return None
        except Exception as e:
            logger.error(f"Error getting price for {sku}: {e}")
            return None

    def update_sheet(self, row, values):
        """Update a row in the Google Sheet"""
        try:
            range_name = f'A{row}:G{row}'
            body = {
                'values': [values]
            }
            self.sheet.values().update(
                spreadsheetId=self.spreadsheet_id,
                range=range_name,
                valueInputOption='USER_ENTERED',
                body=body
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Error updating sheet: {e}")
            return False

    def check_prices(self):
        """Main function to check and update prices"""
        products = self.read_products()
        
        for i, product in enumerate(products, start=2):  # Start from row 2
            try:
                sku = product[0]
                title = product[1]
                current_price = float(product[2])
                
                logger.info(f"Checking price for {sku}")
                acdc_price = self.get_acdc_price(sku, title)
                
                if acdc_price:
                    price_diff = round(current_price - acdc_price, 2)
                    status = 'Price Changed' if abs(price_diff) > 0.01 else 'Up to Date'
                    
                    # Update sheet with new values
                    values = [
                        sku,
                        title,
                        str(current_price),
                        str(acdc_price),
                        str(price_diff),
                        datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        status
                    ]
                    
                    self.update_sheet(i, values)
                    logger.info(f"Updated {sku} - Status: {status}")
                
                # Add delay between requests
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error processing row {i}: {e}")
                continue

# Example usage
if __name__ == "__main__":
    CREDENTIALS_FILE = 'cycle1-price-monitor-e2948349fb68.json'
    SPREADSHEET_ID = 'your_spreadsheet_id_here'  # Get this from your Google Sheet URL
    
    monitor = PriceMonitor(CREDENTIALS_FILE, SPREADSHEET_ID)
    monitor.check_prices()
