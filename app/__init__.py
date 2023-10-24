from flask import Flask
from config import Config

from flask_caching import Cache
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy


app = Flask(__name__)
app.config.from_object(Config)

cache = Cache(app)
db = SQLAlchemy(app)
login = LoginManager(app)
login.login_view = "login"
migrate = Migrate(app, db)

from app.alias import bp as alias_bp

app.register_blueprint(alias_bp, url_prefix="/alias")

from app.api import bp as api_bp

app.register_blueprint(api_bp, url_prefix="/api")

from app.db_import import bp as db_import_bp

app.register_blueprint(db_import_bp, url_prefix="/db_import")

from app import routes, models
