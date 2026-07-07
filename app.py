"""
app.py — application entry point
Run locally:  python app.py
Production:   gunicorn app:app
"""
from core.app_factory import create_app
from core.config import config

app = create_app()

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=config.DEBUG,
    )