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
    path("products/bulk/", dash.product_bulk, name="product_bulk"),
    path("products/<int:pk>/edit/", dash.product_form, name="product_edit"),
    path("products/<int:pk>/duplicate/", dash.product_duplicate, name="product_duplicate"),
    path("products/<int:pk>/delete/", dash.product_delete, name="product_delete"),
    path("products/<int:pk>/stock/", dash.product_stock, name="product_stock"),
    path("categories/", dash.category_list, name="categories"),
    path("categories/new/", dash.category_form, name="category_create"),
    path("categories/<int:pk>/edit/", dash.category_form, name="category_edit"),
    path("categories/<int:pk>/delete/", dash.category_delete, name="category_delete"),
    path("orders/", dash.order_list, name="orders"),
    path("orders/<int:pk>/", dash.order_detail, name="order_detail"),
    path("orders/<int:pk>/delivery/", dash.order_delivery, name="order_delivery"),
    path("orders/<int:pk>/mark-paid/", dash.order_mark_paid, name="order_mark_paid"),
    path("orders/<int:pk>/packing-slip/", dash.order_packing_slip, name="order_packing_slip"),
    path("products/<int:pk>/photos/<int:photo_pk>/delete/", dash.photo_delete, name="photo_delete"),
    path("products/<int:pk>/photos/<int:photo_pk>/make-main/", dash.photo_make_main, name="photo_make_main"),
    path("discounts/", dash.discount_list, name="discounts"),
    path("discounts/new/", dash.discount_form, name="discount_create"),
    path("discounts/<int:pk>/edit/", dash.discount_form, name="discount_edit"),
    path("discounts/<int:pk>/delete/", dash.discount_delete, name="discount_delete"),
    path("activity/", dash.activity_list, name="activity"),
    path("customers/", dash.customer_list, name="customers"),
    path("customers/<int:pk>/toggle/", dash.customer_toggle, name="customer_toggle"),
    path("customers/<int:pk>/make-admin/", dash.customer_make_admin, name="customer_make_admin"),
    path("team/", dash.team_list, name="team"),
    path("team/new/", dash.team_add, name="team_add"),
    path("team/<int:pk>/edit/", dash.team_edit, name="team_edit"),
    path("team/<int:pk>/remove/", dash.team_remove, name="team_remove"),
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
