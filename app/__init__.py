# app/__init__.py
from flask import Flask
from celery import Celery
import os
from app.config import REDIS_URL

# Initialize Flask app
app = Flask(__name__)

# Initialize Celery with Redis configuration
celery = Celery(
    'app',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['app.tasks']
)

# Celery configuration
celery.conf.update(
    result_expires=3600,  # Results expire in 1 hour
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=50,
    task_track_started=True
)

# Import routes after app initialization to avoid circular imports
from app import main
