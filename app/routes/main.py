from flask import Blueprint, render_template

main_blueprint = Blueprint('main', __name__)

@main_blueprint.route('/')
def index():
    """Landing page"""
    return render_template('index.html')
