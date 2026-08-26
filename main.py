"""
Nexura Phase 7 — WSGI Entry Point
Usage:
  flask run           (development)
  gunicorn main:app   (production)
"""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run()
