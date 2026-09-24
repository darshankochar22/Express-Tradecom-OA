from flask import jsonify
from werkzeug.exceptions import HTTPException


class APIError(Exception):
    status_code = 400

    def __init__(self, message, status_code=None, details=None):
        super().__init__(message)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.details = details


class ValidationError(APIError):
    status_code = 400


class NotFoundError(APIError):
    status_code = 404


class ConflictError(APIError):
    status_code = 409


def error_response(message, status_code, details=None):
    body = {"success": False, "error": message}
    if details:
        body["details"] = details
    return jsonify(body), status_code


def register_error_handlers(app):
    @app.errorhandler(APIError)
    def handle_api_error(err):
        return error_response(err.message, err.status_code, err.details)

    @app.errorhandler(HTTPException)
    def handle_http_error(err):
        return error_response(err.description or err.name, err.code)

    @app.errorhandler(Exception)
    def handle_unexpected(err):
        app.logger.exception("Unhandled error")
        return error_response("Internal server error", 500)
