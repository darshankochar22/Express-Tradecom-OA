from flask import jsonify

from app.routes.users import users_bp


def register_routes(app):
    app.register_blueprint(users_bp)

    @app.get("/health")
    def health():
        return jsonify({"success": True, "status": "ok"}), 200
