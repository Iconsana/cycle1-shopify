import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pandas as pd
from bs4 import BeautifulSoup
import requests
import time
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class PriceMonitor:
    def __init__(self, credentials_file, spreadsheet_id):
        self.spreadsheet_id = spreadsheet_id
        try:
            self.credentials = service_account.Credentials.from_service_account_file(
                credentials_file,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            self.service = build('sheets', 'v4', credentials=self.credentials)
            self.sheet = self.service.spreadsheets()
            logger.info("Successfully initialized Google Sheets connection")
        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            raise

    def test_connection(self):
        """Test the connection to Google Sheets"""
        try:
            # Try to read the sheet title
            result = self.sheet.get(spreadsheetId=self.spreadsheet_id).execute()
            logger.info(f"Successfully connected to sheet: {result['properties']['title']}")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def get_acdc_price(self, sku):
        """Get price from ACDC website"""
        try:
            search_url = f"https://acdc.co.za/search?controller=search&s={sku}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            logger.info(f"Searching for SKU: {sku}")
            response = requests.get(search_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                price_elem = soup.select_one(".price")  # Adjust selector as needed
                
                if price_elem:
                    price_text = price_elem.text.strip()
                    # Clean up price text and convert to float
                    price = float(price_text.replace('R', '').replace(',', '').strip())
                    logger.info(f"Found price for {sku}: R{price}")
                    return price
                else:
                    logger.warning(f"No price element found for {sku}")
                    return None
            else:
                logger.error(f"Failed to fetch page: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting price for {sku}: {e}")
            return None

    def update_single_product(self, row_number, sku):
        """Test update for a single product"""
        try:
            # Get current values
            range_name = f'A{row_number}:G{row_number}'
            result = self.sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()
            
            current_values = result.get('values', [[]])[0]
            current_price = float(current_values[2]) if len(current_values) > 2 else 0
            
            # Get new price
            acdc_price = self.get_acdc_price(sku)
            
            if acdc_price:
                price_diff = round(current_price - acdc_price, 2)
                status = 'Price Changed' if abs(price_diff) > 0.01 else 'Up to Date'
                
                # Prepare update values
                values = [
                    [sku, 
                    current_values[1] if len(current_values) > 1 else '',
                    str(current_price),
                    str(acdc_price),
                    str(price_diff),
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    status]
                ]
                
                # Update sheet
                body = {
                    'values': values
                }
                self.sheet.values().update(
                    spreadsheetId=self.spreadsheet_id,
                    range=range_name,
                    valueInputOption='USER_ENTERED',
                    body=body
                ).execute()
                
                logger.info(f"Successfully updated {sku} - Status: {status}")
                return True
            else:
                logger.warning(f"No price found for {sku}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating product {sku}: {e}")
            return False

def main():
    # Configuration
    CREDENTIALS_FILE = 'cycle1-price-monitor-e2948349fb68.json'
    SPREADSHEET_ID = '1VDmG5diadJ1hNdv6ZnHfT1mVTGFM-xejWKe_ACWiuRo'
    
    try:
        # Initialize monitor
        monitor = PriceMonitor(CREDENTIALS_FILE, SPREADSHEET_ID)
        
        # Test connection
        if not monitor.test_connection():
            logger.error("Failed to connect to Google Sheets")
            return
            
        # Test with first product (row 2)
        test_sku = "A0001/3/230-NS"  # First product SKU
        success = monitor.update_single_product(2, test_sku)
        
        if success:
            logger.info("Test completed successfully")
        else:
            logger.error("Test failed")
            
    except Exception as e:
        logger.error(f"Main execution failed: {e}")

if __name__ == "__main__":
    main()
