from flask import Flask, request, jsonify, send_file
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
socketio = SocketIO(app, cors_allowed_origins="*")

# Keep existing Shopify initialization code...

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

def upload_to_shopify(products):
    """Upload products to Shopify with real-time progress updates"""
    results = {
        'uploaded': 0,
        'failed': 0,
        'errors': []
    }
    
    total_products = len(products)
    emit_progress("Starting upload to Shopify...", 0, total_products)
    
    if not init_shopify_session():
        emit_progress("Failed to initialize Shopify session", 0, total_products, 'error')
        results['errors'].append("Failed to initialize Shopify session")
        return results

    try:
        for index, product in enumerate(products, 1):
            try:
                emit_progress(f"Processing: {product['Title']}", index, total_products)
                
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
                    emit_progress(
                        f"Successfully uploaded: {product['Title']}",
                        index,
                        total_products,
                        'success'
                    )
                else:
                    results['failed'] += 1
                    results['errors'].append(f"Failed to save {product['Title']}")
                    emit_progress(
                        f"Failed to upload: {product['Title']}",
                        index,
                        total_products,
                        'error'
                    )
                
                if index % 2 == 0:  # Rate limiting
                    time.sleep(1)
                    
            except Exception as e:
                results['failed'] += 1
                error_msg = f"Error with {product['Title']}: {str(e)}"
                results['errors'].append(error_msg)
                emit_progress(error_msg, index, total_products, 'error')
                
    except Exception as e:
        error_msg = f"Global error: {str(e)}"
        results['errors'].append(error_msg)
        emit_progress(error_msg, 0, total_products, 'error')
    finally:
        try:
            shopify.ShopifyResource.clear_session()
        except:
            pass
    
    return results

@app.route('/')
def index():
    return """
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
                margin: 5px;
                border-radius: 3px;
                border: 1px solid #ddd;
            }
        </style>
    </head>
    <body>
        <h1>ACDC Product Sync</h1>
        <p>Total available pages: 4331</p>
        <p>Recommended: Scrape 50 pages at a time</p>
        
        <form id="scrapeForm">
            <div>
                <label for="start_page">Start Page:</label>
                <input type="number" id="start_page" name="start_page" 
                       value="1" min="1" max="4331" required>
            </div>
            
            <div>
                <label for="end_page">End Page:</label>
                <input type="number" id="end_page" name="end_page" 
                       value="50" min="1" max="4331" required>
            </div>
            
            <button type="submit" id="submitBtn">Start Sync</button>
        </form>
        
        <div class="progress-container" id="progressContainer" style="display: none;">
            <div class="progress-bar" id="progressBar">
                <div class="progress-text" id="progressText">0%</div>
            </div>
        </div>
        
        <div class="log-container" id="logContainer"></div>

        <script>
            const socket = io();
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
            
            socket.on('sync_progress', function(data) {
                progressContainer.style.display = 'block';
                progressBar.style.width = data.percentage + '%';
                progressText.textContent = data.percentage + '%';
                
                addLogEntry(data.message, data.status);
                
                if (data.percentage === 100) {
                    submitBtn.disabled = false;
                }
            });
            
            document.getElementById('scrapeForm').onsubmit = async function(e) {
                e.preventDefault();
                
                // Clear previous logs and reset progress
                logContainer.innerHTML = '';
                progressBar.style.width = '0%';
                progressText.textContent = '0%';
                progressContainer.style.display = 'block';
                submitBtn.disabled = true;
                
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
    """

# Keep existing route handlers but add emit_progress calls...

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
