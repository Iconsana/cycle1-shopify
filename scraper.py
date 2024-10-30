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

def extract_product_code(product_element):
    """Extract only the product code from the product."""
    try:
        # Find product code section
        description = product_element.find('div', class_='product-description')
        if description:
            # The product code is typically after the last occurrence of product title
            text_content = description.get_text()
            # Use regex to find the product code pattern (usually all caps with numbers and dashes)
            product_code_match = re.search(r'[A-Z0-9-]+(?=\s*(?:List Price|$))', text_content)
            if product_code_match:
                return product_code_match.group().strip()
    except Exception as e:
        print(f"Error extracting product code: {e}")
    return None

def clean_title(title_text):
    """Clean the product title."""
    try:
        # Remove inventory status, category, and price information
        title = re.sub(r'In Stock.*?(?=[A-Z0-9])', '', title_text, flags=re.DOTALL)
        title = re.sub(r'List Price.*', '', title, flags=re.DOTALL)
        title = re.sub(r'LIGHTING|INSTALLATION & WIRING ACCESSORIES.*?(?=[A-Z0-9])', '', title, flags=re.DOTALL)
        # Remove multiple spaces and trim
        title = ' '.join(title.split())
        return title.strip()
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
                    # Get product code first
                    product_code = extract_product_code(product)
                    if not product_code:
                        print("Skipping product - no code found")
                        continue

                    # Get raw title and clean it
                    raw_title = product.find('h2', class_='h3').find('a').get_text(strip=True)
                    clean_product_title = clean_title(raw_title)
                    
                    # Get price
                    price_span = product.find('span', class_='product-price')
                    if price_span:
                        original_price = clean_price(price_span.get_text(strip=True))
                        marked_up_price = round(original_price * 1.1, 2)  # 10% markup
                        
                        # Create Shopify-structured product data
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
                        print(f"Successfully scraped: {product_code} - {clean_product_title}")
                    
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
