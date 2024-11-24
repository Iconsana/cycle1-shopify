from flask import Flask
from flask_session import Session
import os
from .routes import init_routes
import shopify

def create_app():
    """Initialize the core application"""
    app = Flask(__name__)
    
    # Configure Flask app
    app.config.update(
        SECRET_KEY=os.environ.get('SECRET_KEY'),
        SESSION_TYPE='filesystem',
        SHOPIFY_API_KEY=os.environ.get('SHOPIFY_API_KEY'),
        SHOPIFY_API_SECRET=os.environ.get('SHOPIFY_API_SECRET')
    )
    
    # Initialize session
    Session(app)
    
    # Initialize Shopify
    shopify.Session.setup(
        api_key=os.environ.get('SHOPIFY_API_KEY'),
        secret=os.environ.get('SHOPIFY_API_SECRET')
    )
    
    # Register routes
    init_routes(app)
    
    @app.route('/')
    def index():
        """Landing page"""
        return app.send_static_file('index.html')
    
    return app
