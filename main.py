from flask import Flask, request, jsonify, send_file
from flask_socketio import SocketIO, emit
import pandas as pd
from datetime import datetime
import os
from scraper import scrape_acdc_products, save_to_csv
import shopify
import time

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY')
socketio = SocketIO(app, cors_allowed_origins="*")

# Initialize Shopify (existing code...)

def emit_progress(message, progress, total, status='processing'):
    """Emit progress update through WebSocket"""
    socketio.emit('sync_progress', {
        'message': message,
        'progress': progress,
        'total': total,
        'status': status,
        'percentage': (progress / total * 100) if total > 0 else 0
    })

def sync_to_shopify(products):
    """Enhanced sync with progress updates"""
    results = {
        'success': 0,
        'failed': 0,
        'errors': []
    }
    
    total_products = len(products)
    
    try:
        init_shopify_session()
        
        for index, product in enumerate(products, 1):
            try:
                emit_progress(
                    f"Processing: {product['Title']}",
                    index,
                    total_products
                )
                
                success, error = create_shopify_product(product)
                
                if success:
                    results['success'] += 1
                    emit_progress(
                        f"Successfully created: {product['Title']}",
                        index,
                        total_products
                    )
                else:
                    results['failed'] += 1
                    results['errors'].append({
                        'product': product['Title'],
                        'error': error
                    })
                    emit_progress(
                        f"Failed to create: {product['Title']} - {error}",
                        index,
                        total_products,
                        'error'
                    )
                
                # Rate limiting
                if index % 2 == 0:
                    time.sleep(1)
                    
            except Exception as e:
                results['failed'] += 1
                results['errors'].append({
                    'product': product['Title'],
                    'error': str(e)
                })
                emit_progress(
                    f"Error processing: {product['Title']} - {str(e)}",
                    index,
                    total_products,
                    'error'
                )
                
    except Exception as e:
        results['errors'].append({
            'global_error': str(e)
        })
        emit_progress(
            f"Global error: {str(e)}",
            0,
            total_products,
            'error'
        )
    finally:
        shopify.ShopifyResource.clear_session()
    
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
            .progress-bar {
                width: 100%;
                height: 20px;
                background-color: #f0f0f0;
                border-radius: 10px;
                overflow: hidden;
                margin: 20px 0;
            }
            .progress {
                width: 0%;
                height: 100%;
                background-color: #4CAF50;
                transition: width 0.3s ease;
            }
            .status-box {
                padding: 10px;
                margin: 10px 0;
                border-radius: 5px;
                max-height: 200px;
                overflow-y: auto;
            }
            .error {
                color: #721c24;
                background-color: #f8d7da;
                border: 1px solid #f5c6cb;
            }
            .success {
                color: #155724;
                background-color: #d4edda;
                border: 1px solid #c3e6cb;
            }
        </style>
    </head>
    <body>
        <h1>ACDC Product Scraper</h1>
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
            
            <button type="submit" style="padding: 10px 20px;">Start Scraping</button>
        </form>
        
        <div class="progress-bar">
            <div class="progress" id="progressBar"></div>
        </div>
        
        <div id="statusBox" class="status-box"></div>
        
        <script>
            const socket = io();
            const statusBox = document.getElementById('statusBox');
            const progressBar = document.getElementById('progressBar');
            
            socket.on('sync_progress', function(data) {
                // Update progress bar
                progressBar.style.width = data.percentage + '%';
                
                // Add status message
                const messageDiv = document.createElement('div');
                messageDiv.classList.add(data.status === 'error' ? 'error' : 'success');
                messageDiv.textContent = data.message;
                statusBox.insertBefore(messageDiv, statusBox.firstChild);
            });
            
            document.getElementById('scrapeForm').onsubmit = function(e) {
                e.preventDefault();
                
                // Clear previous status
                statusBox.innerHTML = '';
                progressBar.style.width = '0%';
                
                const formData = new FormData(e.target);
                
                fetch('/sync', {
                    method: 'POST',
                    body: formData
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        // Final status update
                        const messageDiv = document.createElement('div');
                        messageDiv.classList.add('success');
                        messageDiv.textContent = data.message;
                        statusBox.insertBefore(messageDiv, statusBox.firstChild);
                        
                        // Trigger CSV download
                        const link = document.createElement('a');
                        link.href = data.download_url;
                        link.style.display = 'none';
                        document.body.appendChild(link);
                        link.click();
                        document.body.removeChild(link);
                    } else {
                        const messageDiv = document.createElement('div');
                        messageDiv.classList.add('error');
                        messageDiv.textContent = 'Error: ' + data.message;
                        statusBox.insertBefore(messageDiv, statusBox.firstChild);
                    }
                })
                .catch(error => {
                    const messageDiv = document.createElement('div');
                    messageDiv.classList.add('error');
                    messageDiv.textContent = 'Error: ' + error.message;
                    statusBox.insertBefore(messageDiv, statusBox.firstChild);
                });
            };
        </script>
    </body>
    </html>
    """

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
