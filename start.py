#!/usr/bin/env python3
"""
start.py – Railway production startup script.
Initializes and seeds the database, then hands off to gunicorn.
"""
import os
import sys
import subprocess


def run(cmd: list[str]):
    print(f">> {' '.join(cmd)}", flush=True)
    result = subprocess.run(cmd, capture_output=False)
    if result.returncode != 0:
        print(f"ERROR: command failed with code {result.returncode}", flush=True)
        sys.exit(result.returncode)


if __name__ == "__main__":
    os.environ["FLASK_APP"] = "app.py"
    os.environ["FLASK_ENV"] = "production"
    python = sys.executable

    # 1. Create all tables & seed KB data
    run([python, "-m", "flask", "seed-db"])

    # 2. Hand off to gunicorn
    port = os.environ.get("PORT", "5000")
    # Keep the default small for Railway's memory-limited instances. Increase
    # WEB_CONCURRENCY only after checking the service's memory under load.
    workers = os.environ.get("WEB_CONCURRENCY", "1")
    run([
        python, "-m", "gunicorn",
        "app:create_app('production')",
        "--bind", f"0.0.0.0:{port}",
        "--workers", workers,
        "--timeout", "120",
    ])
