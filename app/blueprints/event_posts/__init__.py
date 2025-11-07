from flask import Blueprint

event_posts_bp = Blueprint('event_posts_bp', __name__)

from . import routes