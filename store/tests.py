from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient

from .models import CartItem, Category, Order, Product


class TechCartTests(TestCase):
    def setUp(self):
        self.cat = Category.objects.create(name="Mice", icon="mouse")
        self.mouse = Product.objects.create(category=self.cat, name="Test Mouse", price=Decimal("20.00"), stock=5)
        self.hidden = Product.objects.create(category=self.cat, name="Old Mouse", price=Decimal("5.00"),
                                             stock=5, is_active=False)
        self.user = User.objects.create_user("alice", "a@example.com", "pass12345")
        self.admin = User.objects.create_user("boss", "b@example.com", "pass12345", is_staff=True)
        self.api = APIClient()

    # ---------- catalogue API ----------
    def test_public_can_list_only_active_products(self):
        res = self.api.get("/api/products/")
        self.assertEqual(res.status_code, 200)
        names = [p["name"] for p in res.data["results"]]
        self.assertEqual(names, ["Test Mouse"])

    def test_search_and_filter(self):
        self.assertEqual(self.api.get("/api/products/?search=test").data["count"], 1)
        self.assertEqual(self.api.get("/api/products/?search=keyboard").data["count"], 0)
        self.assertEqual(self.api.get("/api/products/?category=mice&max_price=10").data["count"], 0)

    def test_customer_cannot_create_product(self):
        self.api.force_authenticate(self.user)
        res = self.api.post("/api/products/", {"name": "X", "price": "1.00", "category": self.cat.id})
        self.assertEqual(res.status_code, 403)

    def test_admin_can_create_product_and_set_stock(self):
        self.api.force_authenticate(self.admin)
        res = self.api.post("/api/products/", {"name": "New Mouse", "price": "9.99",
                                               "category": self.cat.id, "stock": 3})
        self.assertEqual(res.status_code, 201)
        res = self.api.patch(f"/api/products/{res.data['slug']}/stock/", {"stock": 40}, format="json")
        self.assertEqual(res.data["stock"], 40)

    # ---------- auth API ----------
    def test_register_and_login_return_token(self):
        res = self.api.post("/api/auth/register/", {"username": "bob", "email": "bob@x.com",
                                                    "password": "secret123"})
        self.assertEqual(res.status_code, 201)
        self.assertIn("token", res.data)
        res = self.api.post("/api/auth/login/", {"username": "bob", "password": "secret123"})
        self.assertEqual(res.status_code, 200)
        self.api.credentials(HTTP_AUTHORIZATION="Token " + res.data["token"])
        self.assertEqual(self.api.get("/api/auth/me/").data["username"], "bob")

    # ---------- cart + checkout ----------
    def test_cart_requires_login(self):
        self.assertEqual(self.api.get("/api/cart/").status_code, 401)

    def test_cart_stock_limit(self):
        self.api.force_authenticate(self.user)
        self.assertEqual(self.api.post("/api/cart/", {"product_id": self.mouse.id, "quantity": 3}).status_code, 201)
        res = self.api.post("/api/cart/", {"product_id": self.mouse.id, "quantity": 3})
        self.assertEqual(res.status_code, 400)
        self.assertIn("left in stock", res.data["detail"])

    def test_checkout_creates_order_and_reduces_stock(self):
        self.api.force_authenticate(self.user)
        self.api.post("/api/cart/", {"product_id": self.mouse.id, "quantity": 2})
        res = self.api.post("/api/orders/", {"full_name": "Alice", "phone": "012345678", "address": "Phnom Penh"})
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["total"], "40.00")
        self.assertEqual(res.data["payment_method"], "cod")
        self.mouse.refresh_from_db()
        self.assertEqual(self.mouse.stock, 3)
        self.assertFalse(CartItem.objects.filter(user=self.user).exists())

    def test_cancel_returns_stock_and_admin_updates_status(self):
        self.api.force_authenticate(self.user)
        self.api.post("/api/cart/", {"product_id": self.mouse.id, "quantity": 2})
        order_id = self.api.post("/api/orders/", {"full_name": "A", "phone": "012345678",
                                                  "address": "PP"}).data["id"]
        # customer can't change status
        self.assertEqual(self.api.patch(f"/api/orders/{order_id}/status/", {"status": "shipped"}).status_code, 403)
        self.api.force_authenticate(self.admin)
        self.assertEqual(self.api.patch(f"/api/orders/{order_id}/status/", {"status": "cancelled"}).data["status"],
                         "cancelled")
        self.mouse.refresh_from_db()
        self.assertEqual(self.mouse.stock, 5)

    def test_customers_only_see_their_own_orders(self):
        other = User.objects.create_user("eve", "e@x.com", "pass12345")
        Order.objects.create(user=other, full_name="Eve", phone="1", address="x")
        self.api.force_authenticate(self.user)
        self.assertEqual(self.api.get("/api/orders/").data["count"], 0)
        self.api.force_authenticate(self.admin)
        self.assertEqual(self.api.get("/api/orders/").data["count"], 1)

    # ---------- web pages ----------
    def test_pages_render(self):
        for url in [reverse("store:home"), reverse("store:product_list"),
                    reverse("store:product_detail", args=[self.mouse.slug])]:
            self.assertEqual(self.client.get(url).status_code, 200, url)

    def test_web_checkout_flow(self):
        self.client.login(username="alice", password="pass12345")
        CartItem.objects.create(user=self.user, product=self.mouse, quantity=1)
        res = self.client.post(reverse("store:checkout"),
                               {"full_name": "Alice", "phone": "012 345 678", "address": "Street 1"})
        order = Order.objects.get(user=self.user)
        self.assertRedirects(res, reverse("store:order_detail", args=[order.pk]))

    def test_dashboard_is_staff_only(self):
        self.client.login(username="alice", password="pass12345")
        self.assertEqual(self.client.get(reverse("dashboard:overview")).status_code, 302)
        self.client.login(username="boss", password="pass12345")
        self.assertEqual(self.client.get(reverse("dashboard:overview")).status_code, 200)
