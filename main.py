from flask import Flask, request, jsonify, send_file, render_template
from flask_socketio import SocketIO, emit
import pandas as pd
from datetime import datetime
import os
import time
import json
import logging
from threading import Event, Thread
import threading
from price_monitor import PriceMonitor
import traceback

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask with correct template folder
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'templates')
app = Flask(__name__, template_folder=template_dir)

logger.info(f"Template directory: {template_dir}")

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')

# Configure SocketIO
socketio = SocketIO(
    app, 
    cors_allowed_origins="*", 
    async_mode='eventlet', 
    logger=True, 
    engineio_logger=True,
    ping_timeout=120,
    ping_interval=15,
    max_http_buffer_size=1e8,
    async_handlers=True
)

# Constants
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID', '1VDmG5diadJ1hNdv6ZnHfT1mVTGFM-xejWKe_ACWiuRo')
cancel_event = Event()
DEFAULT_MARKUP = 40  # Default 40% markup

def emit_progress(message, current, total, status='processing'):
    """Emit progress updates to the client"""
    try:
        percentage = int((current / total) * 100) if total > 0 else 0
        socketio.emit('sync_progress', {
            'message': message,
            'current': current,
            'total': total,
            'percentage': percentage,
            'status': status,
            'timestamp': time.time()
        }, namespace='/')
    except Exception as e:
        logger.error(f"Error emitting progress: {e}")

def start_heartbeat():
    """Start heartbeat thread"""
    def heartbeat():
        while not cancel_event.is_set():
            try:
                socketio.emit('heartbeat', {
                    'timestamp': time.time(),
                    'status': 'alive'
                }, namespace='/')
                time.sleep(10)
            except Exception as e:
                logger.error(f"Heartbeat error: {e}")
                break

    thread = Thread(target=heartbeat)
    thread.daemon = True
    thread.start()
    return thread

@app.route('/monitor/test-connection')
def test_monitor_connection():
    """Test Google Sheets connection"""
    try:
        logger.info("Testing Google Sheets connection")
        monitor = PriceMonitor(SPREADSHEET_ID)
        if monitor.test_connection():
            logger.info("Successfully connected to Google Sheets")
            return jsonify({
                'success': True,
                'message': 'Successfully connected to Google Sheets'
            })
        logger.error("Failed to connect to Google Sheets")
        return jsonify({
            'success': False,
            'message': 'Failed to connect to Google Sheets'
        })
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/monitor/check-prices')
def check_prices():
    """Check prices for products"""
    try:
        logger.info("Starting price check process")
        markup_percentage = float(request.args.get('markup', DEFAULT_MARKUP))
        monitor = PriceMonitor(SPREADSHEET_ID)
        
        # Test connection first
        if not monitor.test_connection():
            logger.error("Failed to connect to Google Sheets")
            return jsonify({
                'success': False,
                'message': 'Failed to connect to Google Sheets'
            })

        # Reset cancel event
        cancel_event.clear()

        # Start checking prices in background
        def update_task():
            try:
                # Start heartbeat
                heartbeat_thread = start_heartbeat()

                # Emit starting status
                emit_progress('Starting price check...', 0, 100, 'processing')

                # Get price updates with markup
                results = monitor.check_all_prices(markup_percentage)
                
                # Stop heartbeat
                cancel_event.set()
                heartbeat_thread.join(timeout=1)

                # Emit completion status
                emit_progress(
                    f"Updated {results['updated']} prices, {results['failed']} failed",
                    100,
                    100,
                    'success' if results['updated'] > 0 else 'error'
                )

            except Exception as e:
                logger.error(f"Price check failed: {e}")
                logger.error(traceback.format_exc())
                emit_progress(
                    f'Error: {str(e)}',
                    0,
                    100,
                    'error'
                )
                # Ensure heartbeat stops
                cancel_event.set()

        # Start the background task
        thread = Thread(target=update_task)
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'message': 'Price check started'
        })
        
    except Exception as e:
        logger.error(f"Price check failed: {e}")
        logger.error(traceback.format_exc())
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/cancel', methods=['POST'])
def cancel_sync():
    """Cancel ongoing sync"""
    try:
        cancel_event.set()
        return jsonify({'success': True, 'message': 'Sync cancelled'})
    except Exception as e:
        logger.error(f"Cancel sync failed: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/')
def index():
    """Landing page"""
    try:
        logger.info("Attempting to render index.html")
        logger.info(f"Current working directory: {os.getcwd()}")
        logger.info(f"Template folder: {app.template_folder}")
        return render_template('index.html', default_markup=DEFAULT_MARKUP)
    except Exception as e:
        logger.error(f"Error rendering template: {e}")
        logger.error(traceback.format_exc())
        return f"Template error: {str(e)}", 500

if __name__ == '__main__':
    logger.info(f"Starting server with template directory: {template_dir}")
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)
