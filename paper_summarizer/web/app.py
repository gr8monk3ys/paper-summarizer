"""Flask application factory."""

import os
from flask import Flask
from .config import config

def create_app(config_name=None):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    
    # Load configuration
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    app.config.from_object(config[config_name])
    
    # Configure logging
    if not app.debug:
        import logging
        logging.basicConfig(level=logging.INFO)
    
    # Register blueprints
    from .routes import bp
    app.register_blueprint(bp)
    
    # Create upload folder if it doesn't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    return app
