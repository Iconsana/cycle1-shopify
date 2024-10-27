from flask import Flask, request, redirect, jsonify
import shopify
from config import *
from scraper import scrape_acdc_products
import os

app = Flask(__name__)

def setup_shopify_session():
    """Setup Shopify session with store configuration"""
    shop_url = f"https://{SHOP_NAME}.myshopify.com"
    shopify.ShopifyResource.set_site(f"{shop_url}/admin/api/{API_VERSION}")
    shopify.Session.setup(api_key=SHOPIFY_API_KEY, secret=SHOPIFY_API_SECRET)
    return shopify.Session(shop_url, API_VERSION, ACCESS_TOKEN)

@app.route('/')
def index():
    return "ACDC Shopify Sync App is running!"

@app.route('/install')
def install():
    shop_url = request.args.get('shop')
    if not shop_url:
        return "Missing shop parameter", 400
    
    auth_url = f"https://{shop_url}/admin/oauth/authorize"
    auth_params = {
        'client_id': SHOPIFY_API_KEY,
        'scope': 'write_products,read_products',
        'redirect_uri': f"https://{request.host}/callback"
    }
    
    return redirect(auth_url + '?' + '&'.join(f"{key}={value}" for key, value in auth_params.items()))

@app.route('/callback')
def callback():
    return "App installed successfully!"

@app.route('/sync', methods=['POST'])
def trigger_sync():
    try:
        products = scrape_acdc_products()
        successful_updates = 0
        
        if products:
            session = setup_shopify_session()
            for product in products:
                try:
                    shopify_product = shopify.Product()
                    shopify_product.title = product['title']
                    shopify_product.variants = [{
                        'price': str(product['marked_up_price']),
                        'sku': product['sku'],
                        'inventory_management': 'shopify'
                    }]
                    shopify_product.save()
                    successful_updates += 1
                except Exception as e:
                    print(f"Error updating product {product['title']}: {str(e)}")
                    
            return jsonify({
                'success': True,
                'message': f'Successfully updated {successful_updates} out of {len(products)} products'
            })
        
        return jsonify({
            'success': False,
            'message': 'No products found to sync'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
