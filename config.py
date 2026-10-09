"""
CareerBridge AI – configuration classes.
"""
import os
import logging
from dotenv import load_dotenv

load_dotenv()


def _configure_logging():
    """
    Production-safe logging: INFO level, no stack traces leaking secrets.
    Call once at application startup.
    """
    level = logging.DEBUG if os.environ.get("FLASK_ENV") == "development" else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    # Suppress SQLAlchemy query echo in production
    if os.environ.get("FLASK_ENV") != "development":
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


def _resolve_db_url() -> str:
    """
    Resolves the database URL from environment variables.

    Priority:
      1. DATABASE_URL            – explicit full URL (any platform)
      2. MYSQL_URL               – Railway MySQL plugin
      3. RDS_* variables         – AWS Elastic Beanstalk RDS env vars
      4. Local dev default

    Ensures the SQLAlchemy PyMySQL driver prefix is used.
    """
    url = os.environ.get("DATABASE_URL") or os.environ.get("MYSQL_URL")

    if not url:
        # AWS Elastic Beanstalk injects individual RDS_* vars
        rds_host     = os.environ.get("RDS_HOSTNAME")
        rds_port     = os.environ.get("RDS_PORT", "3306")
        rds_db       = os.environ.get("RDS_DB_NAME", "careerbridge")
        rds_user     = os.environ.get("RDS_USERNAME")
        rds_password = os.environ.get("RDS_PASSWORD")

        if rds_host and rds_user and rds_password:
            url = f"mysql+pymysql://{rds_user}:{rds_password}@{rds_host}:{rds_port}/{rds_db}"

    if not url:
        url = "mysql+pymysql://root:password@localhost:3306/careerbridge"

    # Normalise driver prefix: mysql:// → mysql+pymysql://
    if url.startswith("mysql://"):
        url = url.replace("mysql://", "mysql+pymysql://", 1)

    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = _resolve_db_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 5,
        "max_overflow": 10,
    }

    UPLOAD_FOLDER = os.environ.get("UPLOAD_FOLDER", "uploads")
    GENERATED_FOLDER = os.environ.get("GENERATED_FOLDER", "generated_resumes")
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_CONTENT_LENGTH", 5 * 1024 * 1024))
    ALLOWED_EXTENSIONS = {"pdf", "docx"}

    # ── Session / Cookie security ──────────────────────────────────────────────
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Secure flag is set to True only in production (requires HTTPS)
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV") == "production"
    PERMANENT_SESSION_LIFETIME = 86400 * 7   # 7 days

    LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "stub")
    LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
    LLM_MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
    LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", 1024))
    LLM_MONTHLY_COST_CAP = float(os.environ.get("LLM_MONTHLY_COST_CAP_USD", 20.0))

    MODEL_VERSION = os.environ.get("MODEL_VERSION", "v0.1-kb-baseline")
    KB_VERSION = os.environ.get("KB_VERSION", "v0.1")
    FEATURE_VERSION = os.environ.get("FEATURE_VERSION", "v0.1")

    MIN_CONFIRMED_SKILLS = 3  # abstention threshold
    ABSTENTION_THRESHOLD = 0.20

    SKILL_CONF_STRONG = 0.70
    SKILL_CONF_PARTIAL_LOW = 0.40

    # Confidence base values (Section 7)
    CONF_SKILLS_SECTION = 0.45
    CONF_PROJECT = 0.75
    CONF_EXPERIENCE = 0.85
    CONF_CERTIFICATION = 0.70
    CONF_ADDITIONAL_SOURCE = 0.10
    CONF_SELF_REPORTED = 0.60

    # Hybrid scoring weight (alpha = ML weight)
    HYBRID_ALPHA = 0.4  # will be tuned; starts KB-dominant


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}
