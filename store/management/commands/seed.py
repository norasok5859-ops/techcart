from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import BaseCommand

from accounts.demo import DEMO_ACCOUNTS
from store.catalog import CATEGORIES, PRODUCTS, RENAMED
from store.models import Category, Product


class Command(BaseCommand):
    help = "Load the sample catalogue (laptops, monitors, PC parts, accessories), demo users and product images."

    def add_arguments(self, parser):
        parser.add_argument("--no-photos", action="store_true",
                            help="Skip downloading real product photos (offline / tests); illustrations are used.")

    def handle(self, *args, **options):
        cats = {}
        for name, icon, group, position in CATEGORIES:
            cat, _ = Category.objects.get_or_create(name=name)
            cat.icon, cat.group, cat.position = icon, group, position
            cat.save()
            cats[name] = cat

        # Products from older seeds (invented brands) become their real-brand versions.
        renamed = 0
        for old, new in RENAMED.items():
            product = Product.objects.filter(name=old).first()
            if product and not Product.objects.filter(name=new).exists():
                product.name, product.slug = new, ""  # save() builds a fresh slug from the new name
                product.save()
                renamed += 1

        created = 0
        for item in PRODUCTS:
            product, was_created = Product.objects.get_or_create(
                name=item["name"],
                defaults=dict(category=cats[item["cat"]], brand=item["brand"], price=Decimal(item["price"]),
                              stock=item["stock"], is_featured=item["featured"], description=item["desc"],
                              specs=item["specs"]),
            )
            if not was_created:
                # Keep stock and active state an admin may have changed; refresh the catalogue data.
                product.category = cats[item["cat"]]
                product.brand, product.description, product.specs = item["brand"], item["desc"], item["specs"]
                product.price, product.is_featured = Decimal(item["price"]), item["featured"]
                product.save()
            created += was_created

        # Demo accounts always end up with the documented passwords, so they can always log in.
        for acc in DEMO_ACCOUNTS:
            user, _ = User.objects.get_or_create(username=acc["username"])
            user.email = acc["email"]
            user.first_name, user.last_name = acc["first_name"], acc["last_name"]
            user.is_staff = user.is_superuser = acc["is_staff"]
            user.is_active = True
            # Only reset a password that changed: set_password() logs the user out of every
            # open browser session, which broke API calls on pages that were already open.
            if not user.check_password(acc["password"]):
                user.set_password(acc["password"])
            user.save()

        call_command("generate_product_art", stdout=self.stdout)
        if not options["no_photos"]:
            # Real photos replace the illustrations where a freely licensed one exists (needs internet).
            call_command("fetch_product_photos", stdout=self.stdout, stderr=self.stderr)

        self.stdout.write(self.style.SUCCESS(
            f"Seed done: {len(cats)} categories, {len(PRODUCTS)} catalogue products "
            f"({created} new, {renamed} renamed to real brands). Users -> "
            + ", ".join(f"{a['username']}/{a['password']} ({a['role'].lower()})" for a in DEMO_ACCOUNTS)))
