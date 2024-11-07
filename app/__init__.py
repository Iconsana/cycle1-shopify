from flask import Flask
from celery import Celery
import os

# Initialize Flask app
app = Flask(__name__)

# Get Redis URL from environment
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Initialize Celery with the correct Redis URL
celery = Celery(
    'tasks',
    broker=REDIS_URL,
    backend=REDIS_URL
)

# Import routes after app initialization
from app import main
