"""Fixed demo accounts.

`python manage.py seed` creates these users (and resets their passwords), and the login
page lists them so anyone trying the site can sign in with one click.
Turn the list off on the login page with TECHCART_SHOW_DEMO_ACCOUNTS=0.
"""

DEMO_ACCOUNTS = [
    {"username": "admin", "password": "admin12345", "email": "admin@techcart.local",
     "first_name": "Store", "last_name": "Admin", "is_staff": True,
     "role": "Admin", "note": "Dashboard, products, stock and orders"},
    {"username": "demo", "password": "demo12345", "email": "demo@techcart.local",
     "first_name": "Demo", "last_name": "Customer", "is_staff": False,
     "role": "Customer", "note": "Shop, cart, checkout and order history"},
    {"username": "sophia", "password": "sophia12345", "email": "sophia@techcart.local",
     "first_name": "Sophia", "last_name": "Chan", "is_staff": False,
     "role": "Customer", "note": "A second shopper with her own cart"},
    {"username": "david", "password": "david12345", "email": "david@techcart.local",
     "first_name": "David", "last_name": "Kim", "is_staff": False,
     "role": "Customer", "note": "A third shopper with his own cart"},
]


def public_demo_accounts():
    """What the login page and API show: no internal flags."""
    return [{k: a[k] for k in ("username", "password", "email", "first_name", "role", "note")}
            for a in DEMO_ACCOUNTS]
