# app/__init__.py
import logging
from flask import Flask
from celery import Celery
import os
from dotenv import load_dotenv

# Create Flask app immediately
app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)
logger.debug("Initializing application...")

# Load environment variables
load_dotenv()

# Get Redis URL from environment
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
logger.debug(f"Using Redis URL: {REDIS_URL}")

# Configure Flask app
app.config.update(
    CELERY_BROKER_URL=REDIS_URL,
    CELERY_RESULT_BACKEND=REDIS_URL,
    SECRET_KEY=os.getenv('SECRET_KEY', 'your-secret-key-here')
)

# Initialize Celery
celery = Celery(
    'cycle1_shopify.app',  # Note: hyphen changed to underscore
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['cycle1_shopify.app.tasks']  # Note: hyphen changed to underscore
)

# Celery configuration
celery.conf.update(
    result_expires=3600,
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
    task_track_started=True,
    broker_connection_retry_on_startup=True
)
logger.debug("Celery initialized")

# Import routes after app initialization
from cycle1_shopify.app import main  # Note: hyphen changed to underscore
logger.debug("Routes imported")
logger.info("Application initialization completed")
