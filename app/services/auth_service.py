from datetime import datetime, timedelta, timezone

import jwt
from flask import current_app
from sqlalchemy import select
from werkzeug.security import check_password_hash, generate_password_hash

from app.errors import TooManyRequestsError, UnauthorizedError, ValidationError
from app.extensions import db
from app.models import User
from app.services.validators import (
    validate_forgot_password_payload,
    validate_login_payload,
    validate_reset_password_payload,
)

ACCESS_TOKEN = "access"
RESET_TOKEN = "reset"
ALGORITHM = "HS256"

_DUMMY_HASH = generate_password_hash("dummy-password-for-timing")


def _utcnow():
    return datetime.now(timezone.utc)


def _find_by_email(email):
    return db.session.scalar(select(User).where(User.email == email))


def _issue_token(user, token_type, minutes):
    now = _utcnow()
    payload = {
        "sub": str(user.id),
        "type": token_type,
        "ver": user.token_version,
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm=ALGORITHM)


def _user_from_token(token, expected_type):
    try:
        payload = jwt.decode(
            token,
            current_app.config["JWT_SECRET_KEY"],
            algorithms=[ALGORITHM],
            options={"require": ["sub", "exp", "iat"]},
        )
    except jwt.ExpiredSignatureError:
        raise UnauthorizedError("Token has expired")
    except jwt.InvalidTokenError:
        raise UnauthorizedError("Invalid token")

    if payload.get("type") != expected_type:
        raise UnauthorizedError("Invalid token")

    try:
        user = db.session.get(User, int(payload["sub"]))
    except (TypeError, ValueError):
        raise UnauthorizedError("Invalid token")

    if user is None or payload.get("ver") != user.token_version:
        raise UnauthorizedError("Token is no longer valid")
    return user


def login(payload):
    data = validate_login_payload(payload)
    user = _find_by_email(data["email"])

    if user is None:
        check_password_hash(_DUMMY_HASH, data["password"])
        raise UnauthorizedError("Invalid email or password")
    if not user.check_password(data["password"]):
        raise UnauthorizedError("Invalid email or password")

    minutes = current_app.config["ACCESS_TOKEN_EXPIRES_MINUTES"]
    return {
        "access_token": _issue_token(user, ACCESS_TOKEN, minutes),
        "token_type": "Bearer",
        "expires_in": minutes * 60,
    }


def user_from_access_token(token):
    return _user_from_token(token, ACCESS_TOKEN)


def forgot_password(payload):
    data = validate_forgot_password_payload(payload)
    mismatch = ValidationError("Email and date of birth do not match")

    user = _find_by_email(data["email"])
    if user is None:
        raise mismatch

    now = _utcnow().replace(tzinfo=None)
    if user.reset_locked_until and user.reset_locked_until > now:
        raise TooManyRequestsError("Too many failed attempts. Try again later.")

    if user.date_of_birth != data["date_of_birth"]:
        user.reset_attempts += 1
        if user.reset_attempts >= current_app.config["RESET_MAX_ATTEMPTS"]:
            user.reset_locked_until = now + timedelta(minutes=current_app.config["RESET_LOCKOUT_MINUTES"])
            user.reset_attempts = 0
        db.session.commit()
        raise mismatch

    user.reset_attempts = 0
    user.reset_locked_until = None
    db.session.commit()

    minutes = current_app.config["RESET_TOKEN_EXPIRES_MINUTES"]
    return {"reset_token": _issue_token(user, RESET_TOKEN, minutes), "expires_in": minutes * 60}


def reset_password(payload):
    data = validate_reset_password_payload(payload)
    user = _user_from_token(data["reset_token"], RESET_TOKEN)

    user.set_password(data["new_password"])
    user.token_version += 1
    db.session.commit()
