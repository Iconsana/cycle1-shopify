# app/__init__.py
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

logger.debug("Initializing application...")

from flask import Flask
from celery import Celery
import os

# Initialize Flask app
app = Flask(__name__)
logger.debug("Flask app created")

# Rest of your code...
