from flask import Blueprint, url_for

docs_bp = Blueprint("docs", __name__)

SWAGGER_UI_VERSION = "5.17.14"

SWAGGER_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="color-scheme" content="light">
  <title>User Management API - Docs</title>
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@{version}/swagger-ui.css">
  <style>html, body {{ margin: 0; background: #fff; }}</style>
</head>
<body>
  <div id="swagger-ui"></div>
  <script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@{version}/swagger-ui-bundle.js"></script>
  <script>
    window.ui = SwaggerUIBundle({{
      url: "{spec_url}",
      dom_id: "#swagger-ui",
      tryItOutEnabled: true,
      persistAuthorization: true
    }});
  </script>
</body>
</html>"""


@docs_bp.get("/docs")
def swagger_ui():
    spec_url = url_for("static", filename="openapi.yaml")
    return SWAGGER_HTML.format(version=SWAGGER_UI_VERSION, spec_url=spec_url)
