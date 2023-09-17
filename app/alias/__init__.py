from flask import Blueprint

bp = Blueprint("alias", __name__)

from app.alias import routes

