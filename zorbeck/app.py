# Zorbeck — entry point for Railway (`uvicorn app:app`). The service lives in
# zorbeck_app/ (routes in zorbeck_app/main.py); this shim keeps the deployed
# start command unchanged.
from zorbeck_app.main import app

__all__ = ["app"]
