from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import api, dashboard_views as dash, views

app_name = "store"

urlpatterns = [
    path("", views.home, name="home"),
    path("products/", views.product_list, name="product_list"),
    path("category/<slug:category_slug>/", views.product_list, name="category"),
    path("product/<slug:slug>/", views.product_detail, name="product_detail"),
    path("build-pc/", views.pc_builder_page, name="pc_builder"),
    path("cart/", views.cart, name="cart"),
    path("checkout/", views.checkout, name="checkout"),
    path("orders/", views.order_list, name="order_list"),
    path("orders/<int:pk>/", views.order_detail, name="order_detail"),
    path("orders/<int:pk>/cancel/", views.order_cancel, name="order_cancel"),
    path("orders/<int:pk>/pay/", views.order_pay, name="order_pay"),
    path("orders/<int:pk>/receipt/", views.order_receipt, name="order_receipt"),
]

dashboard_patterns = ([
    path("", dash.overview, name="overview"),
    path("products/", dash.product_list, name="products"),
    path("products/new/", dash.product_form, name="product_create"),
    path("products/<int:pk>/edit/", dash.product_form, name="product_edit"),
    path("products/<int:pk>/delete/", dash.product_delete, name="product_delete"),
    path("products/<int:pk>/stock/", dash.product_stock, name="product_stock"),
    path("orders/", dash.order_list, name="orders"),
    path("orders/<int:pk>/", dash.order_detail, name="order_detail"),
], "dashboard")

router = DefaultRouter()
router.register("categories", api.CategoryViewSet, basename="category")
router.register("products", api.ProductViewSet, basename="product")
router.register("cart", api.CartViewSet, basename="cart")
router.register("orders", api.OrderViewSet, basename="order")

api_patterns = ([
    path("auth/register/", api.RegisterView.as_view(), name="register"),
    path("auth/login/", api.LoginView.as_view(), name="login"),
    path("auth/me/", api.MeView.as_view(), name="me"),
    path("auth/demo-accounts/", api.DemoAccountsView.as_view(), name="demo_accounts"),
    path("pc-builder/parts/", api.PCBuildPartsView.as_view(), name="pc_parts"),
    path("pc-builder/check/", api.PCBuildCheckView.as_view(), name="pc_check"),
    path("pc-builder/add-to-cart/", api.PCBuildAddToCartView.as_view(), name="pc_add_to_cart"),
    path("", include(router.urls)),
], "api")
