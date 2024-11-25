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

def generate_csv():
    """Generate CSV from scraped products with page range"""
    try:
        start_page = int(request.form.get('start_page', 1))
        end_page = int(request.form.get('end_page', 50))
        
        if start_page < 1 or end_page > 4331:
            raise ValueError("Invalid page range")
        if start_page > end_page:
            raise ValueError("Start page must be less than end page")
            
        products = scrape_acdc_products(start_page=start_page, end_page=end_page)
        if products:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = os.path.join('/tmp', f'acdc_products_{start_page}_to_{end_page}_{timestamp}.csv')
            return save_to_csv(products, filename)
    except Exception as e:
        print(f"Error generating CSV: {e}")
        return None

def init_shopify_session():
    """Initialize Shopify API session"""
    try:
        shop_url = f"{os.environ.get('SHOP_NAME')}.myshopify.com"
        access_token = os.environ.get('ACCESS_TOKEN')
        
        session = shopify.Session(shop_url, '2023-10', access_token)
        shopify.ShopifyResource.activate_session(session)
        return True
    except Exception as e:
        print(f"Error initializing Shopify session: {e}")
        return False

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

    try:
        for product in products:
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
                else:
                    results['failed'] += 1
                    results['errors'].append(f"Failed to save {product['Title']}")
                
                # Rate limiting
                if results['uploaded'] % 2 == 0:
                    time.sleep(1)
                    
            except Exception as e:
                results['failed'] += 1
                results['errors'].append(f"Error with {product['Title']}: {str(e)}")
                
    except Exception as e:
        results['errors'].append(f"Global error: {str(e)}")
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
        # First generate CSV
        filename = generate_csv()
        if not filename:
            return jsonify({
                'success': False,
                'message': 'No products found to sync'
            })

        # If we have Shopify credentials, try to upload
        if all([
            os.environ.get('SHOPIFY_API_KEY'),
            os.environ.get('SHOPIFY_API_SECRET'),
            os.environ.get('SHOP_NAME'),
            os.environ.get('ACCESS_TOKEN')
        ]):
            # Read products from CSV
            df = pd.read_csv(filename)
            products = df.to_dict('records')
            
            # Upload to Shopify
            upload_results = upload_to_shopify(products)
            
            base_filename = os.path.basename(filename)
            return jsonify({
                'success': True,
                'message': f'Sync completed. {upload_results["uploaded"]} products uploaded to Shopify, {upload_results["failed"]} failed.',
                'details': {
                    'total_processed': len(products),
                    'uploaded_to_shopify': upload_results['uploaded'],
                    'failed_uploads': upload_results['failed'],
                    'errors': upload_results['errors'][:5] if upload_results['errors'] else []
                },
                'download_url': f'/download-csv?file={base_filename}',
                'filename': base_filename
            })
        else:
            # If no Shopify credentials, just return CSV download
            base_filename = os.path.basename(filename)
            return jsonify({
                'success': True,
                'message': 'Successfully scraped products. Download will start automatically.',
                'download_url': f'/download-csv?file={base_filename}',
                'filename': base_filename
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/')
def index():
    return """
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
    
    <div id="error" style="color: red; margin-top: 10px;"></div>
    <div id="status" style="margin-top: 10px;"></div>

    <script>
        document.getElementById('scrapeForm').onsubmit = async function(e) {
            e.preventDefault();
            
            const errorDiv = document.getElementById('error');
            const statusDiv = document.getElementById('status');
            
            // Clear previous messages
            errorDiv.textContent = '';
            statusDiv.textContent = 'Scraping in progress...';
            
            try {
                const formData = new FormData(this);
                const response = await fetch('/sync', {
                    method: 'POST',
                    body: formData
                });
                
                // Check if response is ok
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                let data;
                try {
                    data = await response.json();
                } catch (parseError) {
                    const rawText = await response.text();
                    throw new Error(`Failed to parse response: ${rawText}`);
                }
                
                if (data.success) {
                    statusDiv.textContent = data.message;
                    
                    // Show additional details if available
                    if (data.details) {
                        const details = data.details;
                        statusDiv.innerHTML += `<br><br>Products processed: ${details.total_processed}`;
                        if (details.uploaded_to_shopify !== undefined) {
                            statusDiv.innerHTML += `<br>Uploaded to Shopify: ${details.uploaded_to_shopify}`;
                            statusDiv.innerHTML += `<br>Failed uploads: ${details.failed_uploads}`;
                            
                            if (details.errors && details.errors.length > 0) {
                                statusDiv.innerHTML += '<br><br>Recent errors:';
                                details.errors.forEach(error => {
                                    statusDiv.innerHTML += `<br>- ${error}`;
                                });
                            }
                        }
                    }
                    
                    if (data.download_url) {
                        window.location.href = data.download_url;
                    }
                } else {
                    throw new Error(data.message || 'Unknown error occurred');
                }
            } catch (error) {
                errorDiv.textContent = `Error: ${error.message}`;
                statusDiv.textContent = '';
                console.error('Error details:', error);
            }
        };
    </script>
    
    <style>
        body {
            max-width: 800px;
            margin: 20px auto;
            padding: 0 20px;
            font-family: Arial, sans-serif;
        }
        
        input[type="number"] {
            padding: 5px;
            margin-left: 10px;
        }
        
        #error {
            background-color: #ffe6e6;
            padding: 10px;
            border-radius: 4px;
            display: none;
        }
        
        #error:not(:empty) {
            display: block;
        }
        
        #status {
            background-color: #e6f3ff;
            padding: 10px;
            border-radius: 4px;
            display: none;
        }
        
        #status:not(:empty) {
            display: block;
        }
        
        button {
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        
        button:hover {
            background-color: #45a049;
        }
    </style>
    """

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
