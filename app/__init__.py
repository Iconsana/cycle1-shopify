
from flask import Flask
from celery import Celery

# Initialize Flask app
app = Flask(__name__)

# Initialize Celery
celery = Celery(
    'tasks',
    broker='redis://localhost:6379/0',
    backend='redis://localhost:6379/0'
)

# Import routes after app initialization
from app import main
