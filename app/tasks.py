from cycle1-shopify.app import celery
from cycle1-shopify.app.scraper import scrape_acdc_products, save_to_csv
from celery.utils.log import get_task_logger
import os
from datetime import datetime

# ... rest of your tasks.py code stays the same ...
# Configure logger for tasks
logger = get_task_logger(__name__)

@celery.task(bind=True)
def scrape_products_task(self, start_page=1, end_page=None, category=None):
    """
    Celery task for scraping products with progress tracking
    """
    try:
        # Initialize progress
        self.update_state(
            state='PROGRESS',
            meta={'current': 0, 'total': end_page or MAX_PAGES, 'status': 'Starting scrape...'}
        )

        # Start scraping
        products = scrape_acdc_products(
            start_page=start_page,
            end_page=end_page,
            max_pages=MAX_PAGES
        )

        if products:
            # Generate timestamp-based filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'acdc_products_{timestamp}.csv'
            filepath = os.path.join(UPLOAD_FOLDER, filename)

            # Save to CSV
            save_to_csv(products, filepath)

            # Task completion metadata
            result = {
                'status': 'completed',
                'file': filename,
                'count': len(products),
                'timestamp': timestamp,
                'download_url': f'/download/{filename}'
            }

            logger.info(f"Scraping completed: {len(products)} products saved to {filename}")
            return result

        else:
            logger.warning("No products were scraped")
            return {
                'status': 'completed',
                'error': 'No products found',
                'count': 0
            }

    except Exception as e:
        logger.error(f"Scraping failed: {str(e)}", exc_info=True)
        raise

@celery.task(bind=True)
def process_category_task(self, category, start_page=1, end_page=None):
    """
    Task for processing specific product categories
    """
    try:
        self.update_state(
            state='PROGRESS',
            meta={'status': f'Processing category: {category}'}
        )

        # Implement category-specific scraping logic here
        products = scrape_acdc_products(
            start_page=start_page,
            end_page=end_page,
            category=category
        )

        if products:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'acdc_{category}_{timestamp}.csv'
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            
            save_to_csv(products, filepath)
            
            return {
                'status': 'completed',
                'category': category,
                'file': filename,
                'count': len(products)
            }
        
        return {
            'status': 'completed',
            'category': category,
            'error': 'No products found',
            'count': 0
        }

    except Exception as e:
        logger.error(f"Category processing failed: {str(e)}", exc_info=True)
        raise

@celery.task
def cleanup_old_files():
    """
    Periodic task to clean up old export files
    """
    try:
        # Keep files for 24 hours
        cutoff = datetime.now().timestamp() - (24 * 60 * 60)
        
        for filename in os.listdir(UPLOAD_FOLDER):
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            if os.path.getctime(filepath) < cutoff:
                os.remove(filepath)
                logger.info(f"Removed old file: {filename}")
                
    except Exception as e:
        logger.error(f"Cleanup failed: {str(e)}", exc_info=True)
        raise

# Schedule periodic tasks
@celery.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    # Run cleanup every 12 hours
    sender.add_periodic_task(
        60 * 60 * 12,  # 12 hours
        cleanup_old_files.s(),
        name='cleanup-old-files'
    )
