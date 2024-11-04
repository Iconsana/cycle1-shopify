from app import celery
from app.scraper import scrape_acdc_products
import logging
from datetime import datetime
import json
import redis

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Redis client for storing progress
redis_client = redis.Redis(host='localhost', port=6379, db=0)

def update_progress(job_id, current_page, total_pages, products_count, status):
    """Update job progress in Redis"""
    progress = {
        'job_id': job_id,
        'current_page': current_page,
        'total_pages': total_pages,
        'products_count': products_count,
        'status': status,
        'timestamp': datetime.now().isoformat()
    }
    redis_client.set(
        f'scrape_progress:{job_id}',
        json.dumps(progress),
        ex=86400  # Expire after 24 hours
    )

@celery.task(bind=True)
def scrape_products_task(self, start_page=1, end_page=None, category=None):
    """Celery task for scraping products"""
    job_id = self.request.id
    total_products = 0
    
    try:
        # Initialize progress
        update_progress(job_id, start_page, end_page or "unknown", 0, "started")
        
        # Start scraping
        products = scrape_acdc_products(
            start_page=start_page,
            end_page=end_page,
            category=category
        )
        
        if products:
            # Generate filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'acdc_products_{timestamp}.csv'
            
            # Save to CSV
            import pandas as pd
            df = pd.DataFrame(products)
            df.to_csv(f'static/exports/{filename}', index=False)
            
            # Update final progress
            update_progress(
                job_id,
                end_page or "complete",
                end_page or "complete",
                len(products),
                "completed"
            )
            
            return {
                'status': 'success',
                'filename': filename,
                'products_count': len(products)
            }
            
        else:
            update_progress(job_id, 0, 0, 0, "failed")
            return {
                'status': 'error',
                'message': 'No products found'
            }
            
    except Exception as e:
        logger.error(f"Scraping error: {str(e)}")
        update_progress(job_id, 0, 0, 0, f"error: {str(e)}")
        return {
            'status': 'error',
            'message': str(e)
        }

def get_job_progress(job_id):
    """Get progress of a specific job"""
    progress = redis_client.get(f'scrape_progress:{job_id}')
    if progress:
        return json.loads(progress)
    return None
