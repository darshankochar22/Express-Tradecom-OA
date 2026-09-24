from flask import jsonify

from app.routes.auth import auth_bp
from app.routes.docs import docs_bp
from app.routes.users import users_bp


def register_routes(app):
    app.register_blueprint(users_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(docs_bp)

    @app.get("/health")
    def health():
        return jsonify({"success": True, "status": "ok"}), 200
