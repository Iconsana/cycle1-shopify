from flask import Flask, request, jsonify, send_file, render_template
from flask_socketio import SocketIO, emit
import pandas as pd
from datetime import datetime
import os
from scraper import scrape_acdc_products, save_to_csv
import shopify
import time
import json
from threading import Event, Thread
import threading
from price_monitor import PriceMonitor
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask with correct template folder
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'templates')
app = Flask(__name__, template_folder=template_dir)

# Log template directory for debugging
logger.info(f"Template directory: {template_dir}")

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')

# Configure SocketIO with increased timeout
socketio = SocketIO(
    app, 
    cors_allowed_origins="*", 
    async_mode='eventlet', 
    logger=True, 
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25
)

# Constants
SPREADSHEET_ID = os.environ.get('SPREADSHEET_ID', '1VDmG5diadJ1hNdv6ZnHfT1mVTGFM-xejWKe_ACWiuRo')
cancel_event = Event()

def emit_progress(message, current, total, status='processing'):
    """Emit progress updates to the client"""
    try:
        percentage = int((current / total) * 100) if total > 0 else 0
        socketio.emit('sync_progress', {
            'message': message,
            'current': current,
            'total': total,
            'percentage': percentage,
            'status': status
        })
    except Exception as e:
        logger.error(f"Error emitting progress: {e}")

def generate_csv():
    """Generate CSV from scraped products"""
    try:
        start_page = int(request.form.get('start_page', 1))
        end_page = int(request.form.get('end_page', 50))
        
        if start_page < 1 or end_page > 4331:
            raise ValueError("Invalid page range")
        if start_page > end_page:
            raise ValueError("Start page must be less than end page")
        
        products = scrape_acdc_products(
            start_page=start_page,
            end_page=end_page,
            progress_callback=emit_progress,
            cancel_event=cancel_event
        )
        
        if products:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = os.path.join('/tmp', f'acdc_products_{start_page}_to_{end_page}_{timestamp}.csv')
            saved_file = save_to_csv(products, filename)
            
            emit_progress(
                f'Scraping completed! Found {len(products)} products',
                end_page - start_page + 1,
                end_page - start_page + 1,
                'success'
            )
            
            return saved_file
    except Exception as e:
        emit_progress(
            f'Error: {str(e)}',
            0,
            100,
            'error'
        )
        return None

# Routes
@app.route('/monitor/test-connection')
def test_monitor_connection():
    """Test Google Sheets connection"""
    try:
        monitor = PriceMonitor(SPREADSHEET_ID)
        if monitor.test_connection():
            return jsonify({
                'success': True,
                'message': 'Successfully connected to Google Sheets'
            })
        return jsonify({
            'success': False,
            'message': 'Failed to connect to Google Sheets'
        })
    except Exception as e:
        logger.error(f"Connection test failed: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/monitor/check-prices')
def check_prices():
    """Check prices for products"""
    try:
        monitor = PriceMonitor(SPREADSHEET_ID)
        
        # Test connection first
        if not monitor.test_connection():
            return jsonify({
                'success': False,
                'message': 'Failed to connect to Google Sheets'
            })

        # Start checking prices in background
        def update_task():
            try:
                # Emit starting status
                socketio.emit('sync_progress', {
                    'message': 'Starting price check...',
                    'current': 0,
                    'total': 100,
                    'percentage': 0,
                    'status': 'processing'
                })

                results = monitor.check_all_prices()
                
                # Emit completion status
                socketio.emit('sync_progress', {
                    'message': f"Updated {results['updated']} prices, {results['failed']} failed",
                    'current': 100,
                    'total': 100,
                    'percentage': 100,
                    'status': 'success' if results['updated'] > 0 else 'error'
                })

            except Exception as e:
                logger.error(f"Price check failed: {e}")
                socketio.emit('sync_progress', {
                    'message': f'Error: {str(e)}',
                    'current': 0,
                    'total': 100,
                    'percentage': 0,
                    'status': 'error'
                })

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

@app.route('/download-csv')
def download_csv():
    """Download generated CSV file"""
    try:
        filename = request.args.get('file')
        if not filename:
            return "No filename specified", 400
            
        file_path = os.path.join('/tmp', os.path.basename(filename))
        if not os.path.exists(file_path):
            return "File not found", 404
            
        return send_file(
            file_path,
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        logger.error(f"Download failed: {e}")
        return str(e), 500

@app.route('/sync', methods=['POST'])
def sync_products():
    """Main sync endpoint"""
    try:
        cancel_event.clear()
        filename = generate_csv()
        if not filename:
            return jsonify({
                'success': False,
                'message': 'No products found to sync'
            })

        base_filename = os.path.basename(filename)
        
        return jsonify({
            'success': True,
            'message': 'Scraping completed. Starting download...',
            'download_url': f'/download-csv?file={base_filename}',
            'filename': base_filename
        })
            
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/')
def index():
    """Landing page"""
    try:
        logger.info("Attempting to render index.html")
        logger.info(f"Current working directory: {os.getcwd()}")
        logger.info(f"Template folder: {app.template_folder}")
        return render_template('index.html')
    except Exception as e:
        logger.error(f"Error rendering template: {e}")
        return f"Template error: {str(e)}", 500

@app.route('/debug-info')
def debug_info():
    """Debug endpoint to check template configuration"""
    return jsonify({
        'cwd': os.getcwd(),
        'template_folder': app.template_folder,
        'template_list': os.listdir(app.template_folder) if os.path.exists(app.template_folder) else [],
        'exists': os.path.exists(os.path.join(app.template_folder, 'index.html'))
    })

if __name__ == '__main__':
    logger.info(f"Starting server with template directory: {template_dir}")
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)
