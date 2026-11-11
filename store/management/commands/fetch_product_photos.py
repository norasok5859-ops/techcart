"""Download real product photos from Wikimedia Commons, frame them as square shop images and credit them."""
import html
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from PIL import Image, ImageFilter, ImageOps

from store.models import Product
from store.product_photos import PHOTOS

API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "TechCartDemo/1.0 (educational e-commerce project; python-urllib)"
PREFIX = "products/photo-"
SIZE = 900


def _get(url, timeout=40, tries=4):
    """GET with a polite retry when Wikimedia says 'Too Many Requests'."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code != 429 or attempt == tries - 1:
                raise
            wait = e.headers.get("Retry-After", "")
            time.sleep(min(int(wait) if wait.isdigit() else 5 * (attempt + 1), 30))


def _clean(text):
    return html.unescape(re.sub(r"<[^>]+>", "", text or "")).strip()


def file_info(title):
    """URL of a 1200px rendition plus author / licence metadata for a Commons file."""
    q = urllib.parse.urlencode({"action": "query", "format": "json", "titles": title, "prop": "imageinfo",
                                "iiprop": "url|extmetadata", "iiurlwidth": 1200})
    pages = json.loads(_get(f"{API}?{q}"))["query"]["pages"]
    page = next(iter(pages.values()))
    if "imageinfo" not in page:
        raise LookupError(f"{title} not found on Wikimedia Commons")
    ii = page["imageinfo"][0]
    meta = ii.get("extmetadata", {})
    artist = _clean(meta.get("Artist", {}).get("value")) or "Unknown author"
    return {
        "url": ii.get("thumburl") or ii["url"],
        "page": ii["descriptionurl"],
        "artist": re.sub(r"\s+", " ", artist)[:150],
        "license": _clean(meta.get("LicenseShortName", {}).get("value"))[:60],
    }


def frame_square(raw):
    """Fit the photo in a square on a soft, blurred copy of itself (no cropping of the product)."""
    img = ImageOps.exif_transpose(Image.open(io.BytesIO(raw)))
    if img.mode in ("RGBA", "LA", "P"):
        rgba = img.convert("RGBA")
        flat = Image.new("RGB", rgba.size, (246, 247, 251))
        flat.paste(rgba, mask=rgba.split()[3])
        img = flat
    img = img.convert("RGB")
    bg = ImageOps.fit(img, (SIZE, SIZE)).filter(ImageFilter.GaussianBlur(40))
    bg = Image.blend(bg, Image.new("RGB", bg.size, (246, 247, 251)), 0.55)
    fg = ImageOps.contain(img, (SIZE - 60, SIZE - 60))
    bg.paste(fg, ((SIZE - fg.width) // 2, (SIZE - fg.height) // 2))
    out = io.BytesIO()
    bg.save(out, "JPEG", quality=86, optimize=True, progressive=True)
    return out.getvalue()


class Command(BaseCommand):
    help = "Download freely licensed real product photos (Wikimedia Commons) and attach them with credits."

    def add_arguments(self, parser):
        parser.add_argument("--force", action="store_true", help="Download again even if a photo is already set.")

    def handle(self, *args, force=False, **options):
        out_dir = Path(settings.MEDIA_ROOT) / "products"
        out_dir.mkdir(parents=True, exist_ok=True)
        done = kept = failed = 0
        for name, (title, exact) in PHOTOS.items():
            product = Product.objects.filter(name=name).first()
            if product is None:
                continue
            current = product.image.name if product.image else ""
            if current and not current.startswith(("products/art-", PREFIX)):
                kept += 1  # an admin uploaded their own image
                continue
            path = f"{PREFIX}{product.slug}.jpg"
            if current == path and (out_dir / Path(path).name).exists() and not force:
                kept += 1
                continue
            time.sleep(1.5)  # be gentle with Wikimedia's servers
            try:
                info = file_info(title)
                (Path(settings.MEDIA_ROOT) / path).write_bytes(frame_square(_get(info["url"])))
            except Exception as e:  # network problems: keep the illustration
                failed += 1
                self.stderr.write(f"  ! {name}: {e}")
                continue
            product.image.name = path
            product.photo_credit, product.photo_license = info["artist"], info["license"]
            product.photo_source, product.photo_similar = info["page"], not exact
            product.save(update_fields=["image", "photo_credit", "photo_license", "photo_source", "photo_similar"])
            done += 1
            self.stdout.write(f"  + {name}")
        msg = f"Product photos: {done} downloaded, {kept} already in place"
        if failed:
            msg += f", {failed} failed (they keep their illustration; run the command again later)"
        self.stdout.write(self.style.SUCCESS(msg))
