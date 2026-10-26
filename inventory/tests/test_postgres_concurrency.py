from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from rest_framework.test import APIClient

from inventory.models import Order, Product


@pytest.mark.django_db(transaction=True)
def test_concurrent_orders_cannot_oversell_the_last_unit():
    if connection.vendor != "postgresql":
        pytest.skip("Row-level locking is verified with PostgreSQL.")

    user = get_user_model().objects.create_user(
        username="concurrent-buyer", password="test-password"
    )
    product = Product.objects.create(
        name="Last unit", sku="LAST-UNIT", price="10.00", stock_quantity=1
    )
    user_id = user.pk
    product_id = product.pk
    start_together = Barrier(2)

    def submit_order():
        close_old_connections()
        try:
            customer = get_user_model().objects.get(pk=user_id)
            client = APIClient()
            client.force_authenticate(user=customer)
            start_together.wait(timeout=10)
            response = client.post(
                "/api/orders/",
                {"items": [{"product_id": product_id, "quantity": 1}]},
                format="json",
            )
            return response.status_code
        finally:
            close_old_connections()

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(lambda _: submit_order(), range(2)))

    assert sorted(statuses) == [201, 400]
    product.refresh_from_db()
    assert product.stock_quantity == 0
    assert Order.objects.count() == 1
