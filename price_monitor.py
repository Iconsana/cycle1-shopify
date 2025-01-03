import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pandas as pd
from bs4 import BeautifulSoup
import requests
import time
from datetime import datetime
import logging
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PriceMonitor:
    def __init__(self, credentials_file, spreadsheet_id):
        self.spreadsheet_id = spreadsheet_id
        self.credentials_file = credentials_file
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
            result = self.sheet.get(spreadsheetId=self.spreadsheet_id).execute()
            logger.info(f"Successfully connected to sheet: {result['properties']['title']}")
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def read_products(self):
        """Read all products from Google Sheet"""
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

    def clean_price(self, price_str):
        """Clean price string to float"""
        try:
            # Remove currency symbol, spaces, and commas
            price_str = price_str.replace('R', '').replace(',', '').strip()
            # Remove any other non-numeric characters except decimal point
            price_str = re.sub(r'[^\d.]', '', price_str)
            return float(price_str)
        except Exception as e:
            logger.error(f"Error cleaning price {price_str}: {e}")
            return 0.0

    def get_acdc_price(self, sku):
        """Get price from ACDC website"""
        try:
            url = f"https://acdc.co.za/search?controller=search&s={sku}"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            if response.status_code != 200:
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            products = soup.select(".product-miniature")
            
            for product in products:
                product_sku = product.select_one(".product-reference")
                if product_sku and sku.lower() in product_sku.text.strip().lower():
                    price_elem = product.select_one(".price")
                    if price_elem:
                        return self.clean_price(price_elem.text)
            
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
            else:
                logger.warning(f"No price found for {sku}")
                return False
                
        except Exception as e:
            logger.error(f"Error updating product {sku}: {e}")
            return False

    def check_all_prices(self):
        """Check prices for all products"""
        products = self.read_products()
        results = {
            'updated': 0,
            'failed': 0,
            'errors': []
        }
        
        for index, product in enumerate(products, start=2):  # Start from row 2
            try:
                sku = product[0]
                if self.update_single_product(index, sku):
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

    def get_row_by_sku(self, sku):
        """Find row number for a given SKU"""
        try:
            result = self.sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range='A:A'
            ).execute()
            
            values = result.get('values', [])
            for i, row in enumerate(values):
                if row and row[0] == sku:
                    return i + 1  # Add 1 because sheet rows are 1-based
            
            return None
            
        except Exception as e:
            logger.error(f"Error finding row for SKU {sku}: {e}")
            return None
