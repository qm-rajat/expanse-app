import os
import logging
from flask import Flask
from flask_pymongo import PyMongo
from .config import Config
from flask_bcrypt import Bcrypt

mongo = PyMongo()
bcrypt = Bcrypt()

def create_app():
    template_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../templates'))
    static_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../static'))
    app = Flask(__name__, instance_relative_config=True, template_folder=template_dir, static_folder=static_dir)
    app.config.from_object(Config)
    app.config.from_pyfile('config.py', silent=True)
    
    # Session configuration
    app.config['PERMANENT_SESSION_LIFETIME'] = 30 * 24 * 60 * 60  # 30 days
    app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

    # Setup logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('expense_tracker')
    app.logger.handlers = logger.handlers
    app.logger.setLevel(logging.INFO)

    # Initialize MongoDB
    mongo.init_app(app)
    
    # Initialize Bcrypt
    bcrypt.init_app(app)

    # Add custom escapejs filter for Jinja2 templates
    import json
    from jinja2 import Undefined

    def escapejs_filter(value):
        if isinstance(value, Undefined):
            value = ''
        return json.dumps(value)
    app.jinja_env.filters['escapejs'] = escapejs_filter

    # Register blueprints here (routes, auth, admin)
    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)
    from .auth import auth as auth_blueprint
    app.register_blueprint(auth_blueprint)
    from .admin import admin as admin_blueprint
    app.register_blueprint(admin_blueprint)

    return app

# Export mongo for import in other modules
from . import mongo
