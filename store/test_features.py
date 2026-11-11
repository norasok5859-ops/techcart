import io
import tempfile
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone
from PIL import Image

from store import services
from store.models import ActivityLog, CartItem, DiscountCode, Order, Product, ProductImage, StoredFile

DB_STORAGE = {"default": {"BACKEND": "store.storage.DatabaseStorage"},
              "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}}


def img(name, color=(200, 30, 30)):
    out = io.BytesIO()
    Image.new("RGB", (800, 800), color).save(out, "JPEG")
    return SimpleUploadedFile(name, out.getvalue(), content_type="image/jpeg")


class FeatureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            call_command("seed", no_photos=True, stdout=io.StringIO())
        cls.owner = User.objects.get(username="admin")
        cls.customer = User.objects.get(username="demo")
        cls.cpu = Product.objects.get(name="AMD Ryzen 5 7600")  # $219.00

    def fill_cart(self, qty=2):
        CartItem.objects.filter(user=self.customer).delete()
        CartItem.objects.create(user=self.customer, product=self.cpu, quantity=qty)

    def order(self, code=""):
        return services.place_order(self.customer, "Demo", "012345678", "Phnom Penh", discount_code=code)

    # --- discount codes ---

    def test_percent_and_fixed_codes(self):
        price = self.cpu.price
        DiscountCode.objects.create(code="save10", kind="percent", value=10)
        DiscountCode.objects.create(code="LESS50", kind="fixed", value=50, once_per_customer=False)
        self.fill_cart(2)
        o = self.order("Save10")
        self.assertEqual(o.discount_code, "SAVE10")
        self.assertEqual(o.discount_amount, (price * 2 * Decimal("0.1")).quantize(Decimal("0.01")))
        self.assertEqual(o.total, price * 2 - o.discount_amount)
        self.assertEqual(o.subtotal, price * 2)
        self.assertEqual(DiscountCode.objects.get(code="SAVE10").used_count, 1)
        self.fill_cart(1)
        self.assertEqual(self.order("less50").total, price - 50)

    def test_code_rules(self):
        now = timezone.now()
        DiscountCode.objects.create(code="ONCE", kind="percent", value=5)
        DiscountCode.objects.create(code="BIG", kind="fixed", value=20, min_order=5000)
        DiscountCode.objects.create(code="OLD", kind="percent", value=5, ends_at=now - timedelta(days=1))
        DiscountCode.objects.create(code="SOON", kind="percent", value=5, starts_at=now + timedelta(days=1))
        DiscountCode.objects.create(code="ONE", kind="percent", value=5, max_uses=1, used_count=1)
        DiscountCode.objects.create(code="OFF", kind="percent", value=5, is_active=False)
        for code, msg in [("NOPE", "not a valid"), ("BIG", "at least"), ("OLD", "expired"), ("SOON", "from"),
                          ("ONE", "expired"), ("OFF", "not available")]:
            with self.assertRaisesRegex(services.CartError, msg):
                services.check_discount(code, self.customer, Decimal("300"))
        self.fill_cart(1)
        o = self.order("ONCE")
        with self.assertRaisesRegex(services.CartError, "already used"):
            services.check_discount("ONCE", self.customer, Decimal("300"))
        services.change_order_status(o, Order.Status.CANCELLED)  # gives the use back
        self.assertEqual(DiscountCode.objects.get(code="ONCE").used_count, 0)
        services.check_discount("ONCE", self.customer, Decimal("300"))

    def test_fixed_discount_never_exceeds_order(self):
        DiscountCode.objects.create(code="HUGE", kind="fixed", value=10000)
        self.fill_cart(1)
        self.assertEqual(self.order("HUGE").total, Decimal("0.00"))

    def test_checkout_page_apply_and_place(self):
        DiscountCode.objects.create(code="WEB15", kind="percent", value=15)
        self.fill_cart(1)
        self.client.force_login(self.customer)
        res = self.client.post("/checkout/", {"apply_code": "1", "discount_code": "web15", "phone": "099 888 777"})
        self.assertContains(res, "WEB15")
        self.assertContains(res, "099 888 777")  # typed details are kept
        self.assertNotContains(res, "is-invalid")
        self.client.post("/checkout/", {"remove_code": "1"})
        res = self.client.post("/checkout/", {"apply_code": "1", "discount_code": "BOGUS"})
        self.assertContains(res, "not a valid discount code")
        self.client.post("/checkout/", {"apply_code": "1", "discount_code": "WEB15"})
        self.client.post("/checkout/", {"full_name": "Demo", "phone": "012345678", "address": "PP",
                                        "payment_method": "cod"})
        o = Order.objects.filter(user=self.customer).first()
        self.assertEqual(o.discount_code, "WEB15")
        self.assertContains(self.client.get(f"/orders/{o.pk}/"), "WEB15")
        self.assertContains(self.client.get(f"/orders/{o.pk}/receipt/"), "Discount (WEB15)")

    def test_dashboard_discount_crud(self):
        self.client.force_login(self.owner)
        res = self.client.post("/dashboard/discounts/new/", {"code": "nov-20", "kind": "percent", "value": "20",
                                                             "min_order": "0", "is_active": "on"})
        self.assertRedirects(res, "/dashboard/discounts/")
        d = DiscountCode.objects.get(code="NOV-20")
        res = self.client.post("/dashboard/discounts/new/", {"code": "BAD", "kind": "percent", "value": "150",
                                                             "min_order": "0"})
        self.assertIn("value", res.context["form"].errors)
        self.assertContains(self.client.get("/dashboard/discounts/"), "NOV-20")
        self.client.post(f"/dashboard/discounts/{d.pk}/delete/")
        self.assertFalse(DiscountCode.objects.filter(pk=d.pk).exists())

    # --- photos ---

    @override_settings(STORAGES=DB_STORAGE)
    def test_gallery_upload_swap_delete(self):
        self.client.force_login(self.owner)
        page = self.client.get(f"/dashboard/products/{self.cpu.pk}/edit/")
        data = {k: v for k, v in page.context["form"].initial.items() if v is not None and k != "image"}
        data.update(category=self.cpu.category_id, is_active="on",
                    extra_photos=[img("a.jpg"), img("b.jpg", (30, 30, 200))])
        self.client.post(f"/dashboard/products/{self.cpu.pk}/edit/", data)
        photos = list(self.cpu.photos.all())
        self.assertEqual(len(photos), 2)
        self.assertTrue(StoredFile.objects.filter(name=photos[0].image.name).exists())
        detail = self.client.get(self.cpu.get_absolute_url())
        self.assertContains(detail, "tc-gallery-thumb", count=3 + 3)  # 3 buttons (+ class used in script)
        old_main = Product.objects.get(pk=self.cpu.pk).image.name
        self.client.post(f"/dashboard/products/{self.cpu.pk}/photos/{photos[0].pk}/make-main/")
        self.cpu.refresh_from_db()
        self.assertEqual(self.cpu.image.name, photos[0].image.name)
        self.assertTrue(ProductImage.objects.filter(image=old_main).exists())  # old main kept in gallery
        second = photos[1]
        self.client.post(f"/dashboard/products/{self.cpu.pk}/photos/{second.pk}/delete/")
        self.assertFalse(StoredFile.objects.filter(name=second.image.name).exists())  # file cleaned up
        self.assertTrue(ActivityLog.objects.filter(target_type="Product", details__contains="photos added").exists())

    def test_photo_limit(self):
        self.client.force_login(self.owner)
        for i in range(8):
            ProductImage.objects.create(product=self.cpu, image=f"products/x{i}.jpg")
        page = self.client.get(f"/dashboard/products/{self.cpu.pk}/edit/")
        data = {k: v for k, v in page.context["form"].initial.items() if v is not None and k != "image"}
        data.update(category=self.cpu.category_id, extra_photos=[img("c.jpg")])
        res = self.client.post(f"/dashboard/products/{self.cpu.pk}/edit/", data)
        self.assertIn("extra_photos", res.context["form"].errors)

    # --- orders: delivery, payment, packing slip ---

    def test_delivery_payment_and_packing_slip(self):
        self.fill_cart(1)
        o = self.order()
        self.client.force_login(self.owner)
        self.client.post(f"/dashboard/orders/{o.pk}/delivery/", {"courier": "J&T Express",
                                                                "tracking_number": "820012345678",
                                                                "mark_shipped": "1"})
        o.refresh_from_db()
        self.assertEqual(o.status, Order.Status.SHIPPED)
        self.assertIsNotNone(o.shipped_at)
        self.client.post(f"/dashboard/orders/{o.pk}/mark-paid/", {"reference": "ABA-777"})
        o.refresh_from_db()
        self.assertTrue(o.is_paid)
        self.assertEqual(o.payment_ref, "ABA-777")
        slip = self.client.get(f"/dashboard/orders/{o.pk}/packing-slip/")
        self.assertContains(slip, "820012345678")
        self.assertContains(slip, self.cpu.name)
        detail = self.client.get(f"/dashboard/orders/{o.pk}/")
        self.assertContains(detail, "marked paid")  # history
        self.client.force_login(self.customer)
        self.assertContains(self.client.get(f"/orders/{o.pk}/"), "820012345678")

    # --- activity log ---

    def test_activity_log_records_and_is_owner_only(self):
        self.client.force_login(self.owner)
        self.client.post(f"/dashboard/products/{self.cpu.pk}/stock/", {"stock": "3"})
        page = self.client.get(f"/dashboard/products/{self.cpu.pk}/edit/")
        data = {k: v for k, v in page.context["form"].initial.items() if v is not None and k != "image"}
        data.update(category=self.cpu.category_id, price="189.00", is_active="on")
        self.client.post(f"/dashboard/products/{self.cpu.pk}/edit/", data)
        entry = ActivityLog.objects.filter(target_type="Product", target_id=self.cpu.pk).first()
        self.assertIn(f"price ${self.cpu.price} → $189.00", entry.details)
        self.assertEqual(entry.username, "admin")
        res = self.client.get("/dashboard/activity/?q=189")
        self.assertContains(res, "$189.00")
        staff = User.objects.create_user("clerk2", "c2@x.local", "Str0ng-pass-123", is_staff=True)
        self.client.force_login(staff)
        self.assertRedirects(self.client.get("/dashboard/activity/"), "/dashboard/team/")

    # --- demo owner hidden on the live site ---

    def test_demo_admin_hidden_when_configured(self):
        with self.settings(SHOW_DEMO_ADMIN=False):
            names = [a["username"] for a in self.client.get("/api/auth/demo-accounts/").json()]
            self.assertNotIn("admin", names)
            self.assertIn("demo", names)
        with self.settings(SHOW_DEMO_ADMIN=True):
            self.assertIn("admin", [a["username"] for a in self.client.get("/api/auth/demo-accounts/").json()])
