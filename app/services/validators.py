import re

from app.errors import ValidationError

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

USER_FIELDS = {"name": 100, "email": 255, "role": 50}


def validate_user_payload(payload):
    if not isinstance(payload, dict):
        raise ValidationError("Request body must be a JSON object")

    errors = {}
    clean = {}

    for field, max_len in USER_FIELDS.items():
        value = payload.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            errors[field] = f"{field} is required"
            continue
        if not isinstance(value, str):
            errors[field] = f"{field} must be a string"
            continue
        value = value.strip()
        if len(value) > max_len:
            errors[field] = f"{field} must be at most {max_len} characters"
            continue
        clean[field] = value

    if "email" in clean:
        clean["email"] = clean["email"].lower()
        if not EMAIL_RE.match(clean["email"]):
            errors["email"] = "Invalid email format"

    if errors:
        raise ValidationError("Validation failed", details=errors)

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
