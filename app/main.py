# app/main.py
from flask import (
    request, 
    jsonify, 
    send_file, 
    render_template,
    url_for,
    abort
)
from celery.result import AsyncResult
import pandas as pd
from datetime import datetime
import os

from app import app
from app.tasks import scrape_products_task, process_category_task
from app.config import UPLOAD_FOLDER

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def get_task_status(task_id):
    """Get the status of a Celery task"""
    task = AsyncResult(task_id)
    if task.state == 'PENDING':
        response = {
            'state': task.state,
            'status': 'Task is pending...'
        }
    elif task.state == 'PROGRESS':
        response = {
            'state': task.state,
            'status': task.info.get('status', ''),
            'current': task.info.get('current', 0),
            'total': task.info.get('total', 1),
            'percent': int(task.info.get('current', 0) / task.info.get('total', 1) * 100)
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
    return response

@app.route('/')
def index():
    """Home page with scraping options"""
    return render_template('index.html')

@app.route('/sync', methods=['POST'])
def sync_products():
    """Start a new scraping task"""
    try:
        # Get parameters from request
        category = request.form.get('category')
        start_page = int(request.form.get('start_page', 1))
        end_page = request.form.get('end_page')
        if end_page:
            end_page = int(end_page)

        # Start appropriate task
        if category:
            task = process_category_task.delay(
                category=category,
                start_page=start_page,
                end_page=end_page
            )
        else:
            task = scrape_products_task.delay(
                start_page=start_page,
                end_page=end_page
            )

        return jsonify({
            'success': True,
            'message': 'Scraping task started',
            'task_id': task.id
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/status/<task_id>')
def task_status(task_id):
    """Check the status of a task"""
    return jsonify(get_task_status(task_id))

@app.route('/download/<filename>')
def download_file(filename):
    """Download a generated CSV file"""
    try:
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        if not os.path.exists(file_path):
            abort(404, description="File not found")
            
        return send_file(
            file_path,
            mimetype='text/csv',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return str(e), 500

@app.route('/categories')
def get_categories():
    """Get available product categories"""
    categories = [
        'Lighting',
        'Wiring',
        'Distribution',
        'Protection',
        'Industrial'
    ]
    return jsonify(categories)

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return jsonify({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat()
    })

@app.errorhandler(404)
def not_found_error(error):
    return jsonify({
        'error': 'Not Found',
        'message': str(error)
    }), 404

@app.errorhandler(500)
def internal_error(error):
    return jsonify({
        'error': 'Internal Server Error',
        'message': str(error)
    }), 500

# Optional: Add API documentation endpoint
@app.route('/api/docs')
def api_docs():
    """API documentation endpoint"""
    return jsonify({
        'endpoints': {
            '/sync': {
                'method': 'POST',
                'description': 'Start a new scraping task',
                'parameters': {
                    'category': 'Optional category name',
                    'start_page': 'Starting page number (default: 1)',
                    'end_page': 'Ending page number (optional)'
                }
            },
            '/status/<task_id>': {
                'method': 'GET',
                'description': 'Get task status'
            },
            '/download/<filename>': {
                'method': 'GET',
                'description': 'Download generated CSV file'
            },
            '/categories': {
                'method': 'GET',
                'description': 'Get available product categories'
            }
        }
    })

if __name__ == '__main__':
    # Only for development
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
