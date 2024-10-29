# main.py
from flask import Flask, request, redirect, jsonify
import shopify
from config import *
import os

app = Flask(__name__)

def get_install_url(shop, client_id, scopes, redirect_uri):
    """Generate the installation URL"""
    install_url = f"https://{shop}/admin/oauth/authorize"
    install_url += f"?client_id={client_id}"
    install_url += f"&scope={scopes}"
    install_url += f"&redirect_uri={redirect_uri}"
    return install_url

@app.route('/')
def index():
    """Handle both the root path and installation"""
    shop = request.args.get('shop')
    if shop:
        # If shop parameter exists, handle installation
        scopes = 'write_products,read_products'  # Specify required scopes
        redirect_uri = f"https://{request.host}/callback"
        install_url = get_install_url(shop, SHOPIFY_API_KEY, scopes, redirect_uri)
        return redirect(install_url)
    return "ACDC Shopify Sync App is running!"

@app.route('/callback')
def callback():
    """Handle OAuth callback"""
    # Check for errors
    if request.args.get('error'):
        return f"Error: {request.args.get('error_description')}"

    # Get the temporary code
    code = request.args.get('code')
    shop = request.args.get('shop')
    
    if not code or not shop:
        return "Missing required parameters", 400

    # Exchange temporary code for permanent token
    access_token_url = f"https://{shop}/admin/oauth/access_token"
    access_token_payload = {
        'client_id': SHOPIFY_API_KEY,
        'client_secret': SHOPIFY_API_SECRET,
        'code': code,
    }
    
    try:
        session = shopify.Session(shop, API_VERSION, ACCESS_TOKEN)
        access_token = session.request_token(access_token_payload)
        
        # Store this access_token securely for future use
        # For now, we'll just print it (you should store it in a database)
        print(f"Access Token: {access_token}")
        
        return "App installed successfully! You can close this window."
    except Exception as e:
        return f"Error exchanging code for token: {str(e)}", 400

@app.route('/sync', methods=['POST'])
def sync_products():
    """Sync products from ACDC to Shopify"""
    from scraper import scrape_acdc_products  # Import here to avoid circular imports
    
    try:
        # Get products from ACDC
        products = scrape_acdc_products()
        successful_updates = 0
        
        if products:
            # Setup Shopify session
            shop_url = f"https://{SHOP_NAME}.myshopify.com"
            shopify.Session.setup(api_key=SHOPIFY_API_KEY, secret=SHOPIFY_API_SECRET)
            session = shopify.Session(shop_url, API_VERSION, ACCESS_TOKEN)
            shopify.ShopifyResource.activate_session(session)

            # Process each product
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
                    print(f"Successfully created/updated: {product['title']}")
                except Exception as e:
                    print(f"Error with product {product['title']}: {str(e)}")
            
            shopify.ShopifyResource.clear_session()
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
