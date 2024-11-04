import os
from dotenv import load_dotenv

load_dotenv()

# Existing config
SHOPIFY_API_KEY = os.getenv('SHOPIFY_API_KEY')
SHOPIFY_API_SECRET = os.getenv('SHOPIFY_API_SECRET')
SHOP_NAME = os.getenv('SHOP_NAME', 'cycle1-test')
API_VERSION = os.getenv('API_VERSION', '2023-01')
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')

# New config for Celery
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

# Redis config
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# API URLs
SHOPIFY_API_URL = f"https://{SHOP_NAME}.myshopify.com/admin/api/{API_VERSION}/products.json"
