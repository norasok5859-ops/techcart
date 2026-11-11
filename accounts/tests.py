import io
import tempfile
from pathlib import Path

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.demo import DEMO_ACCOUNTS
from store.models import Product


class LoginTests(TestCase):
    def setUp(self):
        User.objects.create_user("alice", "alice@example.com", "pass12345")

    def test_login_with_username_or_email(self):
        for name in ("alice", "ALICE", "alice@example.com", "Alice@Example.com"):
            self.assertTrue(self.client.login(username=name, password="pass12345"), name)
            self.client.logout()
        self.assertFalse(self.client.login(username="alice@example.com", password="wrong"))

    def test_api_login_accepts_email(self):
        res = APIClient().post("/api/auth/login/", {"username": "alice@example.com", "password": "pass12345"})
        self.assertEqual(res.status_code, 200)
        self.assertIn("token", res.data)


class DemoAccountTests(TestCase):
    def test_seed_creates_working_demo_accounts_and_images(self):
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            call_command("seed", no_photos=True, stdout=io.StringIO())
            self.assertEqual(len(list(Path(media, "products").glob("art-*.svg"))), Product.objects.count())
        for acc in DEMO_ACCOUNTS:
            self.assertTrue(self.client.login(username=acc["username"], password=acc["password"]), acc["username"])
            self.client.logout()
        self.assertTrue(User.objects.get(username="admin").is_staff)
        self.assertFalse(Product.objects.filter(image="").exists())

    def test_login_page_lists_demo_accounts(self):
        res = self.client.get("/accounts/login/")
        self.assertContains(res, "js-demo-login")
        self.assertEqual(len(APIClient().get("/api/auth/demo-accounts/").data), len(DEMO_ACCOUNTS))
