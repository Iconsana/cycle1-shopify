from flask import Blueprint, request, redirect, jsonify, session, current_app
import shopify
from functools import wraps
import os

auth_blueprint = Blueprint('auth', __name__)

def verify_webhook(data, hmac_header):
    """Verify webhook request is from Shopify"""
    return shopify.Webhook.verify_webhook_hmac(
        hmac_header,
        data,
        os.environ.get('SHOPIFY_API_SECRET')
    )

def verify_shop_session(f):
    """Decorator to verify shop has valid session"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        shop = request.args.get('shop')
        if not shop:
            return jsonify({"error": "Shop parameter required"}), 400
            
        if not session.get('shopify_token'):
            return redirect(f"/install?shop={shop}")
            
        return f(*args, **kwargs)
    return decorated_function

@auth_blueprint.route('/install')
def install():
    """App installation endpoint"""
    shop = request.args.get('shop')
    if not shop:
        return "Missing shop parameter", 400
        
    auth_url = shopify.OAuth.create_auth_url(
        shop.strip(),
        os.environ.get('SCOPES').split(','),
        f"{os.environ.get('HOST')}/auth/callback",
        os.environ.get('SHOPIFY_API_KEY')
    )
    return redirect(auth_url)

@auth_blueprint.route('/auth/callback')
def callback():
    """OAuth callback handler"""
    try:
        shop = request.args.get('shop')
        
        # Verify the state parameter
        state = request.args.get('state')
        if not state or session.get('state') != state:
            return "Invalid state parameter", 403
            
        access_token = shopify.OAuth.access_token(
            shop.strip(),
            request.args.get('code'),
            os.environ.get('SHOPIFY_API_SECRET')
        )
        
        session['shopify_token'] = access_token
        session['shop'] = shop
        
        # Initialize webhooks
        init_webhooks(shop, access_token)
        
        return redirect(f"/app?shop={shop}")
        
    except Exception as e:
        return f"Error during authentication: {str(e)}", 500

def init_webhooks(shop, access_token):
    """Initialize required webhooks"""
    try:
        shopify_session = shopify.Session(shop, access_token)
        shopify.ShopifyResource.activate_session(shopify_session)
        
        # Create webhooks for relevant events
        webhooks = {
            'products/create': f'{os.environ.get("HOST")}/webhooks/products/create',
            'products/update': f'{os.environ.get("HOST")}/webhooks/products/update',
            'products/delete': f'{os.environ.get("HOST")}/webhooks/products/delete',
        }
        
        for topic, address in webhooks.items():
            webhook = shopify.Webhook()
            webhook.topic = topic
            webhook.address = address
            webhook.format = 'json'
            webhook.save()
            
    except Exception as e:
        print(f"Error creating webhooks: {e}")
    finally:
        shopify.ShopifyResource.clear_session()
