"""
WSGI config for config project.

It exposes the WSGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/6.1/howto/deployment/wsgi/
"""

import os

from django.core.wsgi import get_wsgi_application

import shutil
from pathlib import Path

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

if os.environ.get("VERCEL") and not (os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL")):
    # Vercel only lets us write to /tmp: start each server instance from the bundled demo database.
    # Orders and new accounts made on the live site last until that instance is recycled.
    demo_db = Path(__file__).resolve().parent.parent / "deploy" / "demo.sqlite3"
    live_db = Path("/tmp/techcart.sqlite3")
    if not live_db.exists() and demo_db.exists():
        shutil.copyfile(demo_db, live_db)

application = get_wsgi_application()

if os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL"):
    # Hosted PostgreSQL: create the tables and load the demo data the first time.
    from config.bootstrap import prepare_database

    prepare_database()

app = application  # Vercel's Python runtime looks for "app"
