from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APIClient

from store import payments, services
from store.models import Category, Order, Product


class PaymentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("ana", "ana@example.com", "pass12345")
        cat = Category.objects.create(name="Laptops", icon="laptop", group="computers")
        self.product = Product.objects.create(category=cat, name="Test Laptop", brand="ASUS",
                                              price=Decimal("1049.50"), stock=5)
        self.client.login(username="ana", password="pass12345")

    def checkout(self, method):
        services.add_to_cart(self.user, self.product, 2)
        return self.client.post("/checkout/", {"full_name": "Ana Sok", "phone": "012 345 678",
                                               "address": "St 1, Phnom Penh", "payment_method": method})

    def test_khqr_payload_has_amount_and_valid_crc(self):
        self.checkout("qr")
        order = Order.objects.get()
        payload = payments.khqr_payload(order)
        self.assertTrue(payload.startswith("000201010212"))
        self.assertIn("54072099.00", payload)          # tag 54, length 07, amount
        self.assertIn(order.number, payload)
        self.assertEqual(payload[-4:], payments._crc16(payload[:-4]))
        # Known CRC-16/CCITT-FALSE check value
        self.assertEqual(payments._crc16("123456789"), "29B1")

    def test_qr_checkout_pay_and_receipt(self):
        res = self.checkout("qr")
        order = Order.objects.get()
        self.assertRedirects(res, f"/orders/{order.pk}/pay/")
        page = self.client.get(f"/orders/{order.pk}/pay/")
        self.assertContains(page, "<svg")
        self.assertContains(page, "$2,099.00")
        res = self.client.post(f"/orders/{order.pk}/pay/")
        self.assertRedirects(res, f"/orders/{order.pk}/receipt/")
        order.refresh_from_db()
        self.assertTrue(order.is_paid)
        self.assertEqual(order.status, Order.Status.CONFIRMED)
        self.assertTrue(order.payment_ref.startswith("KHQR-"))
        receipt = self.client.get(f"/orders/{order.pk}/receipt/")
        self.assertContains(receipt, order.receipt_number)
        self.assertContains(receipt, order.payment_ref)
        # Paying twice is not possible: the pay page now sends you to the receipt.
        self.assertRedirects(self.client.get(f"/orders/{order.pk}/pay/"), f"/orders/{order.pk}/receipt/")

    def test_cancelling_paid_order_marks_refund(self):
        self.checkout("qr")
        order = payments.confirm_payment(Order.objects.get())
        services.change_order_status(order, Order.Status.CANCELLED)
        order.refresh_from_db()
        self.assertEqual(order.payment_status, Order.PaymentStatus.REFUNDED)

    def test_cash_on_delivery_is_paid_when_delivered(self):
        res = self.checkout("cod")
        order = Order.objects.get()
        self.assertRedirects(res, f"/orders/{order.pk}/")
        self.assertFalse(order.is_paid)
        services.change_order_status(order, Order.Status.DELIVERED)
        order.refresh_from_db()
        self.assertTrue(order.is_paid)

    def test_receipt_is_private(self):
        self.checkout("cod")
        order = Order.objects.get()
        User.objects.create_user("bob", "bob@example.com", "pass12345")
        self.client.login(username="bob", password="pass12345")
        self.assertEqual(self.client.get(f"/orders/{order.pk}/receipt/").status_code, 404)

    def test_api_payment_flow(self):
        api = APIClient()
        api.force_authenticate(self.user)
        services.add_to_cart(self.user, self.product, 1)
        res = api.post("/api/orders/", {"full_name": "Ana", "phone": "012345678", "address": "PP",
                                        "payment_method": "qr"}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        oid = res.data["id"]
        qr = api.get(f"/api/orders/{oid}/payment-qr/").data
        self.assertEqual(qr["amount"], "1049.50")
        self.assertIn("<svg", qr["svg"])
        paid = api.post(f"/api/orders/{oid}/confirm-payment/").data
        self.assertEqual(paid["payment_status"], "paid")
        self.assertEqual(api.get(f"/api/orders/{oid}/payment-qr/").status_code, 400)
        receipt = api.get(f"/api/orders/{oid}/receipt/").data
        self.assertEqual(receipt["receipt_number"], f"RC-{oid:05d}")
