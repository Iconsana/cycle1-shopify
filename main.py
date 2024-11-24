from flask import Flask, request, redirect, jsonify, send_file, render_template
import pandas as pd
from datetime import datetime
import os
from scraper import scrape_acdc_products, save_to_csv

app = Flask(__name__)

def generate_csv():
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

@app.route('/sync', methods=['POST'])
def sync_products():
    try:
        filename = generate_csv()
        if filename:
            base_filename = os.path.basename(filename)
            return jsonify({
                'success': True,
                'message': 'Successfully scraped products. Download will start automatically.',
                'download_url': f'/download-csv?file={base_filename}',
                'filename': base_filename
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
            statusDiv.innerHTML = 'Scraping in progress...';
            
            fetch('/sync', {
                method: 'POST',
                body: new FormData(e.target)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    statusDiv.innerHTML = data.message;
                    // Create hidden download link and click it
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
