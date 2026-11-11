import io
import tempfile

from django.contrib.auth.models import User
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from store.models import CartItem, Product


class PCBuilderTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        with tempfile.TemporaryDirectory() as media, override_settings(MEDIA_ROOT=media):
            call_command("seed", no_photos=True, stdout=io.StringIO())

    def setUp(self):
        self.api = APIClient()
        self.id = {p.name: p.pk for p in Product.objects.all()}
        self.good = {
            "cpu": self.id["AMD Ryzen 5 7600"],
            "motherboard": self.id["MSI PRO B650M-A WiFi"],
            "ram": self.id["Kingston FURY Beast 16GB (2×8GB) DDR5-5600"],
            "storage": self.id["Crucial P3 Plus 1TB NVMe SSD"],
            "psu": self.id["Cooler Master MWE 650 Bronze V2"],
            "case": self.id["NZXT H5 Flow"],
        }

    def check(self, parts):
        res = self.api.post("/api/pc-builder/check/", {"parts": parts}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        return res.data

    def test_parts_endpoint_lists_every_slot(self):
        data = self.api.get("/api/pc-builder/parts/").data
        self.assertEqual([s["slot"] for s in data], ["cpu", "motherboard", "ram", "gpu", "storage", "psu", "case"])
        self.assertTrue(all(len(s["parts"]) == 4 for s in data))

    def test_compatible_build_is_ready(self):
        report = self.check(self.good)
        self.assertTrue(report["ready"], report)
        self.assertEqual(report["issues"], [])
        self.assertEqual(report["total"], "639.00")

    def test_incompatible_parts_are_reported(self):
        bad = dict(self.good, cpu=self.id["Intel Core i5-14400F"],
                   ram=self.id["Corsair Vengeance LPX 16GB (2×8GB) DDR4-3200"],
                   motherboard=self.id["ASUS TUF Gaming B650-PLUS WiFi"],
                   case=self.id["Cooler Master MasterBox Q300L"])
        messages = " ".join(i["message"] for i in self.check(bad)["issues"])
        for expected in ("socket", "DDR5", "does not fit", "no built-in graphics"):
            self.assertIn(expected, messages)

    def test_power_supply_too_small(self):
        build = dict(self.good, cpu=self.id["Intel Core i7-14700K"],
                     motherboard=self.id["ASUS ROG Strix Z790-E Gaming WiFi"],
                     gpu=self.id["Gigabyte GeForce RTX 4080 SUPER Gaming OC 16GB"])
        report = self.check(build)
        self.assertFalse(report["ready"])
        self.assertIn("too weak", report["issues"][0]["message"])

    def test_wrong_category_rejected(self):
        res = self.api.post("/api/pc-builder/check/", {"parts": {"cpu": self.id["NZXT H5 Flow"]}}, format="json")
        self.assertEqual(res.status_code, 400)

    def test_add_build_to_cart(self):
        self.assertEqual(self.api.post("/api/pc-builder/add-to-cart/", {"parts": self.good}, format="json").status_code, 401)
        user = User.objects.get(username="demo")
        self.api.force_authenticate(user)
        res = self.api.post("/api/pc-builder/add-to-cart/", {"parts": self.good}, format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(CartItem.objects.filter(user=user).count(), 6)

    def test_incomplete_build_not_added(self):
        self.api.force_authenticate(User.objects.get(username="demo"))
        parts = {k: v for k, v in self.good.items() if k != "psu"}
        res = self.api.post("/api/pc-builder/add-to-cart/", {"parts": parts}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("Power supply", res.data["detail"])

    def test_pages_render(self):
        for url in ("/", "/build-pc/", "/products/", "/category/gaming-laptops/", "/product/asus-tuf-gaming-a15/"):
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.assertContains(self.client.get("/product/asus-tuf-gaming-a15/"), "NVIDIA GeForce RTX 4060")
