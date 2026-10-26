from django.contrib import admin
from .models import Order, OrderItem, Product


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "sku",
        "price",
        "stock_quantity",
        "stock_status",
        "updated_at",
    )
    search_fields = ("name", "sku")
    list_filter = ("created_at",)
    list_editable = ("stock_quantity",)
    readonly_fields = ("created_at", "updated_at")
    list_per_page = 25

    @admin.display(description="Stock status")
    def stock_status(self, product):
        if product.stock_quantity == 0:
            return "Out of stock"
        if product.stock_quantity <= 5:
            return "Low stock"
        return "In stock"


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    fields = ("product", "quantity", "unit_price", "subtotal")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "created_by", "created_at", "item_count", "total_amount")
    list_filter = ("created_at",)
    search_fields = ("=id", "created_by__username", "items__product__sku")
    readonly_fields = ("created_by", "created_at", "total_amount")
    inlines = (OrderItemInline,)
    date_hierarchy = "created_at"

    @admin.display(description="Items")
    def item_count(self, order):
        return order.items.count()

    @admin.display(description="Order total")
    def total_amount(self, order):
        return order.total

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
