from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.urls import reverse
from django.utils.text import slugify


class Category(models.Model):
    class Group(models.TextChoices):
        COMPUTERS = "computers", "Laptops & Monitors"
        COMPONENTS = "components", "PC Components"
        ACCESSORIES = "accessories", "Accessories"

    name = models.CharField(max_length=80, unique=True)
    slug = models.SlugField(max_length=90, unique=True, blank=True)
    icon = models.CharField(
        max_length=40, default="box-seam",
        help_text="Bootstrap Icons name, e.g. 'keyboard', 'mouse', 'headphones'",
    )
    group = models.CharField(max_length=20, choices=Group.choices, default=Group.ACCESSORIES)
    position = models.PositiveSmallIntegerField(default=0, help_text="Order inside its group")

    class Meta:
        ordering = ["position", "name"]
        verbose_name_plural = "categories"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Product(models.Model):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=160, unique=True, blank=True)
    brand = models.CharField(max_length=80, blank=True)
    sku = models.CharField("SKU", max_length=40, blank=True, db_index=True,
                           help_text="Optional. Must be unique.")
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2,
                                validators=[MinValueValidator(Decimal("0.01"))])
    compare_at_price = models.DecimalField(
        "Original price", max_digits=10, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
        help_text="Optional. Shows a sale.")
    stock = models.PositiveIntegerField(default=0)
    image = models.ImageField(upload_to="products/", blank=True, null=True)
    specs = models.JSONField(
        default=dict, blank=True,
        help_text='Spec sheet, e.g. {"summary": "Core i5 · 16GB · 512GB SSD", "Processor": "Intel Core i5-1335U"}. '
                  'PC parts also have "compat": {socket, memory_type, form_factor, form_factors, tdp, wattage, '
                  "integrated_graphics} for the PC builder.")
    # Credit for freely licensed photos (e.g. from Wikimedia Commons), shown under the image.
    photo_credit = models.CharField(max_length=255, blank=True)
    photo_license = models.CharField(max_length=60, blank=True)
    photo_source = models.URLField(max_length=500, blank=True)
    photo_similar = models.BooleanField(default=False, help_text="The photo shows a closely related model.")
    is_featured = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.slug:
            base = slugify(self.name) or "product"
            slug, n = base, 2
            while Product.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        super().save(*args, **kwargs)

    def get_absolute_url(self):
        return reverse("store:product_detail", args=[self.slug])

    @property
    def on_sale(self):
        return bool(self.compare_at_price and self.compare_at_price > self.price)

    @property
    def discount_percent(self):
        if not self.on_sale:
            return 0
        return int(round((1 - self.price / self.compare_at_price) * 100))

    @property
    def in_stock(self):
        return self.stock > 0

    @property
    def summary(self):
        return (self.specs or {}).get("summary", "")

    @property
    def compat(self):
        """PC-builder fields, e.g. {"socket": "AM5", "tdp": 65}."""
        return (self.specs or {}).get("compat", {})

    @property
    def spec_rows(self):
        """Spec sheet rows for the product page, e.g. [("Processor", "Intel Core i5"), ...]."""
        return [(k, v) for k, v in (self.specs or {}).items() if k not in ("summary", "compat")]

    def __str__(self):
        return self.name


class CartItem(models.Model):
    """One product line in a logged-in user's cart."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="cart_items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1, validators=[MinValueValidator(1)])
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "product")
        ordering = ["added_at"]

    @property
    def subtotal(self):
        return self.product.price * self.quantity

    def __str__(self):
        return f"{self.quantity} x {self.product}"


class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    class PaymentMethod(models.TextChoices):
        COD = "cod", "Cash on delivery"
        QR = "qr", "KHQR bank transfer"

    class PaymentStatus(models.TextChoices):
        UNPAID = "unpaid", "Unpaid"
        PAID = "paid", "Paid"
        REFUNDED = "refunded", "Refunded"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                             related_name="orders")
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=30)
    address = models.TextField()
    note = models.CharField(max_length=255, blank=True)
    payment_method = models.CharField(max_length=10, choices=PaymentMethod.choices,
                                      default=PaymentMethod.COD)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.PENDING)
    payment_status = models.CharField(max_length=10, choices=PaymentStatus.choices,
                                      default=PaymentStatus.UNPAID)
    paid_at = models.DateTimeField(null=True, blank=True)
    payment_ref = models.CharField(max_length=40, blank=True, help_text="Bank / KHQR transaction reference")
    total = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    discount_code = models.CharField(max_length=40, blank=True)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    courier = models.CharField(max_length=60, blank=True)
    tracking_number = models.CharField(max_length=80, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    @property
    def subtotal(self):
        """Items before the discount (the total is what the customer pays)."""
        return self.total + self.discount_amount

    @property
    def number(self):
        return f"TC-{self.pk:05d}"

    @property
    def receipt_number(self):
        return f"RC-{self.pk:05d}"

    @property
    def is_paid(self):
        return self.payment_status == self.PaymentStatus.PAID

    @property
    def awaiting_qr_payment(self):
        return (self.payment_method == self.PaymentMethod.QR and self.payment_status == self.PaymentStatus.UNPAID
                and self.status != self.Status.CANCELLED)

    @property
    def payment_color(self):
        return {"paid": "success", "refunded": "secondary"}.get(self.payment_status, "warning")

    @property
    def status_color(self):
        return {
            "pending": "warning", "confirmed": "info", "shipped": "primary",
            "delivered": "success", "cancelled": "secondary",
        }.get(self.status, "secondary")

    def __str__(self):
        return f"Order {self.number}"


class OrderItem(models.Model):
    """A product line inside an order. Price is copied so later price changes don't alter old orders."""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True)
    product_name = models.CharField(max_length=150)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()

    @property
    def subtotal(self):
        return self.price * self.quantity

    def __str__(self):
        return f"{self.quantity} x {self.product_name}"


