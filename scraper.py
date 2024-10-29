import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import re

def clean_price(price_str):
    """Clean price string and convert to float."""
    price_str = price_str.replace('EXCL. VAT', '').replace('R', '').strip()
    price_str = re.sub(r'[^\d.,]', '', price_str)
    price_str = price_str.replace(',', '.')
    return float(price_str)

def get_product_sku(product_element):
    """Extract SKU from product link text."""
    sku_element = product_element.find('h2', class_='h3').find('a')
    if sku_element:
        return sku_element.get_text(strip=True)
    return None

def scrape_acdc_products(max_pages=5):
    base_url = 'https://acdc.co.za/2-home'
    products = []
    
    for page_num in range(1, max_pages + 1):
        page_url = f'{base_url}?page={page_num}'
        print(f"Scraping page {page_num}: {page_url}")
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(page_url, headers=headers)
            
            if response.status_code != 200:
                print(f"Failed to retrieve page {page_num}, status code: {response.status_code}")
                continue
                
            soup = BeautifulSoup(response.content, 'html.parser')
            product_containers = soup.find_all('article', class_='product-miniature')
            
            for product in product_containers:
                try:
                    # Get SKU (product code) and title
                    sku = get_product_sku(product)
                    description = product.find('div', class_='product-description').get_text(strip=True)
                    price_span = product.find('span', class_='product-price')
                    
                    if price_span and sku:
                        original_price = clean_price(price_span.get_text(strip=True))
                        marked_up_price = round(original_price * 1.1, 2)  # 10% markup
                        
                        # Create Shopify-structured product data
                        product_data = {
                            'Handle': sku.lower(),  # Use SKU for handle
                            'Title': description,   # Use full description as title
                            'Body (HTML)': f'Product Code: {sku}<br>Imported from ACDC.',
                            'Vendor': 'ACDC',
                            'Product Category': 'Electrical & Electronics',
                            'Type': 'Electrical Components',
                            'Tags': f'ACDC, {sku}',
                            'Published': 'TRUE',
                            'Option1 Name': 'Title',
                            'Option1 Value': 'Default Title',
                            'Variant SKU': sku,     # Use product code as SKU
                            'Variant Grams': '0',
                            'Variant Inventory Tracker': 'shopify',
                            'Variant Inventory Qty': '100',  # Default stock
                            'Variant Inventory Policy': 'deny',
                            'Variant Fulfillment Service': 'manual',
                            'Variant Price': str(marked_up_price),
                            'Variant Compare At Price': str(original_price),
                            'Variant Requires Shipping': 'TRUE',
                            'Variant Taxable': 'TRUE',
                            'Status': 'active'
                        }
                        
                        products.append(product_data)
                        print(f"Successfully scraped: {sku} - Original: R{original_price} - Marked up: R{marked_up_price}")
                    
                except Exception as e:
                    print(f"Error processing product: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error scraping page {page_num}: {e}")
            continue
            
    return products

def save_to_shopify_csv(products, filename=None):
    """Save products to Shopify-compatible CSV format."""
    if not filename:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'acdc_products_shopify_{timestamp}.csv'
    
    df = pd.DataFrame(products)
    
    # Ensure columns are in correct order
    shopify_columns = [
        'Handle', 'Title', 'Body (HTML)', 'Vendor', 'Product Category', 'Type', 
        'Tags', 'Published', 'Option1 Name', 'Option1 Value', 'Variant SKU',
        'Variant Grams', 'Variant Inventory Tracker', 'Variant Inventory Qty',
        'Variant Inventory Policy', 'Variant Fulfillment Service', 'Variant Price',
        'Variant Compare At Price', 'Variant Requires Shipping', 'Variant Taxable',
        'Status'
    ]
    
    # Reorder columns and fill missing ones with empty strings
    for col in shopify_columns:
        if col not in df.columns:
            df[col] = ''
    
    df = df[shopify_columns]
    df.to_csv(filename, index=False)
    print(f"Saved {len(products)} products to {filename}")
    return filename

if __name__ == "__main__":
    products = scrape_acdc_products(max_pages=5)
    if products:
        save_to_shopify_csv(products)
    else:
        print("No products were scraped successfully.")
