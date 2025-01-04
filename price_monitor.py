import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pandas as pd
from bs4 import BeautifulSoup
import requests
import time
from datetime import datetime
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PriceMonitor:
    def __init__(self, spreadsheet_id):
        self.spreadsheet_id = spreadsheet_id
        try:
            # Get credentials from environment variable
            credentials_json = os.environ.get('GOOGLE_CREDENTIALS')
            if not credentials_json:
                logger.error("GOOGLE_CREDENTIALS not found in environment variables")
                raise ValueError("GOOGLE_CREDENTIALS environment variable not set")
                
            logger.info("Found credentials in environment variables")
            
            credentials_info = json.loads(credentials_json)
            self.credentials = service_account.Credentials.from_service_account_info(
                credentials_info,
                scopes=['https://www.googleapis.com/auth/spreadsheets']
            )
            self.service = build('sheets', 'v4', credentials=self.credentials)
            self.sheet = self.service.spreadsheets()
            logger.info("Successfully initialized Google Sheets connection")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON format in credentials: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to initialize: {e}")
            raise

    def test_connection(self):
        """Test connection to Google Sheets"""
        try:
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
            
            response = requests.get(search_url, headers=headers, timeout=30)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                price_elem = soup.select_one(".price")
                
                if price_elem:
                    price_text = price_elem.text.strip()
                    price = float(price_text.replace('R', '').replace(',', '').strip())
                    logger.info(f"Found price for {sku}: R{price}")
                    return price
                    
            logger.warning(f"No price found for {sku}")
            return None
                
        except Exception as e:
            logger.error(f"Error getting price for {sku}: {e}")
            return None

    def update_single_product(self, row_number, sku):
        """Update a single product's price"""
        try:
            # Get current values
            range_name = f'A{row_number}:G{row_number}'
            result = self.sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range=range_name
            ).execute()
            
            if not result.get('values'):
                logger.error(f"No data found for row {row_number}")
                return False
                
            current_values = result['values'][0]
            current_price = float(current_values[2]) if len(current_values) > 2 else 0
            
            # Get new price from ACDC
            acdc_price = self.get_acdc_price(sku)
            
            if acdc_price is not None:
                # Calculate difference and status
                price_diff = round(current_price - acdc_price, 2)
                status = 'Price Changed' if abs(price_diff) > 0.01 else 'Up to Date'
                
                # Prepare update values
                values = [[
                    sku,
                    current_values[1] if len(current_values) > 1 else '',
                    str(current_price),
                    str(acdc_price),
                    str(price_diff),
                    datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    status
                ]]
                
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
                
                logger.info(f"Updated {sku} - Status: {status}")
                return True
            
            return False
                
        except Exception as e:
            logger.error(f"Error updating product {sku}: {e}")
            return False

    def check_all_prices(self):
        """Check prices for all products"""
        results = {
            'updated': 0,
            'failed': 0,
            'errors': []
        }
        
        try:
            # Get all SKUs
            result = self.sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range='A2:A'  # Skip header row
            ).execute()
            
            if not result.get('values'):
                logger.error("No products found in sheet")
                return results
                
            for row_num, row in enumerate(result['values'], start=2):
                try:
                    sku = row[0]
                    if self.update_single_product(row_num, sku):
                        results['updated'] += 1
                    else:
                        results['failed'] += 1
                        results['errors'].append(f"Failed to update {sku}")
                    
                    # Add delay between requests
                    time.sleep(2)
                    
                except Exception as e:
                    results['failed'] += 1
                    results['errors'].append(f"Error processing {sku}: {str(e)}")
                    
            return results
            
        except Exception as e:
            logger.error(f"Error checking all prices: {e}")
            return results
