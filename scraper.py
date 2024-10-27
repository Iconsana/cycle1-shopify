import requests
from bs4 import BeautifulSoup
import re
import pandas as pd

def clean_price(price_str):
    """Clean price string and convert to float."""
    price_str = price_str.replace('EXCL. VAT', '').replace('R', '').strip()
    price_str = re.sub(r'[^\d.,]', '', price_str)
    price_str = price_str.replace(',', '.')
    return float(price_str)

def apply_markup(price, markup_percentage=10):
    """Apply markup to price."""
    return round(price * (1 + markup_percentage/100), 2)

def scrape_acdc_products(max_pages=5):
    base_url = 'https://acdc.co.za/2-home'
    products = []
    
    for page_num in range(1, max_pages + 1):
        page_url = f'{base_url}?page={page_num}'
        print(f"Scraping page {page_num}: {page_url}")
        
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(page_url, headers=headers)
            
            if response.status_code != 200:
                print(f"Failed to retrieve page {page_num}, status code: {response.status_code}")
                continue
                
            soup = BeautifulSoup(response.content, 'html.parser')
            product_containers = soup.find_all('article', class_='product-miniature')
            
            if not product_containers:
                print(f"No products found on page {page_num}")
                continue
            
            for product in product_containers:
                try:
                    product_title = product.find('h2', class_='h3').find('a').get_text(strip=True)
                    price_span = product.find('span', class_='product-price')
                    
                    if price_span:
                        original_price = clean_price(price_span.get_text(strip=True))
                        marked_up_price = apply_markup(original_price)
                        product_url = product.find('h2', class_='h3').find('a')['href']
                        
                        product_data = {
                            'title': product_title,
                            'sku': product_title,
                            'original_price': original_price,
                            'marked_up_price': marked_up_price,
                            'url': product_url
                        }
                        
                        products.append(product_data)
                        print(f"Successfully scraped: {product_title} - Original: R{original_price} - Marked up: R{marked_up_price}")
                    
                except Exception as e:
                    print(f"Error processing product: {e}")
                    continue
                    
        except Exception as e:
            print(f"Error scraping page {page_num}: {e}")
            continue
            
    return products

def save_to_csv(products, filename='acdc_products.csv'):
    """Save products to CSV file."""
    df = pd.DataFrame(products)
    df.to_csv(filename, index=False)
    print(f"Saved {len(products)} products to {filename}")

if __name__ == "__main__":
    products = scrape_acdc_products(max_pages=5)
    if products:
        save_to_csv(products)
        print(f"\nTotal products scraped: {len(products)}")
    else:
        print("No products were scraped successfully.")
