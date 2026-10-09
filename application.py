"""
application.py – AWS Elastic Beanstalk entry point.

EB looks for a callable named `application` in this file.
"""
from app import create_app

application = create_app("production")

if __name__ == "__main__":
    application.run()
