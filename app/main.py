from flask import request, jsonify, send_file
from datetime import datetime
import os
from app import app  # Import the Flask app instance
from app.scraper import scrape_acdc_products
from app.tasks import scrape_products_task  # Import Celery task

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
        # Start celery task
        task = scrape_products_task.delay()
        return jsonify({
            'success': True,
            'message': 'Scraping started. Check status using the task ID.',
            'task_id': task.id
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/status/<task_id>')
def task_status(task_id):
    """Check task status"""
    task = scrape_products_task.AsyncResult(task_id)
    if task.state == 'PENDING':
        response = {
            'state': task.state,
            'status': 'Pending...'
        }
    elif task.state == 'SUCCESS':
        response = {
            'state': task.state,
            'result': task.result
        }
    else:
        response = {
            'state': task.state,
            'status': str(task.info)
        }
    return jsonify(response)

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

# Remove the if __name__ == '__main__' block since we're using gunicorn
