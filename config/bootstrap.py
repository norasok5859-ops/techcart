"""Get a hosted PostgreSQL database ready when a server instance starts (used by config/wsgi.py).

Applies migrations, and the very first time (no products yet) copies in the bundled demo data from
deploy/demo.sqlite3: the 69 products, categories and the demo accounts. A PostgreSQL advisory lock
makes sure two instances starting at the same moment don't both do it.
"""

import logging
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.db import connections, transaction

log = logging.getLogger(__name__)

DEMO_DB = Path(settings.BASE_DIR) / "deploy" / "demo.sqlite3"
LOCK_ID = 727_001  # any fixed number; only this app uses it

# Tables that Django fills in by itself, or that should start empty on the live site.
EXCLUDE = ["contenttypes", "auth.permission", "admin.logentry", "sessions"]


def prepare_database():
    default = connections["default"]
    if default.vendor != "postgresql":
        return
    # One transaction holding a transaction-level lock: safe behind Neon's connection pooler, and the
    # lock is released automatically even if something fails.
    with transaction.atomic():
        with default.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", [LOCK_ID])
        call_command("migrate", interactive=False, verbosity=0)
        from store.models import Product

        if not Product.objects.exists():
            load_demo_data()


def load_demo_data():
    if "demo" not in settings.DATABASES or not DEMO_DB.exists():
        log.warning("No demo database to copy; the store starts empty.")
        return
    shutil.copyfile(DEMO_DB, settings.DATABASES["demo"]["NAME"])
    call_command("migrate", database="demo", interactive=False, verbosity=0)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        dump = f.name
    call_command("dumpdata", database="demo", exclude=EXCLUDE, natural_foreign=True,
                 output=dump, verbosity=0)
    call_command("loaddata", dump, verbosity=0)  # also resets the id sequences
    Path(dump).unlink(missing_ok=True)
    log.warning("Loaded the demo data into the hosted database.")
