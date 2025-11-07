from flask import Blueprint

photos_bp = Blueprint('photos_bp', __name__)

from . import routes
