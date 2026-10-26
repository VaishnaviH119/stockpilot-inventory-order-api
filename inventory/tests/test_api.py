from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from inventory.models import Order, OrderItem, Product
from inventory.services import create_order


User = get_user_model()


class ProductAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.staff = User.objects.create_user(
            username="manager", password="test-password", is_staff=True
        )

    def test_site_root_redirects_to_api_index(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api/")

    def test_browsable_api_login_redirects_to_api_index(self):
        response = self.client.post(
            "/api-auth/login/",
            {"username": self.staff.username, "password": "test-password"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "/api/")

    def test_staff_can_create_product(self):
        self.client.force_authenticate(self.staff)
        response = self.client.post(
            "/api/products/",
            {
                "name": "Desk Lamp",
                "sku": " lamp-01 ",
                "description": "LED lamp",
                "price": "24.50",
                "stock_quantity": 8,
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["sku"], "LAMP-01")
        self.assertEqual(Product.objects.get().price, Decimal("24.50"))

    def test_product_validation_rejects_bad_price_and_negative_stock(self):
        self.client.force_authenticate(self.staff)
        for price, stock in [("0.00", 5), ("-1.00", 5), ("5.00", -1)]:
            response = self.client.post(
                "/api/products/",
                {
                    "name": "Invalid Product",
                    "sku": f"INVALID-{price}-{stock}",
                    "price": price,
                    "stock_quantity": stock,
                },
                format="json",
            )
            self.assertEqual(response.status_code, 400)
        self.assertEqual(Product.objects.count(), 0)

    def test_sku_must_be_unique(self):
        Product.objects.create(name="First", sku="ONE", price="1.00", stock_quantity=1)
        self.client.force_authenticate(self.staff)
        response = self.client.post(
            "/api/products/",
            {"name": "Second", "sku": "ONE", "price": "2.00", "stock_quantity": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_product_writes_require_staff(self):
        customer = User.objects.create_user(username="customer", password="test-password")
        self.client.force_authenticate(customer)
        response = self.client.post(
            "/api/products/",
            {"name": "Unauthorized", "sku": "NOPE", "price": "2.00", "stock_quantity": 1},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    def test_product_in_an_order_cannot_be_deleted(self):
        customer = User.objects.create_user(username="buyer", password="test-password")
        product = Product.objects.create(
            name="Ordered item", sku="ORDERED", price="3.00", stock_quantity=2
        )
        create_order(user=customer, items=[{"product_id": product.id, "quantity": 1}])
        self.client.force_authenticate(self.staff)

        response = self.client.delete(f"/api/products/{product.id}/")

        self.assertEqual(response.status_code, 409)
        self.assertTrue(Product.objects.filter(pk=product.id).exists())

    def test_product_list_is_public(self):
        response = self.client.get("/api/products/")
        self.assertEqual(response.status_code, 200)


class OrderAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(username="buyer", password="test-password")
        self.product = Product.objects.create(
            name="Notebook", sku="NOTE-1", price=Decimal("4.25"), stock_quantity=10
        )

    def test_authenticated_order_saves_price_total_and_deducts_stock(self):
        self.client.force_authenticate(self.customer)
        response = self.client.post(
            "/api/orders/",
                {
                    "items": [
                        {
                            "product_id": self.product.id,
                            "quantity": 3,
                            "unit_price": "0.01",
                            "total": "0.03",
                        }
                    ]
                },
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["total"], "12.75")
        item = OrderItem.objects.get()
        self.assertEqual(item.unit_price, Decimal("4.25"))
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 7)

    def test_insufficient_stock_rejects_order_without_deducting_any_stock(self):
        extra = Product.objects.create(
            name="Pen", sku="PEN-1", price=Decimal("1.00"), stock_quantity=1
        )
        self.client.force_authenticate(self.customer)
        response = self.client.post(
            "/api/orders/",
            {
                "items": [
                    {"product_id": self.product.id, "quantity": 2},
                    {"product_id": extra.id, "quantity": 2},
                ]
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)
        self.product.refresh_from_db()
        extra.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(extra.stock_quantity, 1)

    def test_invalid_quantities_and_unknown_products_are_rejected(self):
        self.client.force_authenticate(self.customer)
        for product_id, quantity in [(self.product.id, 0), (99999, 1)]:
            response = self.client.post(
                "/api/orders/",
                {"items": [{"product_id": product_id, "quantity": quantity}]},
                format="json",
            )
            self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_failed_database_write_rolls_back_order_items_and_stock(self):
        with patch(
            "inventory.services.Product.objects.bulk_update",
            side_effect=RuntimeError("simulated database failure"),
        ):
            with self.assertRaises(RuntimeError):
                create_order(
                    user=self.customer,
                    items=[{"product_id": self.product.id, "quantity": 2}],
                )

        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(OrderItem.objects.count(), 0)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)

    def test_order_endpoints_require_authentication(self):
        self.assertIn(self.client.get("/api/orders/").status_code, [401, 403])
        self.assertIn(
            self.client.post("/api/orders/", {"items": []}, format="json").status_code,
            [401, 403],
        )

    def test_customers_only_see_their_own_orders(self):
        order = create_order(
            user=self.customer,
            items=[{"product_id": self.product.id, "quantity": 1}],
        )
        other_customer = User.objects.create_user(username="other", password="test-password")
        self.client.force_authenticate(other_customer)

        self.assertEqual(self.client.get("/api/orders/").data["count"], 0)
        self.assertEqual(self.client.get(f"/api/orders/{order.id}/").status_code, 404)
