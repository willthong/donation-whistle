from flask import Flask
from config import Config

from flask_caching import Cache
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

import fakeredis
import redis
import rq

cache = Cache()
db = SQLAlchemy()
login = LoginManager()
login.login_view = "main.login"
migrate = Migrate()


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    if app.config["TESTING"]:
        app.redis = fakeredis.FakeStrictRedis()
        app.task_queue = rq.Queue(is_async=False, connection=app.redis)
    else:
        app.redis = redis.Redis.from_url(app.config["REDIS_URL"])
        app.task_queue = rq.Queue("donation-whistle-tasks", connection=app.redis)

    cache.init_app(app)
    db.init_app(app)
    login.init_app(app)
    migrate.init_app(app, db)

    from app.alias import bp as alias_bp
    app.register_blueprint(alias_bp, url_prefix="/alias")

    from app.api import bp as api_bp
    app.register_blueprint(api_bp, url_prefix="/api")

    from app.db_import import bp as db_import_bp
    app.register_blueprint(db_import_bp, url_prefix="/db_import")

    from app.main import bp as main_bp
    app.register_blueprint(main_bp)

    return app


from app import models
