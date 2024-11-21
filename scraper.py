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
                    
                    # Updated price handling
                    price_span = product.find('span', class_='product-price')
                    price_text = price_span.get_text(strip=True) if price_span else "0"
                    original_price = clean_price(price_text)
                    marked_up_price = round(original_price * 1.1, 2) if original_price > 0 else 0.0
                    
                    # Additional price check - look for regular price if available
                    regular_price_span = product.find('span', class_='regular-price')
                    if regular_price_span:
                        regular_price = clean_price(regular_price_span.get_text(strip=True))
                        if regular_price > 0:
                            original_price = regular_price
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
                    
                    # Print prices for debugging
                    print(f"Scraped: {product_code} - {clean_product_title}")
                    print(f"Price: Original={original_price}, Marked Up={marked_up_price}")
                    
                    products.append(product_data)
                    page_products += 1
                    
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
