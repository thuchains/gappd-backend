import os
from flask import Flask
from app.extensions import ma, limiter, cache
from app.models import db
from app.blueprints.users import users_bp
from app.blueprints.posts import posts_bp
from app.blueprints.comments import comments_bp
from app.blueprints.event_posts import event_posts_bp
from app.blueprints.photos import photos_bp
from flask_swagger_ui import get_swaggerui_blueprint
from flask_cors import CORS

SWAGGER_URL = '/api/docs'
API_URL = '/static/swagger.yaml'

swagger_blueprint = get_swaggerui_blueprint(SWAGGER_URL, API_URL, config={'app_name': "Gapp'd API"})

def create_app(config_name):
    app = Flask(__name__)
    app.config.from_object(f"config.{config_name}")

    db.init_app(app)
    ma.init_app(app)
    limiter.init_app(app)
    cache.init_app(app)
    CORS(app)

    app.register_blueprint(users_bp, url_prefix='/users')
    app.register_blueprint(posts_bp, url_prefix='/posts')
    app.register_blueprint(comments_bp, url_prefix='/comments')
    app.register_blueprint(event_posts_bp, url_prefix='/events')
    app.register_blueprint(photos_bp, url_prefix='/photos')
    app.register_blueprint(swagger_blueprint, url_prefix=SWAGGER_URL)

    return app

