from django.core.management.base import BaseCommand

from inventory.models import Product


class Command(BaseCommand):
    help = "Create a small, repeatable set of sample products for API demos."

    def handle(self, *args, **options):
        products = [
            {
                "sku": "SP-COFFEE-001",
                "name": "Arabica Coffee Beans",
                "description": "One kilogram bag of roasted Arabica beans.",
                "price": "899.00",
                "stock_quantity": 24,
            },
            {
                "sku": "SP-MUG-002",
                "name": "Ceramic Travel Mug",
                "description": "Insulated 350 ml reusable travel mug.",
                "price": "549.00",
                "stock_quantity": 16,
            },
            {
                "sku": "SP-TEA-003",
                "name": "Green Tea Sachets",
                "description": "Box of 25 individually wrapped tea sachets.",
                "price": "275.00",
                "stock_quantity": 40,
            },
        ]

        created_count = 0
        for product in products:
            _, created = Product.objects.get_or_create(
                sku=product["sku"], defaults=product
            )
            created_count += int(created)

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo data ready: {created_count} product(s) created; "
                "existing demo products were left unchanged."
            )
        )
