# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# Load credentials from environment variables
SHOPIFY_API_KEY = os.getenv('SHOPIFY_API_KEY')
SHOPIFY_API_SECRET = os.getenv('SHOPIFY_API_SECRET')
SHOP_NAME = os.getenv('SHOP_NAME', 'cycle1-test')
API_VERSION = os.getenv('API_VERSION', '2023-01')
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')

# Construct the API URL
SHOPIFY_API_URL = f"https://{SHOP_NAME}.myshopify.com/admin/api/{API_VERSION}/products.json"
