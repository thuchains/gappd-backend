from flask import Blueprint

comments_bp = Blueprint('mechanics_bp', __name__)

from . import routes