from flask import Blueprint, request, jsonify
from ..services.scraper import scrape_acdc_products, save_to_csv
from .auth import verify_shop_session
import shopify
import os

products_blueprint = Blueprint('products', __name__)

@products_blueprint.route('/sync', methods=['POST'])
@verify_shop_session
def sync_products():
    """Handle product synchronization"""
    try:
        shop = request.args.get('shop')
        start_page = int(request.form.get('start_page', 1))
        end_page = int(request.form.get('end_page', 30))
        
        # Validate page ranges
        if start_page < 1 or end_page > 4331:
            raise ValueError("Invalid page range")
        if start_page > end_page:
            raise ValueError("Start page must be less than end page")
            
        # Initialize Shopify session
        session = shopify.Session(
            shop,
            os.environ.get('API_VERSION'),
            os.environ.get('ACCESS_TOKEN')
        )
        shopify.ShopifyResource.activate_session(session)
        
        try:
            # Scrape products
            products = scrape_acdc_products(start_page=start_page, end_page=end_page)
            
            if products:
                products_created = 0
                for product_data in products:
                    try:
                        new_product = shopify.Product()
                        new_product.title = product_data['Title']
                        new_product.body_html = product_data['Body (HTML)']
                        new_product.vendor = product_data['Vendor']
                        new_product.product_type = product_data['Type']
                        new_product.tags = product_data['Tags']
                        
                        # Set variant
                        variant = shopify.Variant()
                        variant.price = product_data['Variant Price']
                        variant.compare_at_price = product_data['Variant Compare At Price']
                        variant.sku = product_data['Variant SKU']
                        variant.inventory_management = 'shopify'
                        variant.inventory_quantity = 100
                        
                        new_product.variants = [variant]
                        
                        if new_product.save():
                            products_created += 1
                            
                    except Exception as e:
                        print(f"Error creating product {product_data['Title']}: {e}")
                        continue
                
                return jsonify({
                    'success': True,
                    'message': f'Successfully synced {products_created} products',
                    'total_processed': len(products),
                    'successful_syncs': products_created
                })
            
            return jsonify({
                'success': False,
                'message': 'No products found to sync'
            })
            
        finally:
            shopify.ShopifyResource.clear_session()
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@products_blueprint.route('/webhooks/products/create', methods=['POST'])
def product_create_webhook():
    """Handle product creation webhook"""
    # Verify webhook
    hmac_header = request.headers.get('X-Shopify-Hmac-SHA256')
    if not hmac_header:
        return 'No HMAC header', 401

    data = request.get_data()
    verified = verify_webhook(data, hmac_header)
    
    if not verified:
        return 'Invalid webhook', 401

    # Process webhook
    try:
        webhook_data = request.get_json()
        print(f"Product created: {webhook_data.get('title')}")
        return 'OK', 200
    except Exception as e:
        print(f"Error processing webhook: {e}")
        return 'Error', 500
