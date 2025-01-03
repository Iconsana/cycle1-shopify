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

# Configure app
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')

# Initialize SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', logger=True, engineio_logger=True)

# Constants
CREDENTIALS_FILE = 'cycle1-price-monitor-e2948349fb68.json'
SPREADSHEET_ID = '1VDmG5diadJ1hNdv6ZnHfT1mVTGFM-xejWKe_ACWiuRo'
SHOPIFY_SHOP_URL = "cycle1-test.myshopify.com"
SHOPIFY_API_VERSION = '2023-10'

# Global variables
cancel_event = Event()
current_sync_thread = None
sync_manager = None

def get_credentials_path():
    """Get the full path to the credentials file"""
    return os.path.join(os.path.dirname(__file__), CREDENTIALS_FILE)

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

def init_shopify_session():
    """Initialize Shopify session"""
    try:
        access_token = os.environ.get('ACCESS_TOKEN')
        session = shopify.Session(SHOPIFY_SHOP_URL, SHOPIFY_API_VERSION, access_token)
        shopify.ShopifyResource.activate_session(session)
        shop = shopify.Shop.current()
        logger.info(f"Connected to shop: {shop.name}")
        return True
    except Exception as e:
        logger.error(f"Shopify session error: {e}")
        return False

def sync_task(products):
    """Background task for syncing products"""
    try:
        results = upload_to_shopify(products)
        if not cancel_event.is_set():
            socketio.emit('sync_complete', results)
    except Exception as e:
        socketio.emit('sync_error', {'message': str(e)})

def upload_to_shopify(products):
    """Upload products to Shopify"""
    results = {
        'uploaded': 0,
        'failed': 0,
        'errors': []
    }
    
    if not init_shopify_session():
        results['errors'].append("Failed to initialize Shopify session")
        return results

    total_products = len(products)
    for index, product in enumerate(products, 1):
        if cancel_event.is_set():
            break
            
        try:
            new_product = shopify.Product()
            new_product.title = product['Title']
            new_product.body_html = product['Body (HTML)']
            new_product.vendor = product['Vendor']
            new_product.product_type = product['Type']
            new_product.tags = product['Tags']
            
            variant = shopify.Variant({
                'price': product['Variant Price'],
                'compare_at_price': product['Variant Compare At Price'],
                'sku': product['Variant SKU'],
                'inventory_management': 'shopify',
                'inventory_quantity': int(product['Variant Inventory Qty']),
                'requires_shipping': product['Variant Requires Shipping'] == 'TRUE',
                'taxable': product['Variant Taxable'] == 'TRUE'
            })
            
            new_product.variants = [variant]
            
            if new_product.save():
                results['uploaded'] += 1
                emit_progress(f'Uploaded: {product["Title"]}', index, total_products, 'success')
            else:
                results['failed'] += 1
                results['errors'].append(f"Failed to save {product['Title']}")
                
        except Exception as e:
            results['failed'] += 1
            results['errors'].append(f"Error with {product['Title']}: {str(e)}")
            emit_progress(f'Error: {str(e)}', index, total_products, 'error')
            
        # Rate limiting
        if index % 2 == 0:
            time.sleep(1)
            
    shopify.ShopifyResource.clear_session()
    return results

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
        monitor = PriceMonitor(
            spreadsheet_id='1VDmG5diadJ1hNdv6ZnHfT1mVTGFM-xejWKe_ACWiuRo'
        )
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
        monitor = PriceMonitor(
            get_credentials_path(),
            SPREADSHEET_ID
        )
        
        # Check first product first
        test_sku = "A0001/3/230-NS"
        success = monitor.update_single_product(2, test_sku)
        
        if success:
            # Start checking all prices in background
            thread = Thread(target=monitor.check_all_prices)
            thread.start()
            
            return jsonify({
                'success': True,
                'message': 'Price check started',
                'sku': test_sku
            })
        return jsonify({
            'success': False,
            'message': 'Failed to check prices',
            'sku': test_sku
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
    global current_sync_thread
    try:
        cancel_event.set()
        if current_sync_thread and current_sync_thread.is_alive():
            current_sync_thread.join(timeout=5)
        cancel_event.clear()
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
    global current_sync_thread
    try:
        cancel_event.clear()
        filename = generate_csv()
        if not filename:
            return jsonify({
                'success': False,
                'message': 'No products found to sync'
            })

        base_filename = os.path.basename(filename)
        download_url = f'/download-csv?file={base_filename}'
        
        shopify_sync_status = {'started': False, 'error': None}
        if all([
            os.environ.get('SHOPIFY_API_KEY'),
            os.environ.get('SHOPIFY_API_SECRET'),
            os.environ.get('ACCESS_TOKEN')
        ]):
            try:
                df = pd.read_csv(filename)
                products = df.to_dict('records')
                current_sync_thread = threading.Thread(target=sync_task, args=(products,))
                current_sync_thread.start()
                shopify_sync_status['started'] = True
            except Exception as e:
                shopify_sync_status['error'] = str(e)
                logger.error(f"Shopify sync error: {e}")

        return jsonify({
            'success': True,
            'message': 'Scraping completed. Starting download...',
            'download_url': download_url,
            'filename': base_filename,
            'shopify_sync': shopify_sync_status
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
        # Debug: Print current directory and template folder
        print(f"Current working directory: {os.getcwd()}")
        print(f"Template folder: {app.template_folder}")
        
        return render_template('index.html')
    except Exception as e:
        print(f"Template error: {e}")
        # Fallback: Try absolute path
        template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app', 'templates')
        print(f"Looking for template in: {template_dir}")
        return render_template('index.html')

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)
