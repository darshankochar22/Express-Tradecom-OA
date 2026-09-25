from functools import wraps

from flask import g, request

from app.errors import UnauthorizedError
from app.services import auth_service


def jwt_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        scheme, _, token = request.headers.get("Authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token.strip():
            raise UnauthorizedError("Missing or invalid Authorization header")
        g.current_user = auth_service.user_from_access_token(token.strip())
        return view(*args, **kwargs)

    return wrapper
