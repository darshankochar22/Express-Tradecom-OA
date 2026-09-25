from flask import Blueprint, current_app, jsonify, request

from app.routes.decorators import jwt_required
from app.services import user_service
from app.services.validators import parse_positive_int

users_bp = Blueprint("users", __name__, url_prefix="/users")


@users_bp.get("")
@jwt_required
def list_users():
    search = request.args.get("search", "").strip() or None

    page = limit = None
    if "page" in request.args or "limit" in request.args:
        page = parse_positive_int(request.args.get("page"), "page", default=1)
        limit = parse_positive_int(
            request.args.get("limit"),
            "limit",
            default=current_app.config["DEFAULT_PAGE_LIMIT"],
            maximum=current_app.config["MAX_PAGE_LIMIT"],
        )

    users, pagination = user_service.list_users(search=search, page=page, limit=limit)

    body = {"success": True, "data": [u.to_dict() for u in users]}
    if pagination:
        body["pagination"] = pagination
    return jsonify(body), 200


@users_bp.post("")
def create_user():
    payload = request.get_json(silent=True)
    user = user_service.create_user(payload)
    return jsonify({"success": True, "data": user.to_dict()}), 201


@users_bp.get("/<int:user_id>")
@jwt_required
def get_user(user_id):
    user = user_service.get_user(user_id)
    return jsonify({"success": True, "data": user.to_dict()}), 200
