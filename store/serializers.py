from django.contrib.auth.models import User
from rest_framework import serializers

from .models import CartItem, Category, Order, OrderItem, Product


class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Category
        fields = ["id", "name", "slug", "icon", "group", "position", "product_count"]
        read_only_fields = ["slug"]


class ProductSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    in_stock = serializers.BooleanField(read_only=True)
    on_sale = serializers.BooleanField(read_only=True)

    class Meta:
        model = Product
        fields = ["id", "name", "slug", "brand", "sku", "description", "price", "compare_at_price", "on_sale",
                  "stock", "in_stock",
                  "image", "specs", "is_featured", "is_active", "category", "category_name",
                  "created_at", "updated_at"]
        read_only_fields = ["slug", "created_at", "updated_at"]


class BuilderPartSerializer(serializers.ModelSerializer):
    in_stock = serializers.BooleanField(read_only=True)
    summary = serializers.CharField(read_only=True)
    url = serializers.CharField(source="get_absolute_url", read_only=True)

    class Meta:
        model = Product
        fields = ["id", "name", "brand", "price", "stock", "in_stock", "image", "summary", "compat", "url"]

    compat = serializers.DictField(read_only=True)


class BuilderSlotSerializer(serializers.Serializer):
    slot = serializers.CharField()
    label = serializers.CharField()
    required = serializers.BooleanField()
    icon = serializers.CharField()
    parts = BuilderPartSerializer(many=True)


class BuildRequestSerializer(serializers.Serializer):
    parts = serializers.DictField(child=serializers.IntegerField(allow_null=True),
                                  help_text='e.g. {"cpu": 12, "motherboard": 20, "ram": 25}')


class BuildIssueSerializer(serializers.Serializer):
    level = serializers.ChoiceField(choices=["error", "warning"])
    message = serializers.CharField()


class BuildReportSerializer(serializers.Serializer):
    parts = serializers.DictField(child=serializers.IntegerField())
    total = serializers.DecimalField(max_digits=10, decimal_places=2)
    estimated_watts = serializers.IntegerField()
    recommended_psu_watts = serializers.IntegerField()
    missing = serializers.ListField(child=serializers.CharField())
    issues = BuildIssueSerializer(many=True)
    compatible = serializers.BooleanField()
    complete = serializers.BooleanField()
    ready = serializers.BooleanField()


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True), source="product", write_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ["id", "product", "product_id", "quantity", "subtotal", "added_at"]


class CartItemUpdateSerializer(serializers.Serializer):
    quantity = serializers.IntegerField(min_value=0)


class OrderItemSerializer(serializers.ModelSerializer):
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "product", "product_name", "price", "quantity", "subtotal"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    number = serializers.CharField(read_only=True)
    customer = serializers.CharField(source="user.username", read_only=True)
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    discount_code = serializers.CharField(required=False, allow_blank=True, max_length=40,
                                          help_text="Optional discount code, e.g. NEWYEAR10")

    class Meta:
        model = Order
        fields = ["id", "number", "customer", "full_name", "phone", "address", "note",
                  "payment_method", "payment_status", "paid_at", "payment_ref",
                  "status", "subtotal", "discount_code", "discount_amount", "total",
                  "courier", "tracking_number", "shipped_at", "items", "created_at"]
        read_only_fields = ["payment_status", "paid_at", "payment_ref", "status", "total", "created_at",
                            "discount_amount", "courier", "tracking_number", "shipped_at"]


class PaymentQRSerializer(serializers.Serializer):
    order = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField()
    payload = serializers.CharField(help_text="KHQR / EMVCo string to encode in a QR code")
    svg = serializers.CharField(help_text="Ready-made QR code as inline SVG")
    expires_in_seconds = serializers.IntegerField()
    merchant = serializers.CharField()
    account = serializers.CharField()


class ReceiptSerializer(serializers.Serializer):
    receipt_number = serializers.CharField()
    order_number = serializers.CharField()
    date = serializers.DateTimeField()
    customer = serializers.CharField()
    phone = serializers.CharField()
    address = serializers.CharField()
    items = serializers.ListField(child=serializers.DictField())
    subtotal = serializers.DecimalField(max_digits=12, decimal_places=2)
    delivery = serializers.DecimalField(max_digits=12, decimal_places=2)
    total = serializers.DecimalField(max_digits=12, decimal_places=2)
    currency = serializers.CharField()
    payment_method = serializers.CharField()
    payment_status = serializers.CharField()
    payment_ref = serializers.CharField(allow_blank=True)
    paid_at = serializers.DateTimeField(allow_null=True)
    order_status = serializers.CharField()


class OrderStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices)


class StockSerializer(serializers.Serializer):
    stock = serializers.IntegerField(min_value=0)


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "password"]

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class DemoAccountSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()
    email = serializers.EmailField()
    first_name = serializers.CharField()
    role = serializers.CharField()
    note = serializers.CharField()


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "is_staff"]
