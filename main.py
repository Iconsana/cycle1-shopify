from flask import Flask, request, jsonify, send_file, render_template
import pandas as pd
from datetime import datetime
import os
from scraper import scrape_acdc_products, save_to_csv

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY')

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
            filename = os.path.join('/tmp', f'acdc_products_{start_page}_to_{end_page}_{timestamp}.csv')
            return save_to_csv(products, filename)
    except Exception as e:
        print(f"Error generating CSV: {e}")
        return None

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
    """Generate CSV and handle sync"""
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
                
                // Try to parse JSON response
                let data;
                try {
                    data = await response.json();
                } catch (parseError) {
                    // If JSON parsing fails, show raw response text
                    const rawText = await response.text();
                    throw new Error(`Failed to parse response: ${rawText}`);
                }
                
                if (data.success) {
                    statusDiv.textContent = data.message;
                    
                    // Handle file download
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

        .progress-container {
            width: 100%;
            background-color: #f1f1f1;
            padding: 3px;
            border-radius: 3px;
            box-shadow: inset 0 1px 3px rgba(0, 0, 0, .2);
            margin-top: 10px;
            display: none;
        }

        .progress-bar {
            display: flex;
            height: 20px;
            background-color: #4CAF50;
            border-radius: 3px;
            transition: width 500ms ease-in-out;
            align-items: center;
            justify-content: center;
            color: white;
            width: 0%;
        }

        .progress-container.active {
            display: block;
        }
    </style>
    """

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
