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

@app.route('/monitor/test-connection')
def test_monitor_connection():
    """Test Google Sheets connection"""
    try:
        monitor = PriceMonitor(
            'cycle1-price-monitor-e2948349fb68.json',
            '1VDmG5diadJ1hNdv6ZnHfT1mVTGFM-xejWKe_ACWiuRo'
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
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/monitor/check-prices')
def check_prices():
    """Test price checking for the first product"""
    try:
        monitor = PriceMonitor(
            'cycle1-price-monitor-e2948349fb68.json',
            '1VDmG5diadJ1hNdv6ZnHfT1mVTGFM-xejWKe_ACWiuRo'
        )
        
        # Test with first product
        test_sku = "A0001/3/230-NS"
        success = monitor.update_single_product(2, test_sku)
        
        if success:
            return jsonify({
                'success': True,
                'message': 'Successfully checked and updated price',
                'sku': test_sku
            })
        return jsonify({
            'success': False,
            'message': 'Failed to update price',
            'sku': test_sku
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

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
    return '''
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>ACDC Product Sync</title>
        <link rel="stylesheet" href="https://unpkg.com/@shopify/polaris@12.0.0/build/esm/styles.css"/>
        <script src="https://unpkg.com/@shopify/app-bridge@3"></script>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
        <style>
            body {
                max-width: 800px;
                margin: 20px auto;
                padding: 0 20px;
                font-family: Arial, sans-serif;
            }
            
            .sync-container {
                max-width: 800px;
                margin: 20px auto;
                padding: 20px;
            }
            
            .progress-container {
                width: 100%;
                background-color: #f1f1f1;
                padding: 3px;
                border-radius: 3px;
                box-shadow: inset 0 1px 3px rgba(0, 0, 0, .2);
                margin-top: 20px;
            }
            
            .progress-bar {
                width: 100%;
                height: 20px;
                background-color: #f0f0f0;
                border-radius: 10px;
                overflow: hidden;
                margin: 10px 0;
            }
            
            .progress {
                width: 0%;
                height: 100%;
                background-color: #008060;
                transition: width 0.3s ease;
            }
            
            .log-container {
                margin-top: 20px;
                max-height: 300px;
                overflow-y: auto;
                border: 1px solid #ddd;
                padding: 10px;
                border-radius: 4px;
            }
            
            .log-entry {
                margin: 5px 0;
                padding: 5px;
                border-radius: 3px;
            }
            
            .log-success { background-color: #dff0d8; }
            .log-error { background-color: #f2dede; }
            .log-info { background-color: #d9edf7; }
            
            button {
                background-color: #4CAF50;
                color: white;
                padding: 10px 20px;
                border: none;
                border-radius: 4px;
                cursor: pointer;
                margin: 5px;
            }
            
            button:disabled {
                background-color: #cccccc;
                cursor: not-allowed;
            }
            
            input[type="number"] {
                padding: 5px;
                margin-left: 10px;
            }
            
            .form-section {
                margin-bottom: 20px;
                padding: 20px;
                border: 1px solid #ddd;
                border-radius: 4px;
            }
        </style>
    </head>
    <body>
        <div class="sync-container">
            <h1>ACDC Product Sync</h1>
            
            <div class="form-section">
                <h2>Product Sync Settings</h2>
                <form id="syncForm">
                    <div>
                        <label for="startPage">Start Page:</label>
                        <input type="number" id="startPage" name="start_page" min="1" max="4331" value="1">
                    </div>
                    <div>
                        <label for="endPage">End Page:</label>
                        <input type="number" id="endPage" name="end_page" min="1" max="4331" value="30">
                    </div>
                    <button type="submit" id="submitBtn">Start Sync</button>
                    <button type="button" id="cancelBtn" style="display: none;">Cancel Sync</button>
                </form>
            </div>

            <div class="form-section">
                <h2>Price Monitor</h2>
                <button type="button" id="testConnectionBtn">Test Connection</button>
                <button type="button" id="checkPricesBtn">Check Prices</button>
                <div id="monitorStatus"></div>
            </div>

            <div class="progress-section" style="display: none;">
                <h2>Sync Progress</h2>
                <div class="progress-bar">
                    <div class="progress" id="progressBar"></div>
                </div>
                <p id="statusMessage">Preparing sync...</p>
                <p id="productCount">Products synced: 0</p>
            </div>

            <div class="log-container" id="logContainer"></div>
        </div>

        <script>
            const socket = io({
                transports: ['websocket'],
                upgrade: false,
                reconnection: true,
                reconnectionAttempts: 5
            });
            
            const progressBar = document.getElementById('progressBar');
            const progressSection = document.querySelector('.progress-section');
            const statusMessage = document.getElementById('statusMessage');

            const productCount = document.getElementById('productCount');
            const logContainer = document.getElementById('logContainer');
            const submitBtn = document.getElementById('submitBtn');
            const cancelBtn = document.getElementById('cancelBtn');
            
            function addLogEntry(message, type = 'info') {
                const entry = document.createElement('div');
                entry.className = `log-entry log-${type}`;
                entry.textContent = message;
                logContainer.insertBefore(entry, logContainer.firstChild);
            }
            
            socket.on('connect', () => {
                console.log('Connected to server');
                addLogEntry('Connected to server', 'success');
            });
            
            socket.on('connect_error', (error) => {
                console.error('Socket connection error:', error);
                addLogEntry('Connection error: ' + error.message, 'error');
            });
            
            socket.on('sync_progress', function(data) {
                console.log('Progress update:', data);
                progressSection.style.display = 'block';
                progressBar.style.width = data.percentage + '%';
                statusMessage.textContent = data.message;
                productCount.textContent = `Products synced: ${data.current}/${data.total}`;
                addLogEntry(data.message, data.status);
            });
            
            socket.on('sync_complete', function(data) {
                const message = `Sync completed. Uploaded: ${data.uploaded}, Failed: ${data.failed}`;
                statusMessage.textContent = message;
                addLogEntry(message, 'success');
                submitBtn.disabled = false;
                cancelBtn.style.display = 'none';
                
                if (data.errors && data.errors.length > 0) {
                    data.errors.forEach(error => {
                        addLogEntry(error, 'error');
                    });
                }
            });
            
            socket.on('sync_error', function(data) {
                statusMessage.textContent = 'Error: ' + data.message;
                addLogEntry('Error: ' + data.message, 'error');
                submitBtn.disabled = false;
                cancelBtn.style.display = 'none';
            });
            
            document.getElementById('syncForm').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                // Clear previous logs
                logContainer.innerHTML = '';
                progressBar.style.width = '0%';
                statusMessage.textContent = 'Preparing sync...';
                productCount.textContent = 'Products synced: 0';
                
                // Show progress section and update buttons
                progressSection.style.display = 'block';
                submitBtn.disabled = true;
                cancelBtn.style.display = 'inline-block';
                
                addLogEntry('Starting sync process...', 'info');
                
                try {
                    const response = await fetch('/sync', {
                        method: 'POST',
                        body: new FormData(e.target)
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        addLogEntry(data.message, 'success');
                        if (data.download_url) {
                            window.location.href = data.download_url;
                        }
                        
                        if (data.shopify_sync?.started) {
                            addLogEntry('Shopify sync started', 'info');
                        } else if (data.shopify_sync?.error) {
                            addLogEntry('Shopify sync error: ' + data.shopify_sync.error, 'error');
                        }
                    } else {
                        addLogEntry('Error: ' + data.message, 'error');
                        submitBtn.disabled = false;
                        cancelBtn.style.display = 'none';
                    }
                } catch (error) {
                    addLogEntry('Error: ' + error.message, 'error');
                    submitBtn.disabled = false;
                    cancelBtn.style.display = 'none';
                }
            });
            
            cancelBtn.addEventListener('click', async () => {
                try {
                    const response = await fetch('/cancel', {
                        method: 'POST'
                    });
                    const data = await response.json();
                    if (data.success) {
                        addLogEntry('Sync cancelled', 'info');
                        submitBtn.disabled = false;
                        cancelBtn.style.display = 'none';
                    } else {
                        addLogEntry('Error cancelling sync: ' + data.message, 'error');
                    }
                } catch (error) {
                    addLogEntry('Error cancelling sync: ' + error.message, 'error');
                }
            });

            // Price Monitor buttons
            document.getElementById('testConnectionBtn').addEventListener('click', async () => {
                try {
                    const response = await fetch('/monitor/test-connection');
                    const data = await response.json();
                    addLogEntry(data.message, data.success ? 'success' : 'error');
                } catch (error) {
                    addLogEntry('Error: ' + error.message, 'error');
                }
            });

            document.getElementById('checkPricesBtn').addEventListener('click', async () => {
                try {
                    const response = await fetch('/monitor/check-prices');
                    const data = await response.json();
                    addLogEntry(data.message, data.success ? 'success' : 'error');
                } catch (error) {
                    addLogEntry('Error: ' + error.message, 'error');
                }
            });
        </script>
    </body>
    </html>
    '''

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)
            const productCount = document.getElementByI
