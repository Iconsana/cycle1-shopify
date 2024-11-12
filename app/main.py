# main.py
from flask import Flask, request, redirect, jsonify, send_file
import pandas as pd
from datetime import datetime
import os
from scraper import scrape_acdc_products

app = Flask(__name__)

def generate_csv():
    """Generate CSV from scraped products"""
    products = scrape_acdc_products()
    if products:
        # Create DataFrame
        df = pd.DataFrame(products)
        
        # Add timestamp to filename
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'acdc_products_{timestamp}.csv'
        
        # Save to CSV
        df.to_csv(filename, index=False)
        return filename
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
    """Generate CSV and return download link"""
    try:
        filename = generate_csv()
        if filename:
            download_url = f"https://{request.host}/download-csv"
            return jsonify({
                'success': True,
                'message': f'Successfully scraped products. Click the link below to download:',
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
    <p>Use the buttons below to:</p>
    <form action="/sync" method="post">
        <button type="submit">Scrape Products</button>
    </form>
    <br>
    <a href="/download-csv">
        <button>Download Latest CSV</button>
    </a>
    """

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
