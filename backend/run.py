"""
Flask application entry point.

Runs the development server on localhost:5000.
In production, use a WSGI server like gunicorn instead.
"""
from app.dashboard import app

if __name__ == "__main__":
    # Run Flask development server
    # debug=True enables auto-reload on code changes
    app.run(host="127.0.0.1", port=5000, debug=True)
