from flask import Flask, request, jsonify, send_file, render_template
from flask_socketio import SocketIO, emit
import pandas as pd
from datetime import datetime
import os
from scraper import scrape_acdc_products, save_to_csv
import shopify
import time
import json

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', logger=True, engineio_logger=True)

# Initialize Shopify
shopify.Session.setup(
    api_key=os.environ.get('SHOPIFY_API_KEY'),
    secret=os.environ.get('SHOPIFY_API_SECRET')
)

def emit_progress(message, current, total, status='processing'):
    """Emit progress update through WebSocket"""
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
    """Generate CSV from scraped products with page range"""
    try:
        start_page = int(request.form.get('start_page', 1))
        end_page = int(request.form.get('end_page', 50))
        
        if start_page < 1 or end_page > 4331:
            raise ValueError("Invalid page range")
        if start_page > end_page:
            raise ValueError("Start page must be less than end page")
            
        # Initialize progress
        socketio.emit('sync_progress', {
            'message': 'Starting scrape...',
            'current': 0,
            'total': end_page - start_page + 1,
            'percentage': 0,
            'status': 'processing'
        })
        
        products = scrape_acdc_products(start_page=start_page, end_page=end_page)
        
        if products:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = os.path.join('/tmp', f'acdc_products_{start_page}_to_{end_page}_{timestamp}.csv')
            saved_file = save_to_csv(products, filename)
            
            # Update progress for completion
            socketio.emit('sync_progress', {
                'message': 'Scraping completed!',
                'current': end_page - start_page + 1,
                'total': end_page - start_page + 1,
                'percentage': 100,
                'status': 'success'
            })
            
            return saved_file
    except Exception as e:
        print(f"Error generating CSV: {e}")
        socketio.emit('sync_progress', {
            'message': f'Error: {str(e)}',
            'current': 0,
            'total': 100,
            'percentage': 0,
            'status': 'error'
        })
        return None

def init_shopify_session():
    """Initialize Shopify API session"""
    try:
        shop_url = f"{os.environ.get('SHOP_NAME')}.myshopify.com"
        access_token = os.environ.get('ACCESS_TOKEN')
        api_version = '2023-10'
        
        # Debug logging
        print(f"Initializing Shopify session for shop: {shop_url}")
        print(f"Using API version: {api_version}")
        
        session = shopify.Session(shop_url, api_version, access_token)
        shopify.ShopifyResource.activate_session(session)
        
        # Verify session
        shop = shopify.Shop.current()
        if shop:
            print(f"Successfully connected to shop: {shop.name}")
            return True
        return False
    except Exception as e:
        print(f"Error initializing Shopify session: {str(e)}")
        return False

def upload_to_shopify(products):
    """Upload products to Shopify with real-time progress updates"""
    results = {
        'uploaded': 0,
        'failed': 0,
        'errors': []
    }
    
    total_products = len(products)
    socketio.emit('sync_progress', {
        'message': 'Starting Shopify upload...',
        'current': 0,
        'total': total_products,
        'percentage': 0,
        'status': 'processing'
    })
    
    if not init_shopify_session():
        socketio.emit('sync_progress', {
            'message': 'Failed to initialize Shopify session',
            'current': 0,
            'total': total_products,
            'percentage': 0,
            'status': 'error'
        })
        results['errors'].append("Failed to initialize Shopify session")
        return results

    try:
        for index, product in enumerate(products, 1):
            try:
                socketio.emit('sync_progress', {
                    'message': f'Processing: {product["Title"]}',
                    'current': index,
                    'total': total_products,
                    'percentage': int((index / total_products) * 100),
                    'status': 'processing'
                })
                
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
                    socketio.emit('sync_progress', {
                        'message': f'Uploaded: {product["Title"]}',
                        'current': index,
                        'total': total_products,
                        'percentage': int((index / total_products) * 100),
                        'status': 'success'
                    })
                else:
                    results['failed'] += 1
                    results['errors'].append(f"Failed to save {product['Title']}")
                    socketio.emit('sync_progress', {
                        'message': f'Failed to upload: {product["Title"]}',
                        'current': index,
                        'total': total_products,
                        'percentage': int((index / total_products) * 100),
                        'status': 'error'
                    })
                
                if index % 2 == 0:  # Rate limiting
                    time.sleep(1)
                    
            except Exception as e:
                results['failed'] += 1
                error_msg = f"Error with {product['Title']}: {str(e)}"
                results['errors'].append(error_msg)
                socketio.emit('sync_progress', {
                    'message': error_msg,
                    'current': index,
                    'total': total_products,
                    'percentage': int((index / total_products) * 100),
                    'status': 'error'
                })
                
    except Exception as e:
        error_msg = f"Global error: {str(e)}"
        results['errors'].append(error_msg)
        socketio.emit('sync_progress', {
            'message': error_msg,
            'current': 0,
            'total': total_products,
            'percentage': 0,
            'status': 'error'
        })
    finally:
        try:
            shopify.ShopifyResource.clear_session()
        except:
            pass
    
    return results

