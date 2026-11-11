from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from store.catalog import PRODUCTS
from store.models import Product
from store.product_art_tech import render

PREFIX = "products/art-"
ART_BY_NAME = {p["name"]: p["art"] for p in PRODUCTS if p.get("art")}


class Command(BaseCommand):
    help = "Generate SVG product images for the sample catalogue and attach them to the products."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true",
                            help="Also replace images that were uploaded by hand.")

    def handle(self, *args, force=False, **options):
        out_dir = Path(settings.MEDIA_ROOT) / "products"
        out_dir.mkdir(parents=True, exist_ok=True)
        done = skipped = 0
        for product in Product.objects.select_related("category"):
            art = ART_BY_NAME.get(product.name)
            if art is None:
                continue
            if product.image and not product.image.name.startswith(PREFIX) and not force:
                skipped += 1  # keep images an admin uploaded
                continue
            kind, opts = art
            name = f"{PREFIX}{product.slug}.svg"
            (Path(settings.MEDIA_ROOT) / name).write_text(render(kind, opts, product.category.name),
                                                          encoding="utf-8")
            if product.image.name != name:
                product.image.name = name
                product.save(update_fields=["image"])
            done += 1
        # Remove generated images that no product uses any more (e.g. after a rename).
        in_use = set(Product.objects.filter(image__startswith=PREFIX).values_list("image", flat=True))
        for f in out_dir.glob("art-*.svg"):
            if f"products/{f.name}" not in in_use:
                f.unlink()
        msg = f"Product art: {done} image(s) generated"
        if skipped:
            msg += f", {skipped} kept (real photo or admin upload; --force replaces them)"
        self.stdout.write(self.style.SUCCESS(msg))
