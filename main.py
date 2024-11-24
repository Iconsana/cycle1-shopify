from flask import Flask, request, redirect, jsonify, send_file, render_template
import pandas as pd
from datetime import datetime
import os
from scraper import scrape_acdc_products, save_to_csv
import shopify
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')

# Shopify setup
shopify.Session.setup(
    api_key=os.environ.get('SHOPIFY_API_KEY'),
    secret=os.environ.get('SHOPIFY_API_SECRET')
)

def verify_shop_session(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        shop = request.args.get('shop')
        if not shop:
            return jsonify({"error": "Shop parameter required"}), 400
        return f(*args, **kwargs)
    return decorated_function

def generate_csv():
    """Generate CSV from scraped products with page range"""
    try:
        start_page = int(request.form.get('start_page', 1))
        end_page = int(request.form.get('end_page', 50))
        
        # Validate page ranges
        if start_page < 1 or end_page > 4331:
            raise ValueError("Invalid page range")
        if start_page > end_page:
            raise ValueError("Start page must be less than end page")
            
        products = scrape_acdc_products(start_page=start_page, end_page=end_page)
        if products:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'acdc_products_{start_page}_to_{end_page}_{timestamp}.csv'
            return save_to_csv(products, filename)
    except Exception as e:
        print(f"Error generating CSV: {e}")
        return None

@app.route('/download-csv', methods=['GET'])
def download_csv():
    """Endpoint to download the latest product data as CSV"""
    try:
        filename = generate_csv()
        if filename:
            return send_file(
                filename,
                mimetype='text/csv',
                as_attachment=True,
                download_name=filename
            )
        return "No products found", 404
    except Exception as e:
        return str(e), 500

@app.route('/sync', methods=['POST'])
def sync_products():
    """Generate CSV and handle Shopify sync"""
    try:
        filename = generate_csv()
        if filename:
            # Try to sync with Shopify if credentials are available
            shop = request.args.get('shop')
            if shop and os.environ.get('ACCESS_TOKEN'):
                try:
                    session = shopify.Session(
                        shop,
                        os.environ.get('API_VERSION', '2023-10'),
                        os.environ.get('ACCESS_TOKEN')
                    )
                    shopify.ShopifyResource.activate_session(session)
                    # Future Shopify sync logic will go here
                except Exception as e:
                    print(f"Shopify sync error: {e}")

            download_url = f"/download-csv?file={filename}"
            return jsonify({
                'success': True,
                'message': f'Successfully scraped products. Click below to download:',
                'download_url': download_url,
                'filename': filename
            })
        return jsonify({
            'success': False,
            'message': 'No products found to sync'
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
    
    <form action="/sync" method="post">
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
    """

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
