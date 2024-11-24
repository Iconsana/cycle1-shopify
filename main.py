from flask import Flask, request, jsonify, send_file, render_template
import pandas as pd
from datetime import datetime
import os
from scraper import scrape_acdc_products, save_to_csv
import shopify
import time

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')

# Initialize Shopify
shopify.Session.setup(
    api_key=os.environ.get('SHOPIFY_API_KEY'),
    secret=os.environ.get('SHOPIFY_API_SECRET')
)

def init_shopify_session():
    """Initialize Shopify API session"""
    shop_url = f"{os.environ.get('SHOP_NAME')}.myshopify.com"
    api_version = os.environ.get('API_VERSION', '2023-10')
    access_token = os.environ.get('ACCESS_TOKEN')
    
    session = shopify.Session(shop_url, api_version, access_token)
    shopify.ShopifyResource.activate_session(session)

def create_shopify_product(product_data):
    """Create a product in Shopify"""
    try:
        new_product = shopify.Product()
        new_product.title = product_data['Title']
        new_product.body_html = product_data['Body (HTML)']
        new_product.vendor = product_data['Vendor']
        new_product.product_type = product_data['Type']
        new_product.tags = product_data['Tags']
        
        # Create variant
        variant = shopify.Variant()
        variant.price = product_data['Variant Price']
        variant.compare_at_price = product_data['Variant Compare At Price']
        variant.sku = product_data['Variant SKU']
        variant.inventory_management = 'shopify'
        variant.inventory_quantity = int(product_data['Variant Inventory Qty'])
        
        new_product.variants = [variant]
        
        if new_product.save():
            return True, None
        return False, "Failed to save product"
        
    except Exception as e:
        return False, str(e)

def sync_to_shopify(products):
    """Sync products to Shopify with rate limiting"""
    results = {
        'success': 0,
        'failed': 0,
        'errors': []
    }
    
    try:
        init_shopify_session()
        
        for index, product in enumerate(products):
            success, error = create_shopify_product(product)
            
            if success:
                results['success'] += 1
            else:
                results['failed'] += 1
                results['errors'].append({
                    'product': product['Title'],
                    'error': error
                })
            
            # Rate limiting - max 2 requests per second
            if index % 2 == 0:
                time.sleep(1)
                
    except Exception as e:
        results['errors'].append({
            'global_error': str(e)
        })
    finally:
        shopify.ShopifyResource.clear_session()
    
    return results

@app.route('/sync', methods=['POST'])
def sync_products():
    """Enhanced sync endpoint with Shopify integration"""
    try:
        start_page = int(request.form.get('start_page', 1))
        end_page = int(request.form.get('end_page', 50))
        
        if start_page < 1 or end_page > 4331:
            raise ValueError("Invalid page range")
        if start_page > end_page:
            raise ValueError("Start page must be less than end page")
        
        # Scrape products
        products = scrape_acdc_products(start_page=start_page, end_page=end_page)
        
        if not products:
            return jsonify({
                'success': False,
                'message': 'No products found to sync'
            })
        
        # Save CSV as backup
        filename = os.path.join('/tmp', f'acdc_products_{start_page}_to_{end_page}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
        save_to_csv(products, filename)
        
        # Sync to Shopify
        sync_results = sync_to_shopify(products)
        
        return jsonify({
            'success': True,
            'message': f'Sync completed. {sync_results["success"]} products created, {sync_results["failed"]} failed.',
            'details': {
                'total_processed': len(products),
                'successful_syncs': sync_results['success'],
                'failed_syncs': sync_results['failed'],
                'errors': sync_results['errors'][:5] if sync_results['errors'] else []
            },
            'download_url': f'/download-csv?file={os.path.basename(filename)}',
            'filename': os.path.basename(filename)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# Keep your existing routes
@app.route('/download-csv', methods=['GET'])
def download_csv():
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

@app.route('/')
def index():
    return """
    <h1>ACDC Product Scraper</h1>
    <p>Total available pages: 4331</p>
    <p>Recommended: Scrape 50 pages at a time</p>
    
    <form id="scrapeForm" action="/sync" method="post">
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
    
    <div id="status" style="margin-top: 20px;"></div>
    
    <script>
        document.getElementById('scrapeForm').onsubmit = function(e) {
            e.preventDefault();
            
            const statusDiv = document.getElementById('status');
            statusDiv.innerHTML = 'Scraping and syncing in progress... This may take a few minutes.';
            
            fetch('/sync', {
                method: 'POST',
                body: new FormData(e.target)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    let message = data.message + '<br><br>';
                    if (data.details) {
                        message += `Processed: ${data.details.total_processed}<br>`;
                        message += `Successful: ${data.details.successful_syncs}<br>`;
                        message += `Failed: ${data.details.failed_syncs}<br>`;
                        
                        if (data.details.errors.length > 0) {
                            message += '<br>Recent errors:<br>';
                            data.details.errors.forEach(error => {
                                message += `- ${error.product || 'Global'}: ${error.error}<br>`;
                            });
                        }
                    }
                    
                    message += '<br>Downloading CSV backup...';
                    statusDiv.innerHTML = message;
                    
                    // Trigger CSV download
                    const link = document.createElement('a');
                    link.href = data.download_url;
                    link.style.display = 'none';
                    document.body.appendChild(link);
                    link.click();
                    document.body.removeChild(link);
                } else {
                    statusDiv.innerHTML = 'Error: ' + data.message;
                }
            })
            .catch(error => {
                statusDiv.innerHTML = 'Error: ' + error.message;
            });
        };
    </script>
    """

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
