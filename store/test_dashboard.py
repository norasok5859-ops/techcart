import io
import tempfile

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from PIL import Image

from store.models import Category, Product, StoredFile


def png_bytes(size=(2400, 1800)):
    out = io.BytesIO()
    Image.new("RGB", size, (90, 80, 240)).save(out, "PNG")
    return out.getvalue()


class DashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            call_command("seed", no_photos=True, stdout=io.StringIO())
        cls.owner = User.objects.get(username="admin")
        cls.staff = User.objects.create_user("clerk", "clerk@techcart.local", "Str0ng-pass-123", is_staff=True)
        cls.customer = User.objects.get(username="demo")
        cls.cat = Category.objects.get(slug="laptops")

    def login(self, user):
        self.client.force_login(user)

    # --- access ---

    def test_pages_need_staff(self):
        self.assertEqual(self.client.get("/dashboard/").status_code, 302)
        self.login(self.customer)
        self.assertEqual(self.client.get("/dashboard/products/").status_code, 302)

    def test_all_pages_render_for_owner(self):
        self.login(self.owner)
        for url in ("/dashboard/", "/dashboard/products/", "/dashboard/products/new/", "/dashboard/categories/",
                    "/dashboard/categories/new/", "/dashboard/orders/", "/dashboard/customers/",
                    "/dashboard/team/", "/dashboard/team/new/", f"/dashboard/team/{self.staff.pk}/edit/",
                    "/dashboard/products/?stock=low&status=active&q=asus"):
            self.assertEqual(self.client.get(url).status_code, 200, url)

    # --- admin team ---

    def test_owner_adds_staff_admin(self):
        self.login(self.owner)
        res = self.client.post("/dashboard/team/new/", {
            "first_name": "Dara", "last_name": "Sok", "username": "dara", "email": "dara@techcart.local",
            "role": "staff", "password1": "Laptop-Store-2026", "password2": "Laptop-Store-2026"})
        self.assertRedirects(res, "/dashboard/team/")
        dara = User.objects.get(username="dara")
        self.assertTrue(dara.is_staff)
        self.assertFalse(dara.is_superuser)
        self.assertTrue(dara.check_password("Laptop-Store-2026"))

    def test_owner_adds_owner(self):
        self.login(self.owner)
        self.client.post("/dashboard/team/new/", {
            "first_name": "Mina", "username": "mina", "email": "mina@techcart.local", "role": "owner",
            "password1": "Laptop-Store-2026", "password2": "Laptop-Store-2026"})
        self.assertTrue(User.objects.get(username="mina").is_superuser)

    def test_weak_or_mismatched_password_rejected(self):
        self.login(self.owner)
        res = self.client.post("/dashboard/team/new/", {
            "first_name": "X", "username": "x1", "email": "x1@techcart.local", "role": "staff",
            "password1": "12345678", "password2": "12345678"})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(User.objects.filter(username="x1").exists())
        res = self.client.post("/dashboard/team/new/", {
            "first_name": "X", "username": "x2", "email": "x2@techcart.local", "role": "staff",
            "password1": "Laptop-Store-2026", "password2": "Laptop-Store-2027"})
        self.assertContains(res, "don&#x27;t match")

    def test_staff_cannot_manage_team(self):
        self.login(self.staff)
        self.assertEqual(self.client.get("/dashboard/team/").status_code, 200)
        self.assertRedirects(self.client.get("/dashboard/team/new/"), "/dashboard/team/")
        self.client.post(f"/dashboard/team/{self.owner.pk}/remove/")
        self.assertTrue(User.objects.get(pk=self.owner.pk).is_staff)

    def test_last_owner_is_protected(self):
        self.login(self.owner)
        res = self.client.post(f"/dashboard/team/{self.owner.pk}/edit/", {
            "first_name": "Store", "last_name": "Admin", "email": "admin@techcart.local",
            "role": "staff", "is_active": ""})
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_superuser and self.owner.is_active)  # own role/active fields are locked
        self.client.post(f"/dashboard/team/{self.owner.pk}/remove/")
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_staff)

    def test_owner_edits_and_removes_staff(self):
        self.login(self.owner)
        self.client.post(f"/dashboard/team/{self.staff.pk}/edit/", {
            "first_name": "Clerk", "last_name": "One", "email": "clerk@techcart.local", "role": "owner",
            "is_active": "on", "new_password": "Another-Pass-77"})
        self.staff.refresh_from_db()
        self.assertTrue(self.staff.is_superuser)
        self.assertTrue(self.staff.check_password("Another-Pass-77"))
        self.client.post(f"/dashboard/team/{self.staff.pk}/remove/")
        self.staff.refresh_from_db()
        self.assertFalse(self.staff.is_staff or self.staff.is_superuser)

    # --- products ---

    def product_data(self, **extra):
        data = {"name": "ASUS Zenbook 14 OLED", "category": self.cat.pk, "brand": "ASUS", "sku": "lap-zen-14",
                "price": "999.00", "compare_at_price": "1199.00", "stock": "7",
                "description": "Light 14-inch laptop.", "summary": "Core Ultra 7 · 16GB · 1TB · 14\" OLED",
                "spec_lines": "Processor: Intel Core Ultra 7 155H\nMemory: 16GB LPDDR5X\nWarranty: 2 years",
                "compat_json": "", "is_active": "on"}
        data.update(extra)
        return data

    @override_settings(STORAGES={"default": {"BACKEND": "store.storage.DatabaseStorage"},
                                 "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"}})
    def test_add_product_with_photo_saved_in_database(self):
        self.login(self.staff)
        photo = SimpleUploadedFile("zenbook.png", png_bytes(), content_type="image/png")
        res = self.client.post("/dashboard/products/new/", self.product_data(image=photo))
        self.assertRedirects(res, "/dashboard/products/")
        p = Product.objects.get(name="ASUS Zenbook 14 OLED")
        self.assertEqual(p.sku, "LAP-ZEN-14")
        self.assertTrue(p.on_sale)
        self.assertEqual(p.discount_percent, 17)
        self.assertEqual(p.specs["summary"], "Core Ultra 7 · 16GB · 1TB · 14\" OLED")
        self.assertEqual(p.specs["Processor"], "Intel Core Ultra 7 155H")
        stored = StoredFile.objects.get(name=p.image.name)
        self.assertLessEqual(max(Image.open(io.BytesIO(bytes(stored.content))).size), 1600)  # resized
        res = self.client.get(p.image.url)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res["Content-Type"], "image/png")
        page = self.client.get(p.get_absolute_url())
        self.assertContains(page, "Save 17%")
        self.assertContains(page, "Intel Core Ultra 7 155H")

    def test_product_validation(self):
        self.login(self.staff)
        Product.objects.filter(pk=Product.objects.first().pk).update(sku="TAKEN-1")
        res = self.client.post("/dashboard/products/new/", self.product_data(
            sku="taken-1", compare_at_price="900", spec_lines="no colon here"))
        self.assertEqual(res.status_code, 200)
        form = res.context["form"]
        self.assertIn("sku", form.errors)
        self.assertIn("compare_at_price", form.errors)
        self.assertIn("spec_lines", form.errors)

    def test_edit_keeps_pc_builder_data(self):
        self.login(self.owner)
        cpu = Product.objects.get(name="AMD Ryzen 5 7600")
        page = self.client.get(f"/dashboard/products/{cpu.pk}/edit/")
        form = page.context["form"]
        data = {k: v for k, v in form.initial.items() if v is not None and k != "image"}
        data.update({"category": cpu.category_id, "price": "199.00", "is_active": "on"})
        self.client.post(f"/dashboard/products/{cpu.pk}/edit/", data)
        cpu.refresh_from_db()
        self.assertEqual(str(cpu.price), "199.00")
        self.assertEqual(cpu.compat["socket"], "AM5")

    def test_duplicate_bulk_and_export(self):
        self.login(self.staff)
        p = Product.objects.get(name="AMD Ryzen 5 7600")
        res = self.client.post(f"/dashboard/products/{p.pk}/duplicate/")
        copy = Product.objects.get(name="AMD Ryzen 5 7600 (copy)")
        self.assertRedirects(res, f"/dashboard/products/{copy.pk}/edit/")
        self.assertFalse(copy.is_active)
        self.client.post("/dashboard/products/bulk/", {"ids": [p.pk, copy.pk], "action": "feature"})
        self.assertEqual(Product.objects.filter(pk__in=[p.pk, copy.pk], is_featured=True).count(), 2)
        self.client.post("/dashboard/products/bulk/", {"ids": [copy.pk], "action": "delete"})
        self.assertFalse(Product.objects.filter(pk=copy.pk).exists())
        csv = self.client.get("/dashboard/products/?q=ryzen&export=csv")
        self.assertEqual(csv["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("AMD Ryzen 5 7600", csv.content.decode("utf-8-sig"))

    # --- categories, customers, orders ---

    def test_categories(self):
        self.login(self.staff)
        self.client.post("/dashboard/categories/new/", {"name": "Tablets", "group": "computers",
                                                        "icon": "tablet", "position": 9})
        tablets = Category.objects.get(name="Tablets")
        self.assertEqual(tablets.slug, "tablets")
        self.client.post(f"/dashboard/categories/{self.cat.pk}/delete/")
        self.assertTrue(Category.objects.filter(pk=self.cat.pk).exists())  # has products
        self.client.post(f"/dashboard/categories/{tablets.pk}/delete/")
        self.assertFalse(Category.objects.filter(pk=tablets.pk).exists())

    def test_customers_block_and_promote(self):
        self.login(self.staff)
        self.assertContains(self.client.get("/dashboard/customers/?q=demo"), "@demo")
        self.client.post(f"/dashboard/customers/{self.customer.pk}/toggle/")
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.is_active)
        self.client.post(f"/dashboard/customers/{self.customer.pk}/make-admin/")  # staff can't
        self.customer.refresh_from_db()
        self.assertFalse(self.customer.is_staff)
        self.login(self.owner)
        self.client.post(f"/dashboard/customers/{self.customer.pk}/make-admin/")
        self.customer.refresh_from_db()
        self.assertTrue(self.customer.is_staff)

    def test_orders_search_and_export(self):
        self.login(self.owner)
        self.assertEqual(self.client.get("/dashboard/orders/?q=TC-00001&status=pending&payment=unpaid").status_code, 200)
        res = self.client.get("/dashboard/orders/?export=csv")
        self.assertTrue(res.content.decode("utf-8-sig").startswith("Order,Date,Customer"))
