"""
CareerBridge AI – Flask application factory.
"""
import os
from flask import Flask, jsonify
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from database.models import db, login_manager
from config import config_map, _configure_logging


def create_app(config_name: str = None) -> Flask:
    config_name = config_name or os.environ.get("FLASK_ENV", "development")

    # Configure logging before anything else
    _configure_logging()

    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config_map.get(config_name, config_map["default"]))

    if config_name == "production":
        has_database_url = bool(
            os.environ.get("DATABASE_URL") or os.environ.get("MYSQL_URL")
        )
        has_rds_config = all(
            os.environ.get(key)
            for key in ("RDS_HOSTNAME", "RDS_USERNAME", "RDS_PASSWORD")
        )
        missing = []
        if not os.environ.get("SECRET_KEY"):
            missing.append("SECRET_KEY")
        if not has_database_url and not has_rds_config:
            missing.append("DATABASE_URL or MYSQL_URL")
        if missing:
            raise RuntimeError(
                "Missing required production environment variables: "
                + ", ".join(missing)
            )

    # Trust one level of reverse-proxy headers (Railway / AWS ALB / nginx).
    # Required so SESSION_COOKIE_SECURE and url_for(..., _external=True) work
    # correctly behind HTTPS load-balancers.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # Ensure private folders exist
    for folder_key in ("UPLOAD_FOLDER", "GENERATED_FOLDER"):
        os.makedirs(app.config[folder_key], exist_ok=True)

    # Extensions
    db.init_app(app)
    login_manager.init_app(app)
    CORS(app, supports_credentials=True)

    # Rate limiter (optional, graceful if redis absent)
    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address
        limiter = Limiter(get_remote_address, app=app, default_limits=["200 per day", "50 per hour"])
        app.extensions["limiter"] = limiter
    except Exception:
        pass

    # Register CLI commands
    from database.seed import register_commands
    register_commands(app)

    # Blueprints
    from api.auth import auth_bp
    from api.resume import resume_bp
    from api.careers import careers_bp
    from api.skills import skills_bp
    from api.roadmap import roadmap_bp
    from api.chat import chat_bp
    from api.profile import profile_bp
    from api.resume_builder import builder_bp
    from api.feedback import feedback_bp

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(resume_bp, url_prefix="/api/resume")
    app.register_blueprint(careers_bp, url_prefix="/api/careers")
    app.register_blueprint(skills_bp, url_prefix="/api/skills")
    app.register_blueprint(roadmap_bp, url_prefix="/api/roadmap")
    app.register_blueprint(chat_bp, url_prefix="/api/chat")
    app.register_blueprint(profile_bp, url_prefix="/api/profile")
    app.register_blueprint(builder_bp, url_prefix="/api/resume-builder")
    app.register_blueprint(feedback_bp, url_prefix="/api/feedback")

    # Health
    @app.route("/api/health")
    def health():
        return jsonify({"status": "ok", "version": app.config["MODEL_VERSION"]})

    # Serve frontend SPA for non-api routes
    @app.route("/", defaults={"path": ""})
    @app.route("/<path:path>")
    def serve_frontend(path):
        from flask import send_from_directory, render_template
        # Try static file first, else serve index.html
        static_path = os.path.join(app.static_folder, path)
        if path and os.path.exists(static_path):
            return send_from_directory(app.static_folder, path)
        return render_template("index.html")

    # Global error handlers
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"status": "error", "error": {"code": "NOT_FOUND", "message": str(e)}}), 404

    @app.errorhandler(413)
    def too_large(e):
        return jsonify({"status": "error", "error": {"code": "FILE_TOO_LARGE", "message": "File exceeds 5 MB limit"}}), 413

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"status": "error", "error": {"code": "SERVER_ERROR", "message": "Internal server error"}}), 500

    return app
