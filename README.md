# StockPilot — Inventory & Order Management API

StockPilot is a small inventory and order API built with Django, Django REST Framework, and the Django ORM. It demonstrates product CRUD, server-side order pricing, protected stock changes, transaction handling, and automated API tests.

## Requirements

- Python 3.12 or later
- PostgreSQL for concurrency verification (SQLite is the default for local development)

## Local setup

From the repository root in PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py createsuperuser
python manage.py seed_demo_data
python manage.py runserver
```

Open `http://127.0.0.1:8000/` to be redirected to the browsable API index. Django Admin is at `http://127.0.0.1:8000/admin/`, and the browsable API login is at `http://127.0.0.1:8000/api-auth/login/`. Product reads are public. Staff users can create and change products. The admin product list highlights low or empty stock and supports inline stock edits. Orders are displayed with their item and price snapshots, but cannot be manually changed or deleted. An authenticated user can create orders and only view their own orders; staff can view all orders.

## API endpoints

| Method | Endpoint | Access | Purpose |
| --- | --- | --- | --- |
| GET | `/api/products/` | Public | List products |
| POST | `/api/products/` | Staff | Create a product |
| GET | `/api/products/{id}/` | Public | Retrieve a product |
| PUT/PATCH | `/api/products/{id}/` | Staff | Update a product |
| DELETE | `/api/products/{id}/` | Staff | Delete an unused product (409 if order history references it) |
| GET | `/api/orders/` | Authenticated | List the caller's orders |
| POST | `/api/orders/` | Authenticated | Create an order |
| GET | `/api/orders/{id}/` | Owner or staff | Retrieve an order |

Product listing supports `?search=lamp`, `?ordering=price`, and `?page=2&page_size=20` (maximum page size 100).

### Create an order

```json
{
  "items": [
    {"product_id": 1, "quantity": 2},
    {"product_id": 4, "quantity": 1}
  ]
}
```

The client sends product IDs and quantities only. The server reads current prices, stores a price snapshot on each order item, computes the total, and deducts inventory. Client-supplied prices and totals are ignored because they are not accepted input fields.

## How order creation works

`Order` belongs to a Django user and has multiple `OrderItem` rows. Each item references a product and stores `unit_price` as the price at purchase time. That snapshot keeps old receipts correct after a catalog price change.

The order service runs inside `transaction.atomic()`. It locks products in stable ID order with `select_for_update()`, validates all requested quantities, writes the order and items, then updates stock. A failure rolls back all writes. PostgreSQL enforces row locks for this workflow. SQLite does not provide equivalent row-level locking, so it is useful for quick development but not for verifying concurrent oversell protection.

## Authentication

The API supports Django session authentication for the browsable API and HTTP Basic authentication for simple local clients. Product writes require a staff account. Orders require a signed-in user, and regular users are limited to their own orders. For deployment, serve authentication over HTTPS and set a strong `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=false`, and an explicit `DJANGO_ALLOWED_HOSTS` value.

Copy `.env.example` to `.env` for local development and fill in the values. The project loads simple `KEY=VALUE` entries from `.env`; that file is ignored by Git. Environment variables already set in the process take precedence. For PostgreSQL, set `DB_ENGINE=postgres`, provide the `DB_*` connection values, and create the `stockpilot` database before running migrations. In pgAdmin, connect to the built-in `postgres` database and run `CREATE DATABASE stockpilot;` as a database administrator. In deployment, configure environment variables directly and keep `DEBUG` disabled.

## Tests

```powershell
python -m pytest -q
```

The suite covers product validation and access control, order totals and price snapshots, successful stock deductions, insufficient stock, invalid input, user-scoped order reads, and transaction rollback after a simulated database write failure. A PostgreSQL-only concurrency test submits two orders for the same last unit and verifies that one succeeds while the other is rejected; SQLite skips this row-locking test because its locking behavior differs.
