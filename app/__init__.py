from flask import Flask

from app.config import Config
from app.errors import register_error_handlers
from app.extensions import db
from app.routes import register_routes


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    app.json.sort_keys = False

    if not app.config.get("JWT_SECRET_KEY"):
        raise RuntimeError("JWT_SECRET_KEY environment variable is not set")

    db.init_app(app)
    register_routes(app)
    register_error_handlers(app)

    return app
