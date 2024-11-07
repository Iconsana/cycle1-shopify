# app/config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Flask Configuration
SECRET_KEY = os.getenv('SECRET_KEY', 'your-secret-key-here')
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

# Redis Configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://default:cBVQaXcbrUZMvausFvgIvJQNwBjQcgNS@redis.railway.internal:6379')

# Celery Configuration
CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

# Shopify Configuration
SHOPIFY_API_KEY = os.getenv('SHOPIFY_API_KEY')
SHOPIFY_API_SECRET = os.getenv('SHOPIFY_API_SECRET')
SHOP_NAME = os.getenv('SHOP_NAME', 'cycle1-test')
API_VERSION = os.getenv('API_VERSION', '2023-01')
ACCESS_TOKEN = os.getenv('ACCESS_TOKEN')
SHOPIFY_API_URL = f"https://{SHOP_NAME}.myshopify.com/admin/api/{API_VERSION}/products.json"

# Scraping Configuration
MAX_PAGES = int(os.getenv('MAX_PAGES', '4176'))
SCRAPE_DELAY = float(os.getenv('SCRAPE_DELAY', '2.0'))  # Delay between page requests
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '10'))  # Request timeout in seconds

# File Storage Configuration
UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'exports')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)  # Create exports directory if it doesn't exist

# Logging Configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Application Configuration
MARKUP_PERCENTAGE = float(os.getenv('MARKUP_PERCENTAGE', '10.0'))  # Default 10% markup
DEFAULT_INVENTORY_QTY = int(os.getenv('DEFAULT_INVENTORY_QTY', '100'))
