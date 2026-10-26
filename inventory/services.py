from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import Order, OrderItem, Product


@transaction.atomic
def create_order(*, user, items):
    """Create an order and deduct its stock as one all-or-nothing operation."""
    product_ids = [item["product_id"] for item in items]
    if len(product_ids) != len(set(product_ids)):
        raise ValidationError({"items": "Each product can appear only once per order."})

    # Lock in stable ID order to reduce deadlock risk when orders overlap.
    products = list(
        Product.objects.select_for_update()
        .filter(id__in=product_ids)
        .order_by("id")
    )
    by_id = {product.id: product for product in products}
    missing_ids = sorted(set(product_ids) - set(by_id))
    if missing_ids:
        raise ValidationError({"items": f"Unknown product IDs: {missing_ids}."})

    for item in items:
        product = by_id[item["product_id"]]
        if product.stock_quantity < item["quantity"]:
            raise ValidationError(
                {
                    "items": (
                        f"Insufficient stock for {product.sku}: "
                        f"requested {item['quantity']}, available {product.stock_quantity}."
                    )
                }
            )

    order = Order.objects.create(created_by=user)
    order_items = []
    for item in items:
        product = by_id[item["product_id"]]
        quantity = item["quantity"]
        order_items.append(
            OrderItem(
                order=order,
                product=product,
                quantity=quantity,
                unit_price=product.price,
            )
        )
        product.stock_quantity -= quantity

    OrderItem.objects.bulk_create(order_items)
    Product.objects.bulk_update(products, ["stock_quantity"])
    return order
