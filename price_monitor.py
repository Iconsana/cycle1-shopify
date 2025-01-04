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
from crawler import ACDCCrawler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PriceMonitor:
    def __init__(self, spreadsheet_id):
        self.spreadsheet_id = spreadsheet_id
        self.crawler = ACDCCrawler()
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

    def get_skus_from_sheet(self):
        """Get list of SKUs from sheet"""
        try:
            result = self.sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range='A2:A'  # Skip header row
            ).execute()
            
            if not result.get('values'):
                logger.error("No SKUs found in sheet")
                return []
                
            return [row[0] for row in result['values']]
        except Exception as e:
            logger.error(f"Error getting SKUs: {e}")
            return []

    def update_single_product(self, row_number, sku):
        """Update a single product's price in sheet (legacy method)"""
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
            
            # Get new price from ACDC using crawler
            crawler_results = self.crawler.targeted_crawl([sku])
            acdc_price = crawler_results.get(sku, {}).get('price')
            
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
            logger.error(f"Error updating {sku}: {e}")
            return False

    def update_prices(self):
        """Update all prices using targeted crawler"""
        try:
            # Get SKUs from sheet
            skus = self.get_skus_from_sheet()
            if not skus:
                return {
                    'updated': 0,
                    'failed': 0,
                    'errors': ['No SKUs found in sheet']
                }
            
            # Get prices using targeted crawler
            results = self.crawler.targeted_crawl(skus)
            
            updates = {
                'updated': 0,
                'failed': 0,
                'errors': []
            }
            
            # Update each SKU in sheet
            for row_num, sku in enumerate(skus, start=2):
                if sku in results:
                    if self.update_single_product(row_num, sku):
                        updates['updated'] += 1
                    else:
                        updates['failed'] += 1
                        updates['errors'].append(f"Failed to update {sku} in sheet")
                else:
                    updates['failed'] += 1
                    updates['errors'].append(f"No price found for {sku}")
            
            return updates
            
        except Exception as e:
            logger.error(f"Price update error: {e}")
            return {
                'updated': 0,
                'failed': 0,
                'errors': [str(e)]
            }

    def check_all_prices(self):
        """Check prices for all products"""
        return self.update_prices()
