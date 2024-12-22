import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import re
import time
import random
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import logging
from threading import Event

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def clean_price(price_str):
    try:
        price_str = price_str.replace('EXCL. VAT', '').replace('R', '').strip()
        price_str = re.sub(r'[^\d.,]', '', price_str).replace(',', '.')
        return float(price_str)
    except (ValueError, AttributeError) as e:
        logger.error(f"Error converting price: {e}")
        return 0.0

def extract_product_code(product_element):
    try:
        description = product_element.find('div', class_='product-description')
        if description:
            text_content = description.get_text()
            product_code_match = re.search(r'[A-Z0-9-]+(?=\s*(?:List Price|$))', text_content)
            if product_code_match:
                return product_code_match.group().strip()
    except Exception as e:
        logger.error(f"Error extracting product code: {e}")
    return None

def clean_title(title_text):
    try:
        title = re.sub(r'In Stock.*?(?=[A-Z0-9])', '', title_text, flags=re.DOTALL)
        title = re.sub(r'List Price.*', '', title, flags=re.DOTALL)
        title = re.sub(r'LIGHTING|INSTALLATION & WIRING ACCESSORIES.*?(?=[A-Z0-9])', '', title, flags=re.DOTALL)
        return ' '.join(title.split()).strip()
    except Exception as e:
        logger.error(f"Error cleaning title: {e}")
        return title_text

def create_clean_description(product_code, title):
    return f"""
    <div class="product-description">
        <p>Product Code: {product_code}</p>
        <p>{title}</p>
        <p>Imported from ACDC Dynamics</p>
    </div>
    """

def scrape_acdc_products(start_page=1, end_page=50, progress_callback=None, cancel_event=None):
    """Enhanced scraper with progress tracking and cancellation support"""
    base_url = 'https://acdc.co.za/2-home'
    products = []
    total_pages = end_page - start_page + 1
    pages_processed = 0
    
    session = requests.Session()
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    
    user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:100.0) Gecko/20100101 Firefox/100.0'
    ]
    
    if progress_callback:
        progress_callback("Starting scrape...", 0, total_pages)
    
    for page_num in range(start_page, end_page + 1):
        if cancel_event and cancel_event.is_set():
            if progress_callback:
                progress_callback("Scrape cancelled", pages_processed, total_pages, 'info')
            break
            
        try:
            page_url = f'{base_url}?page={page_num}'
            headers = {'User-Agent': random.choice(user_agents)}
            
            if progress_callback:
                progress_callback(f"Scraping page {page_num}", pages_processed, total_pages)
            
            response = session.get(page_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            product_containers = soup.find_all('article', class_='product-miniature')
            
            page_products = 0
            for product in product_containers:
                if cancel_event and cancel_event.is_set():
                    break
                    
                try:
                    product_code = extract_product_code(product)
                    if not product_code:
                        continue

                    title_element = product.find('h2', class_='h3').find('a')
                    raw_title = title_element.get_text(strip=True) if title_element else ""
                    clean_product_title = clean_title(raw_title)
                    
                    price_span = product.find('span', class_='price')
                    original_price = 0.0
                    if price_span:
                        original_price = clean_price(price_span.get_text(strip=True))
                    else:
                        price_span = product.find('span', class_='product-price')
                        if price_span:
                            original_price = clean_price(price_span.get_text(strip=True))
                    
                    marked_up_price = round(original_price * 1.1, 2) if original_price > 0 else 0.0
                    
                    product_data = {
                        'Handle': product_code.lower(),
                        'Title': clean_product_title,
                        'Body (HTML)': create_clean_description(product_code, clean_product_title),
                        'Vendor': 'ACDC',
                        'Product Category': 'Electrical & Electronics',
                        'Type': 'Electrical Components',
                        'Tags': f'ACDC, {product_code}',
                        'Published': 'TRUE',
                        'Option1 Name': 'Title',
                        'Option1 Value': 'Default Title',
                        'Variant SKU': product_code,
                        'Variant Grams': '0',
                        'Variant Inventory Tracker': 'shopify',
                        'Variant Inventory Qty': '100',
                        'Variant Inventory Policy': 'deny',
                        'Variant Fulfillment Service': 'manual',
                        'Variant Price': str(marked_up_price),
                        'Variant Compare At Price': str(original_price),
                        'Variant Requires Shipping': 'TRUE',
                        'Variant Taxable': 'TRUE',
                        'Status': 'active'
                    }
                    
                    products.append(product_data)
                    page_products += 1
                    
                except Exception as e:
                    logger.error(f"Error processing product: {e}")
                    continue
            
            pages_processed += 1
            if progress_callback:
                progress_callback(
                    f"Completed page {page_num} - Found {page_products} products",
                    pages_processed,
                    total_pages,
                    'success'
                )
            
            time.sleep(random.uniform(2, 4))
                
        except Exception as e:
            logger.error(f"Error processing page {page_num}: {e}")
            if progress_callback:
                progress_callback(
                    f"Error on page {page_num}: {str(e)}",
                    pages_processed,
                    total_pages,
                    'error'
                )
            time.sleep(5)  # Longer delay after error
            continue
    
    if progress_callback:
        progress_callback(
            f"Scraping completed! Total products: {len(products)}",
            total_pages,
            total_pages,
            'success'
        )
    
    return products

def save_to_csv(products, filename=None):
    if not filename:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'/tmp/acdc_products_{timestamp}.csv'
    
    df = pd.DataFrame(products)
    df.to_csv(filename, index=False)
    logger.info(f"Saved {len(products)} products to {filename}")
    return filename

# Make sure these are available for import
__all__ = ['scrape_acdc_products', 'save_to_csv']