@app.route('/download-csv', methods=['GET'])
def download_csv():
    """Endpoint to download the latest product data as CSV"""
    try:
        filename = request.args.get('file')
        if not filename:
            return "No filename specified", 400
            
        file_path = os.path.join('/tmp', os.path.basename(filename))
        if os.path.exists(file_path):
            response = send_file(
                file_path,
                mimetype='text/csv',
                as_attachment=True,
                download_name=os.path.basename(filename)
            )
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
            return response
        return "File not found", 404
    except Exception as e:
        return str(e), 500

@app.route('/sync', methods=['POST'])
def sync_products():
    """Generate CSV and optionally upload to Shopify"""
    try:
        filename = generate_csv()
        if not filename:
            return jsonify({
                'success': False,
                'message': 'No products found to sync'
            })

        base_filename = os.path.basename(filename)
        
        # Always return immediate success for CSV generation
        response_data = {
            'success': True,
            'message': 'Successfully scraped products. Download will start automatically.',
            'download_url': f'/download-csv?file={base_filename}',
            'filename': base_filename
        }
        
        # If Shopify credentials exist, queue up the Shopify sync
        if all([
            os.environ.get('SHOPIFY_API_KEY'),
            os.environ.get('SHOPIFY_API_SECRET'),
            os.environ.get('SHOP_NAME'),
            os.environ.get('ACCESS_TOKEN')
        ]):
            try:
                df = pd.read_csv(filename)
                products = df.to_dict('records')
                # Upload to Shopify in background
                socketio.start_background_task(upload_to_shopify, products)
            except Exception as e:
                print(f"Shopify sync error: {e}")
                # Still return success for CSV even if Shopify fails
        
        return jsonify(response_data)
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/')
def index():
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>ACDC Product Sync</title>
        <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
        <style>
            body {
                max-width: 800px;
                margin: 20px auto;
                padding: 0 20px;
                font-family: Arial, sans-serif;
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
                height: 20px;
                background-color: #4CAF50;
                width: 0%;
                border-radius: 3px;
                transition: width 500ms ease-in-out;
                position: relative;
            }
            
            .progress-text {
                position: absolute;
                width: 100%;
                text-align: center;
                color: white;
                text-shadow: 1px 1px 2px rgba(0,0,0,0.5);
                line-height: 20px;
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
            }
            
            button:disabled {
                background-color: #cccccc;
                cursor: not-allowed;
            }
            
            input[type="number"] {
                padding: 5px;
                margin-left: 10px;
            }
        </style>
    </head>
    <body>
        <h1>ACDC Product Sync</h1>
        <p>Total available pages: 4331</p>
        <p>Recommended: Scrape 50 pages at a time</p>
        
        <form id="scrapeForm">
            <div style="margin-bottom: 15px;">
                <label for="start_page">Start Page:</label>
                <input type="number" id="start_page" name="start_page" 
                       value="1" min="1" max="4331" required>
            </div>
            
            <div style="margin-bottom: 15px;">
                <label for="end_page">End Page:</label>
                <input type="number" id="end_page" name="end_page" 
                       value="50" min="1" max="4331" required>
            </div>
            
            <button type="submit" id="submitBtn">Start Sync</button>
        </form>
        
        <div class="progress-container" id="progressContainer">
            <div class="progress-bar" id="progressBar">
                <div class="progress-text" id="progressText">0%</div>
            </div>
        </div>
        
        <div class="log-container" id="logContainer"></div>

        <script>
            const socket = io({
                transports: ['websocket'],
                upgrade: false,
                reconnection: true,
                reconnectionAttempts: 5
            });
            
            const progressBar = document.getElementById('progressBar');
            const progressText = document.getElementById('progressText');
            const progressContainer = document.getElementById('progressContainer');
            const logContainer = document.getElementById('logContainer');
            const submitBtn = document.getElementById('submitBtn');
            
            function addLogEntry(message, type = 'info') {
                const entry = document.createElement('div');
                entry.className = `log-entry log-${type}`;
                entry.textContent = message;
                logContainer.insertBefore(entry, logContainer.firstChild);
            }
            
            socket.on('connect', () => {
                console.log('Socket connected');
                addLogEntry('Connected to server', 'success');
            });
            
            socket.on('connect_error', (error) => {
                console.error('Socket connection error:', error);
                addLogEntry('Connection error: ' + error, 'error');
            });
            
            socket.on('sync_progress', function(data) {
                console.log('Progress update:', data);
                progressContainer.style.display = 'block';
                progressBar.style.width = data.percentage + '%';
                progressText.textContent = data.percentage + '%';
                
                addLogEntry(data.message, data.status);
            });
            
            document.getElementById('scrapeForm').onsubmit = async function(e) {
                e.preventDefault();
                
                logContainer.innerHTML = '';
                progressBar.style.width = '0%';
                progressText.textContent = '0%';
                progressContainer.style.display = 'block';
                submitBtn.disabled = true;
                
                addLogEntry('Starting sync process...', 'info');
                
                try {
                    const formData = new FormData(e.target);
                    const response = await fetch('/sync', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        addLogEntry(data.message, 'success');
                        if (data.download_url) {
                            window.location.href = data.download_url;
                        }
                    } else {
                        addLogEntry('Error: ' + data.message, 'error');
                    }
                } catch (error) {
                    addLogEntry('Error: ' + error.message, 'error');
                } finally {
                    submitBtn.disabled = false;
                }
            };
        </script>
    </body>
    </html>
    '''

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)
