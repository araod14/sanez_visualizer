"""Entrypoint: `uvicorn main:app`. La app real se ensambla en app.factory."""

from app.factory import create_app

app = create_app()
