import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))


class Config(object):
    TESTING = False
    SECRET_KEY = os.environ.get("SECRET_KEY") or "a-very-secret-key"
    SQLALCHEMY_DATABASE_URI = (
        os.environ.get("DATABASE_URL") or 
        "sqlite:///" + os.path.join(basedir, "donation-whistle.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CACHE_TYPE = "FileSystemCache"
    CACHE_DIR = "./cache"
    RAW_DATA_LOCATION = "./"
    REDIS_URL = os.environ.get("REDIS_URL") or "redis://localhost:6379"
