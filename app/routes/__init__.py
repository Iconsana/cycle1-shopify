from flask import Blueprint
from .auth import auth_blueprint
from .products import products_blueprint
from .main import main_blueprint

def init_routes(app):
    app.register_blueprint(main_blueprint)
    app.register_blueprint(auth_blueprint)
    app.register_blueprint(products_blueprint)
