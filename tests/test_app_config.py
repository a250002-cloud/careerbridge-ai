import pytest

from app import create_app


def test_production_requires_secret_and_database(monkeypatch):
    for key in (
        "SECRET_KEY",
        "DATABASE_URL",
        "MYSQL_URL",
        "RDS_HOSTNAME",
        "RDS_USERNAME",
        "RDS_PASSWORD",
    ):
        monkeypatch.delenv(key, raising=False)

    with pytest.raises(RuntimeError, match="SECRET_KEY, DATABASE_URL or MYSQL_URL"):
        create_app("production")
