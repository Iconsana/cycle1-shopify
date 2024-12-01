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

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', logger=True, engineio_logger=True)

# Global variables
cancel_event = Event()
current_sync_thread = None
sync_manager = None

def emit_progress(message, current, total, status='processing'):
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
        print(f"Error emitting progress: {e}")

def generate_csv():
    try:
        start_page = int(request.form.get('start_page', 1))
        end_page = int(request.form.get('end_page', 50))
        
        if start_page < 1 or end_page > 4331:
            raise ValueError("Invalid page range")
            
        products = scrape_acdc_products(start_page=start_page, end_page=end_page)
        
        if products:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = os.path.join('/tmp', f'acdc_products_{start_page}_to_{end_page}_{timestamp}.csv')
            return save_to_csv(products, filename)
        return None
    except Exception as e:
        print(f"Error generating CSV: {e}")
        return None

def init_shopify_session():
    try:
        access_token = os.environ.get('ACCESS_TOKEN')
        shop_url = "cycle1-test.myshopify.com"
        api_version = '2023-10'
        
        session = shopify.Session(shop_url, api_version, access_token)
        shopify.ShopifyResource.activate_session(session)
        
        shop = shopify.Shop.current()
        print(f"Connected to shop: {shop.name}")
        return True
    except Exception as e:
        print(f"Shopify session error: {e}")
        return False

def sync_task(products):
    try:
        results = upload_to_shopify(products)
        if not cancel_event.is_set():
            socketio.emit('sync_complete', results)
    except Exception as e:
        socketio.emit('sync_error', {'message': str(e)})

def upload_to_shopify(products):
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
            
        if index % 2 == 0:
            time.sleep(1)
            
    shopify.ShopifyResource.clear_session()
    return results

@app.route('/cancel', methods=['POST'])
def cancel_sync():
    global current_sync_thread
    try:
        cancel_event.set()
        if current_sync_thread and current_sync_thread.is_alive():
            current_sync_thread.join(timeout=5)
        cancel_event.clear()
        return jsonify({'success': True, 'message': 'Sync cancelled'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/download-csv')
def download_csv():
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
        print(f"Download error: {e}")
        return str(e), 500

@app.route('/sync', methods=['POST'])
def sync_products():
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
                print(f"Shopify sync error: {e}")

        return jsonify({
            'success': True,
            'message': 'Scraping completed. Starting download...',
            'download_url': download_url,
            'filename': base_filename,
            'shopify_sync': shopify_sync_status
        })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)