class StoredFile(models.Model):
    """An uploaded file kept in the database (store/storage.py). Used on Vercel, whose disk is read-only."""
    name = models.CharField(max_length=255, unique=True)
    content = models.BinaryField()
    content_type = models.CharField(max_length=100, blank=True)
    size = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class ProductImage(models.Model):
    """Extra gallery photos of a product (the main photo is Product.image)."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="photos")
    image = models.ImageField(upload_to="products/gallery/")
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return f"Photo of {self.product}"


class DiscountCode(models.Model):
    class Kind(models.TextChoices):
        PERCENT = "percent", "Percentage off"
        FIXED = "fixed", "Fixed amount off ($)"

    code = models.CharField(max_length=40, unique=True,
                            help_text="What customers type at checkout, e.g. NEWYEAR10. Letters and numbers.")
    description = models.CharField(max_length=160, blank=True, help_text="Internal note, e.g. “New Year campaign”.")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.PERCENT)
    value = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))],
                                help_text="10 = 10% off (percentage) or $10 off (fixed amount).")
    min_order = models.DecimalField("Minimum order", max_digits=10, decimal_places=2, default=Decimal("0.00"),
                                    help_text="Order subtotal needed to use the code. 0 = no minimum.")
    max_uses = models.PositiveIntegerField("Total uses allowed", null=True, blank=True,
                                           help_text="Leave empty for unlimited.")
    once_per_customer = models.BooleanField(default=True)
    used_count = models.PositiveIntegerField(default=0)
    starts_at = models.DateTimeField("Starts", null=True, blank=True)
    ends_at = models.DateTimeField("Ends", null=True, blank=True)
    is_active = models.BooleanField("Active", default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return self.code

    @property
    def label(self):
        return f"{self.value.normalize():f}% off" if self.kind == self.Kind.PERCENT else f"${self.value:,.2f} off"

    @property
    def state(self):
        """("Active" | "Scheduled" | "Expired" | "Used up" | "Off", bootstrap colour)."""
        from django.utils import timezone
        now = timezone.now()
        if not self.is_active:
            return "Off", "secondary"
        if self.ends_at and self.ends_at < now:
            return "Expired", "secondary"
        if self.max_uses is not None and self.used_count >= self.max_uses:
            return "Used up", "secondary"
        if self.starts_at and self.starts_at > now:
            return "Scheduled", "info"
        return "Active", "success"

    def amount_for(self, subtotal):
        if self.kind == self.Kind.PERCENT:
            amount = (subtotal * min(self.value, Decimal("100")) / 100).quantize(Decimal("0.01"))
        else:
            amount = self.value
        return min(amount, subtotal)


class ActivityLog(models.Model):
    """Who changed what in the admin dashboard, and when."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
                             related_name="+")
    username = models.CharField(max_length=150)
    action = models.CharField(max_length=30)
    target_type = models.CharField(max_length=30)
    target_id = models.PositiveIntegerField(null=True, blank=True)
    target_label = models.CharField(max_length=200, blank=True)
    details = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]

    @property
    def icon(self):
        return {"Product": "box-seam", "Category": "tags", "Order": "receipt", "Customer": "person",
                "Admin": "shield-lock", "Discount": "ticket-perforated"}.get(self.target_type, "dot")

    @property
    def color(self):
        return {"deleted": "danger", "removed": "danger", "blocked": "danger", "created": "success",
                "added": "success"}.get(self.action, "primary")

    def __str__(self):
        return f"{self.username} {self.action} {self.target_type} {self.target_label}"
