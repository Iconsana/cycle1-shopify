import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import re
import time

def clean_price(price_str):
    """Clean price string and convert to float."""
    try:
        price_str = price_str.replace('EXCL. VAT', '').replace('R', '').strip()
        price_str = re.sub(r'[^\d.,]', '', price_str).replace(',', '.')
        return float(price_str)
    except ValueError as e:
        print(f"Error converting price: {e}")
        return 0.0

def extract_product_code(product_element):
    """Extract only the product code from the product."""
    try:
        description = product_element.find('div', class_='product-description')
        if description:
            text_content = description.get_text()
            product_code_match = re.search(r'[A-Z0-9-]+(?=\s*(?:List Price|$))', text_content)
            if product_code_match:
                return product_code_match.group().strip()
    except Exception as e:
        print(f"Error extracting product code: {e}")
    return None

def clean_title(title_text):
    """Clean the product title."""
    try:
        title = re.sub(r'In Stock.*?(?=[A-Z0-9])', '', title_text, flags=re.DOTALL)
        title = re.sub(r'List Price.*', '', title, flags=re.DOTALL)
        title = re.sub(r'LIGHTING|INSTALLATION & WIRING ACCESSORIES.*?(?=[A-Z0-9])', '', title, flags=re.DOTALL)
        return ' '.join(title.split()).strip()
    except Exception as e:
        print(f"Error cleaning title: {e}")
        return title_text

def create_clean_description(product_code, title):
    """Create a clean HTML description."""
    return f"""
    <div class="product-description">
        <p>Product Code: {product_code}</p>
        <p>{title}</p>
        <p>Imported from ACDC Dynamics</p>
    </div>
    """

def scrape_acdc_products(start_page=1, end_page=50):
    """Scrape products from ACDC website with page range support."""
    base_url = 'https://acdc.co.za/2-home'
    products = []
    total_pages_scraped = 0
    
    print(f"Starting scrape from page {start_page} to {end_page}")
    
    for page_num in range(start_page, end_page + 1):
        try:
            page_url = f'{base_url}?page={page_num}'
            print(f"\nScraping page {page_num} of {end_page}")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(page_url, headers=headers, timeout=30)
            
            if response.status_code != 200:
                print(f"Failed to retrieve page {page_num}, status code: {response.status_code}")
                continue
                
            soup = BeautifulSoup(response.content, 'html.parser')
            product_containers = soup.find_all('article', class_='product-miniature')
            
            page_products = 0
            for product in product_containers:
                try:
                    product_code = extract_product_code(product)
                    if not product_code:
                        print("Skipping product - no code found")
                        continue

                    title_element = product.find('h2', class_='h3').find('a')
                    raw_title = title_element.get_text(strip=True) if title_element else ""
                    clean_product_title = clean_title(raw_title)
                    
                    price_span = product.find('span', class_='product-price')
                    if price_span:
                        original_price = clean_price(price_span.get_text(strip=True))
                        marked_up_price = round(original_price * 1.1, 2)
                        
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
                        print(f"Scraped: {product_code} - {clean_product_title}")
                    
                except Exception as e:
                    print(f"Error processing product: {e}")
                    continue
            
            total_pages_scraped += 1
            print(f"\nCompleted page {page_num}")
            print(f"Products on this page: {page_products}")
            print(f"Total products so far: {len(products)}")
            print(f"Progress: {total_pages_scraped}/{end_page - start_page + 1} pages")
            
            time.sleep(2)
                
        except Exception as e:
            print(f"Error processing page {page_num}: {e}")
            continue
    
    print(f"\nScraping completed!")
    print(f"Total pages scraped: {total_pages_scraped}")
    print(f"Total products scraped: {len(products)}")
    return products

def save_to_csv(products, filename=None):
    """Save products to CSV file."""
    if not filename:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'acdc_products_{timestamp}.csv'
    
    df = pd.DataFrame(products)
    df.to_csv(filename, index=False)
    print(f"Saved {len(products)} products to {filename}")
    return filename

if __name__ == "__main__":
    try:
        start = 1
        end = 3
        print(f"Testing scraper with pages {start}-{end}")
        
        products = scrape_acdc_products(start_page=start, end_page=end)
        if products:
            filename = save_to_csv(products)
            print(f"Test successful! Check {filename}")
        else:
            print("No products scraped during test")
            
    except KeyboardInterrupt:
        print("\nScraping interrupted by user")
    except Exception as e:
        print(f"Error during test: {e}")
