from django.contrib import admin

from .models import CartItem, Category, Order, OrderItem, Product


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "icon")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "brand", "price", "stock", "is_featured", "is_active")
    list_filter = ("category", "is_featured", "is_active")
    list_editable = ("price", "stock", "is_featured", "is_active")
    search_fields = ("name", "brand", "description")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ("product", "product_name", "price", "quantity")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("number", "user", "full_name", "total", "status", "created_at")
    list_filter = ("status",)
    inlines = [OrderItemInline]


admin.site.register(CartItem)
admin.site.site_header = "TechCart administration"
