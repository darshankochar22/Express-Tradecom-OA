from flask import Blueprint, g, jsonify, request

from app.routes.decorators import jwt_required
from app.services import auth_service

auth_bp = Blueprint("auth", __name__, url_prefix="/auth")


@auth_bp.post("/login")
def login():
    tokens = auth_service.login(request.get_json(silent=True))
    return jsonify({"success": True, "data": tokens}), 200


@auth_bp.get("/me")
@jwt_required
def me():
    return jsonify({"success": True, "data": g.current_user.to_dict()}), 200


@auth_bp.post("/forgot-password")
def forgot_password():
    result = auth_service.forgot_password(request.get_json(silent=True))
    return jsonify({"success": True, "data": result}), 200


@auth_bp.post("/reset-password")
def reset_password():
    auth_service.reset_password(request.get_json(silent=True))
    return jsonify({"success": True, "message": "Password has been reset. Please log in again."}), 200
