import re
from datetime import date

from app.errors import ValidationError

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

USER_FIELDS = {"name": 100, "email": 255, "role": 50}
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128
MIN_DATE_OF_BIRTH = date(1900, 1, 1)


def _require_object(payload):
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object")


def _raise_if_errors(errors):
    if errors:
        raise ValidationError("Validation failed", details=errors)


def _string(payload, field, max_len, errors):
    value = payload.get(field)
    if value is None or (isinstance(value, str) and not value.strip()):
        errors[field] = f"{field} is required"
        return None
    if not isinstance(value, str):
        errors[field] = f"{field} must be a string"
        return None
    value = value.strip()
    if len(value) > max_len:
        errors[field] = f"{field} must be at most {max_len} characters"
        return None
    return value


def _email(payload, errors, field="email"):
    value = _string(payload, field, USER_FIELDS["email"], errors)
    if value is None:
        return None
    value = value.lower()
    if not EMAIL_RE.match(value):
        errors[field] = "Invalid email format"
        return None
    return value


def _password(payload, field, errors):
    value = payload.get(field)
    if value is None or value == "":
        errors[field] = f"{field} is required"
        return None
    if not isinstance(value, str):
        errors[field] = f"{field} must be a string"
        return None
    if len(value) < PASSWORD_MIN_LENGTH:
        errors[field] = f"{field} must be at least {PASSWORD_MIN_LENGTH} characters"
        return None
    if len(value) > PASSWORD_MAX_LENGTH:
        errors[field] = f"{field} must be at most {PASSWORD_MAX_LENGTH} characters"
        return None
    return value


def _date_of_birth(payload, errors, field="date_of_birth"):
    value = payload.get(field)
    if value is None or (isinstance(value, str) and not value.strip()):
        errors[field] = f"{field} is required"
        return None
    if not isinstance(value, str) or not DATE_RE.match(value.strip()):
        errors[field] = f"{field} must be a date in YYYY-MM-DD format"
        return None
    try:
        parsed = date.fromisoformat(value.strip())
    except ValueError:
        errors[field] = f"{field} is not a valid date"
        return None
    if parsed > date.today():
        errors[field] = f"{field} cannot be in the future"
        return None
    if parsed < MIN_DATE_OF_BIRTH:
        errors[field] = f"{field} must be on or after {MIN_DATE_OF_BIRTH.isoformat()}"
        return None
    return parsed


def validate_user_payload(payload):
    _require_object(payload)
    errors = {}
    clean = {
        "name": _string(payload, "name", USER_FIELDS["name"], errors),
        "email": _email(payload, errors),
        "role": _string(payload, "role", USER_FIELDS["role"], errors),
        "password": _password(payload, "password", errors),
        "date_of_birth": _date_of_birth(payload, errors),
    }
    _raise_if_errors(errors)
    return clean


def validate_login_payload(payload):
    _require_object(payload)
    errors = {}
    email = _string(payload, "email", USER_FIELDS["email"], errors)
    password = payload.get("password")
    if not isinstance(password, str) or password == "":
        errors["password"] = "password is required"
    _raise_if_errors(errors)
    return {"email": email.lower(), "password": password}


def validate_forgot_password_payload(payload):
    _require_object(payload)
    errors = {}
    clean = {"email": _email(payload, errors), "date_of_birth": _date_of_birth(payload, errors)}
    _raise_if_errors(errors)
    return clean


def validate_reset_password_payload(payload):
    _require_object(payload)
    errors = {}
    clean = {
        "reset_token": _string(payload, "reset_token", 2048, errors),
        "new_password": _password(payload, "new_password", errors),
    }
    _raise_if_errors(errors)
    return clean


def parse_positive_int(raw, name, default, maximum=None):
    if raw is None or raw == "":
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        raise ValidationError(f"{name} must be a positive integer")
    if value < 1:
        raise ValidationError(f"{name} must be a positive integer")
    if maximum is not None and value > maximum:
        raise ValidationError(f"{name} must not exceed {maximum}")
    return value
