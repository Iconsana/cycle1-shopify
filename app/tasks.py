# tasks.py
from celery import Celery
import redis
from flask import current_app
import os
import json
from datetime import datetime

# Setup Celery
celery = Celery('tasks', broker='redis://localhost:6379/0')

# Setup Redis for storing progress
redis_client = redis.Redis(host='localhost', port=6379, db=0)

class ChunkedScraper:
    def __init__(self, chunk_size=100):
        self.chunk_size = chunk_size
        self.redis_client = redis_client

    def get_job_progress(self, job_id):
        """Get progress of a scraping job"""
        progress = self.redis_client.get(f"job_progress:{job_id}")
        return json.loads(progress) if progress else None

    def save_progress(self, job_id, current_page, total_products, status):
        """Save job progress to Redis"""
        progress = {
            'job_id': job_id,
            'current_page': current_page,
            'total_products': total_products,
            'status': status,
            'last_updated': datetime.now().isoformat()
        }
        self.redis_client.set(
            f"job_progress:{job_id}",
            json.dumps(progress),
            ex=86400  # Expire after 24 hours
        )

@celery.task(bind=True)
def scrape_chunk(self, start_page, end_page, job_id):
    """Scrape a chunk of pages"""
    scraper = ChunkedScraper()
    products = []
    current_page = start_page
    
    while current_page <= end_page:
        try:
            # Scrape page
            page_products = scrape_page(current_page)
            products.extend(page_products)
            
            # Update progress
            scraper.save_progress(
                job_id,
                current_page,
                len(products),
                'in_progress'
            )
            
            # Save chunk if we've reached chunk size
            if len(products) >= scraper.chunk_size:
                save_chunk(products, job_id, current_page)
                products = []  # Clear products after saving
                
        except Exception as e:
            scraper.save_progress(
                job_id,
                current_page,
                len(products),
                f'error: {str(e)}'
            )
            raise
            
        current_page += 1
    
    # Save any remaining products
    if products:
        save_chunk(products, job_id, current_page)
    
    # Mark job as complete
    scraper.save_progress(job_id, end_page, len(products), 'completed')
    return job_id

def save_chunk(products, job_id, current_page):
    """Save a chunk of products to CSV"""
    if not products:
        return
        
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'products_chunk_{job_id}_{current_page}_{timestamp}.csv'
    
    df = pd.DataFrame(products)
    df.to_csv(f'chunks/{filename}', index=False)
    return filename

# main.py modifications
from flask import Flask, jsonify, send_file
from celery.result import AsyncResult

app = Flask(__name__)

@app.route('/start-scrape', methods=['POST'])
def start_scrape():
    """Start a new scraping job"""
    chunk_size = int(request.args.get('chunk_size', 100))
    total_pages = 4176  # Total known pages
    
    # Create job ID
    job_id = f"scrape_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    # Start background task
    task = scrape_chunk.delay(1, total_pages, job_id)
    
    return jsonify({
        'job_id': job_id,
        'task_id': task.id,
        'status': 'started',
        'message': 'Scraping started in background'
    })

@app.route('/job-status/<job_id>')
def job_status(job_id):
    """Get status of a scraping job"""
    scraper = ChunkedScraper()
    progress = scraper.get_job_progress(job_id)
    
    if not progress:
        return jsonify({'error': 'Job not found'}), 404
        
    return jsonify(progress)

@app.route('/download-chunk/<job_id>/<chunk_number>')
def download_chunk(job_id, chunk_number):
    """Download a specific chunk of products"""
    try:
        chunk_files = os.listdir('chunks')
        target_file = [f for f in chunk_files if f.startswith(f'products_chunk_{job_id}_{chunk_number}_')]
        
        if not target_file:
            return jsonify({'error': 'Chunk not found'}), 404
            
        return send_file(
            f'chunks/{target_file[0]}',
            mimetype='text/csv',
            as_attachment=True
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500
