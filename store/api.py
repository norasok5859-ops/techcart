"""REST API views (Django REST Framework)."""
from django.conf import settings
from django.db.models import Count, Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, mixins, permissions, status, viewsets
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.decorators import action
from rest_framework.response import Response

from accounts.demo import public_demo_accounts

from . import payments, pc_builder, services
from .models import CartItem, Category, Order, Product
from .permissions import IsAdminOrReadOnly
from .serializers import (BuilderPartSerializer, BuilderSlotSerializer, BuildReportSerializer,
                          BuildRequestSerializer, CartItemSerializer, CartItemUpdateSerializer,
                          CategorySerializer, DemoAccountSerializer, OrderSerializer,
                          OrderStatusSerializer, PaymentQRSerializer, ProductSerializer, ReceiptSerializer,
                          RegisterSerializer, StockSerializer, UserSerializer)


# ---------- Catalogue ----------

class CategoryViewSet(viewsets.ModelViewSet):
    """List categories (public). Create / update / delete: admin only."""
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    pagination_class = None

    def get_queryset(self):
        return Category.objects.annotate(
            product_count=Count("products", filter=Q(products__is_active=True)))


@extend_schema(parameters=[
    OpenApiParameter("search", str, description="Search name, brand or description"),
    OpenApiParameter("category", str, description="Category slug"),
    OpenApiParameter("min_price", float), OpenApiParameter("max_price", float),
    OpenApiParameter("in_stock", bool),
    OpenApiParameter("ordering", str, enum=["price", "-price", "name", "-created_at"]),
])
class ProductViewSet(viewsets.ModelViewSet):
    """Products. Reading is public; create / update / delete / stock changes are admin only."""
    serializer_class = ProductSerializer
    permission_classes = [IsAdminOrReadOnly]
    lookup_field = "slug"

    def get_queryset(self):
        qs = Product.objects.select_related("category")
        if not self.request.user.is_staff:
            qs = qs.filter(is_active=True)
        p = self.request.query_params
        if p.get("search"):
            term = p["search"]
            qs = qs.filter(Q(name__icontains=term) | Q(brand__icontains=term)
                           | Q(description__icontains=term))
        if p.get("category"):
            qs = qs.filter(category__slug=p["category"])
        if p.get("min_price"):
            qs = qs.filter(price__gte=p["min_price"])
        if p.get("max_price"):
            qs = qs.filter(price__lte=p["max_price"])
        if p.get("in_stock") in ("1", "true", "True"):
            qs = qs.filter(stock__gt=0)
        if p.get("ordering") in ("price", "-price", "name", "-created_at"):
            qs = qs.order_by(p["ordering"])
        return qs

    @extend_schema(request=StockSerializer, responses=ProductSerializer)
    @action(detail=True, methods=["patch"], permission_classes=[permissions.IsAdminUser])
    def stock(self, request, slug=None):
        """Admin: set the stock level, body {"stock": 25}."""
        product = self.get_object()
        s = StockSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        product.stock = s.validated_data["stock"]
        product.save(update_fields=["stock"])
        return Response(ProductSerializer(product, context={"request": request}).data)


# ---------- Cart (customer) ----------

class CartViewSet(mixins.ListModelMixin, mixins.CreateModelMixin, mixins.RetrieveModelMixin,
                  mixins.DestroyModelMixin, viewsets.GenericViewSet):
    """The logged-in user's cart. POST adds a product (or increases its quantity)."""
    serializer_class = CartItemSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def get_queryset(self):
        return CartItem.objects.filter(user=self.request.user).select_related("product__category")

    def list(self, request, *args, **kwargs):
        items, total, count = services.get_cart(request.user)
        data = CartItemSerializer(items, many=True, context={"request": request}).data
        return Response({"items": data, "total": str(total), "count": count})

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            item = services.add_to_cart(request.user, serializer.validated_data["product"],
                                        serializer.validated_data.get("quantity", 1))
        except services.CartError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(item).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=CartItemUpdateSerializer, responses=CartItemSerializer)
    def partial_update(self, request, *args, **kwargs):
        """Change quantity, body {"quantity": 3}. Quantity 0 removes the item."""
        item = self.get_object()
        s = CartItemUpdateSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            item = services.set_quantity(item, s.validated_data["quantity"])
        except services.CartError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        if item is None:
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(self.get_serializer(item).data)

    @action(detail=False, methods=["delete"])
    def clear(self, request):
        self.get_queryset().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------- Orders ----------

class OrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, mixins.CreateModelMixin,
                   viewsets.GenericViewSet):
    """Customers see and place their own orders (cash on delivery); admins see all orders."""
    serializer_class = OrderSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        qs = Order.objects.prefetch_related("items").select_related("user")
        if not self.request.user.is_staff:
            qs = qs.filter(user=self.request.user)
        if self.request.query_params.get("status"):
            qs = qs.filter(status=self.request.query_params["status"])
        return qs

    def create(self, request, *args, **kwargs):
        """Checkout: converts the current cart into an order and reduces stock."""
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            order = services.place_order(
                request.user, payment_method=s.validated_data.get("payment_method", Order.PaymentMethod.COD),
                discount_code=s.validated_data.get("discount_code", ""),
                **{k: s.validated_data.get(k, "") for k in ("full_name", "phone", "address", "note")})
        except services.CartError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(self.get_serializer(order).data, status=status.HTTP_201_CREATED)

    @extend_schema(request=OrderStatusSerializer, responses=OrderSerializer)
    @action(detail=True, methods=["patch"], permission_classes=[permissions.IsAdminUser])
    def status(self, request, pk=None):
        """Admin: update order status, body {"status": "shipped"}."""
        order = self.get_object()
        s = OrderStatusSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            services.change_order_status(order, s.validated_data["status"])
        except services.CartError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(self.get_serializer(order).data)

    @extend_schema(request=None, responses=PaymentQRSerializer)
    @action(detail=True, methods=["get"], url_path="payment-qr")
    def payment_qr(self, request, pk=None):
        """KHQR code for an unpaid QR order: the payload string and a ready-made SVG."""
        try:
            return Response(payments.payment_qr(self.get_object()))
        except payments.PaymentError as e:
            return Response({"detail": str(e)}, status=400)

    @extend_schema(request=None, responses=OrderSerializer)
    @action(detail=True, methods=["post"], url_path="confirm-payment")
    def confirm_payment(self, request, pk=None):
        """Demo: confirm the KHQR payment (a real shop would check with the bank first)."""
        order = self.get_object()
        if order.user_id != request.user.id:
            return Response({"detail": "Only the customer can confirm their payment."}, status=403)
        try:
            order = payments.confirm_payment(order)
        except payments.PaymentError as e:
            return Response({"detail": str(e)}, status=400)
        return Response(self.get_serializer(order).data)

    @extend_schema(responses=ReceiptSerializer)
    @action(detail=True, methods=["get"])
    def receipt(self, request, pk=None):
        """Receipt / invoice data for an order."""
        return Response(ReceiptSerializer(payments.receipt_data(self.get_object())).data)

    @extend_schema(request=None, responses=OrderSerializer)
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        """Customer: cancel own order while it is still pending."""
        order = self.get_object()
        if order.status != Order.Status.PENDING:
            return Response({"detail": "Only pending orders can be cancelled."}, status=400)
        services.change_order_status(order, Order.Status.CANCELLED)
        return Response(self.get_serializer(order).data)


# ---------- Auth ----------

class RegisterView(generics.CreateAPIView):
    """Create a customer account. Returns the user and an API token."""
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        s = self.get_serializer(data=request.data)
        s.is_valid(raise_exception=True)
        user = s.save()
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"user": UserSerializer(user).data, "token": token.key}, status=201)


class LoginView(ObtainAuthToken):
    """Log in with username + password and receive an API token."""

    def post(self, request, *args, **kwargs):
        s = self.serializer_class(data=request.data, context={"request": request})
        s.is_valid(raise_exception=True)
        user = s.validated_data["user"]
        token, _ = Token.objects.get_or_create(user=user)
        return Response({"token": token.key, "user": UserSerializer(user).data})


# ---------- PC builder ----------

class PCBuildPartsView(generics.GenericAPIView):
    """Every part the PC builder offers, grouped by slot (cpu, motherboard, ram, gpu, storage, psu, case)."""
    queryset = Product.objects.none()  # the browsable API needs a queryset; these views do not list one
    permission_classes = [permissions.AllowAny]
    serializer_class = BuilderPartSerializer
    pagination_class = None

    @extend_schema(responses=BuilderSlotSerializer(many=True))
    def get(self, request):
        grouped = pc_builder.parts_by_slot()
        data = [{"slot": slot, "label": label, "required": required, "icon": icon,
                 "parts": BuilderPartSerializer(grouped[slot], many=True, context={"request": request}).data}
                for slot, label, _cat, required, icon in pc_builder.SLOTS]
        return Response(data)


class PCBuildCheckView(generics.GenericAPIView):
    """Check a build: body {"parts": {"cpu": 1, "motherboard": 5, ...}}. Returns total, power and issues."""
    queryset = Product.objects.none()  # the browsable API needs a queryset; these views do not list one
    permission_classes = [permissions.AllowAny]
    serializer_class = BuildRequestSerializer

    @extend_schema(responses=BuildReportSerializer)
    def post(self, request):
        s = BuildRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            parts = pc_builder.load_parts(s.validated_data["parts"])
        except pc_builder.BuildError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(pc_builder.check(parts))


class PCBuildAddToCartView(generics.GenericAPIView):
    """Add a complete, compatible build to the logged-in user's cart (one of each part)."""
    queryset = Product.objects.none()  # the browsable API needs a queryset; these views do not list one
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = BuildRequestSerializer

    @extend_schema(responses=BuildReportSerializer)
    def post(self, request):
        s = BuildRequestSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        try:
            parts = pc_builder.load_parts(s.validated_data["parts"])
            report = pc_builder.add_to_cart(request.user, parts)
        except pc_builder.BuildError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)
        _items, _total, count = services.get_cart(request.user)
        return Response({**report, "cart_count": count}, status=status.HTTP_201_CREATED)


class DemoAccountsView(generics.GenericAPIView):
    """Fixed demo logins (admin + customers). Empty when TECHCART_SHOW_DEMO_ACCOUNTS=0."""
    queryset = Product.objects.none()  # the browsable API needs a queryset; these views do not list one
    permission_classes = [permissions.AllowAny]
    serializer_class = DemoAccountSerializer
    pagination_class = None

    @extend_schema(responses=DemoAccountSerializer(many=True))
    def get(self, request):
        data = public_demo_accounts() if settings.SHOW_DEMO_ACCOUNTS else []
        return Response(DemoAccountSerializer(data, many=True).data)


class MeView(generics.RetrieveAPIView):
    """The currently authenticated user."""
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user
