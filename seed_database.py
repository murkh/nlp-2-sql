"""
Database Seeder - Creates and populates the SQLite sales database.

Generates realistic sales data including:
- 10 products across 4 categories
- 30 customers across 4 regions
- 5 sales representatives
- ~200 orders spanning the last 12 months
- ~500 order line items
- Order assignments to sales reps

Run this script to initialize the database before using the NLP2SQL system.
"""

import sqlite3
import random
from datetime import datetime, timedelta

DATABASE_FILE = "db_sales.db"


def create_tables(cursor):
    """Create all tables for the sales management schema."""

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS products (
        product_id INTEGER PRIMARY KEY,
        product_name TEXT NOT NULL,
        category TEXT NOT NULL,
        unit_price REAL NOT NULL,
        cost_price REAL NOT NULL,
        stock_quantity INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        customer_id INTEGER PRIMARY KEY,
        customer_name TEXT NOT NULL,
        email TEXT,
        region TEXT NOT NULL,
        country TEXT NOT NULL,
        customer_segment TEXT DEFAULT 'Regular',
        created_at TEXT NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        order_id INTEGER PRIMARY KEY,
        customer_id INTEGER NOT NULL,
        order_date TEXT NOT NULL,
        status TEXT DEFAULT 'completed',
        total_amount REAL DEFAULT 0,
        FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_items (
        item_id INTEGER PRIMARY KEY,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        discount_percent REAL DEFAULT 0,
        line_total REAL NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(order_id),
        FOREIGN KEY (product_id) REFERENCES products(product_id)
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS sales_reps (
        rep_id INTEGER PRIMARY KEY,
        rep_name TEXT NOT NULL,
        region TEXT NOT NULL,
        hire_date TEXT NOT NULL
    );
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS order_assignments (
        order_id INTEGER NOT NULL,
        rep_id INTEGER NOT NULL,
        PRIMARY KEY (order_id, rep_id),
        FOREIGN KEY (order_id) REFERENCES orders(order_id),
        FOREIGN KEY (rep_id) REFERENCES sales_reps(rep_id)
    );
    """)


def seed_products(cursor):
    """Insert product catalog."""
    products = [
        (1, "Wireless Mouse", "Electronics", 29.99, 12.50, 150, 1),
        (2, "Mechanical Keyboard", "Electronics", 89.99, 35.00, 85, 1),
        (3, "Office Chair", "Furniture", 349.99, 180.00, 40, 1),
        (4, "Standing Desk", "Furniture", 599.99, 310.00, 25, 1),
        (5, "USB-C Hub", "Accessories", 49.99, 18.00, 200, 1),
        (6, "Monitor Arm", "Accessories", 79.99, 32.00, 65, 1),
        (7, "Webcam Pro", "Electronics", 129.99, 55.00, 110, 1),
        (8, "Noise Canceling Headphones", "Electronics", 249.99, 105.00, 55, 1),
        (9, "Project Management Software", "Software", 19.99, 2.00, 999, 1),
        (10, "Cloud Storage Subscription", "Software", 9.99, 1.50, 999, 1),
    ]
    cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?, ?, ?, ?)", products)


def seed_customers(cursor):
    """Insert diverse customer base across 4 regions."""
    customers = [
        # North America
        (
            1,
            "TechCorp Inc",
            "info@techcorp.com",
            "North America",
            "United States",
            "Enterprise",
            "2023-01-15",
        ),
        (
            2,
            "DataFlow LLC",
            "sales@dataflow.com",
            "North America",
            "United States",
            "SMB",
            "2023-03-22",
        ),
        (
            3,
            "Maple Systems",
            "contact@maplesys.ca",
            "North America",
            "Canada",
            "Regular",
            "2023-06-10",
        ),
        (
            4,
            "Silicon Valley Startups",
            "hello@svs.com",
            "North America",
            "United States",
            "SMB",
            "2023-08-01",
        ),
        (
            5,
            "Pacific Innovations",
            "info@pacinno.com",
            "North America",
            "United States",
            "Enterprise",
            "2023-02-14",
        ),
        (
            6,
            "Northern Lights Tech",
            "info@nlt.ca",
            "North America",
            "Canada",
            "Regular",
            "2023-11-20",
        ),
        (
            7,
            "Quantum Solutions",
            "hello@quantum.com",
            "North America",
            "United States",
            "VIP",
            "2023-01-05",
        ),
        (
            8,
            "MountainView Analytics",
            "contact@mva.com",
            "North America",
            "United States",
            "SMB",
            "2024-01-10",
        ),
        # Europe
        (
            9,
            "GlobalSoft Ltd",
            "info@globalsoft.co.uk",
            "Europe",
            "United Kingdom",
            "Enterprise",
            "2023-04-18",
        ),
        (
            10,
            "BerlinTech GmbH",
            "kontakt@berlintech.de",
            "Europe",
            "Germany",
            "SMB",
            "2023-05-25",
        ),
        (
            11,
            "Paris Digital",
            "bonjour@parisdigital.fr",
            "Europe",
            "France",
            "Regular",
            "2023-07-14",
        ),
        (
            12,
            "Nordic Innovations",
            "hello@nordic.se",
            "Europe",
            "Sweden",
            "SMB",
            "2023-09-30",
        ),
        (
            13,
            "Mediterranean Systems",
            "info@medsys.es",
            "Europe",
            "Spain",
            "Regular",
            "2024-02-01",
        ),
        (
            14,
            "Alpine Solutions AG",
            "info@alpinesol.ch",
            "Europe",
            "Switzerland",
            "VIP",
            "2023-03-12",
        ),
        # Asia Pacific
        (
            15,
            "Tokyo Systems KK",
            "info@tokyosys.jp",
            "Asia Pacific",
            "Japan",
            "Enterprise",
            "2023-02-28",
        ),
        (
            16,
            "SingaporeTech Pte",
            "hello@sgtech.sg",
            "Asia Pacific",
            "Singapore",
            "SMB",
            "2023-06-15",
        ),
        (
            17,
            "Mumbai Digital",
            "info@mumbaidigital.in",
            "Asia Pacific",
            "India",
            "Regular",
            "2023-08-22",
        ),
        (
            18,
            "Seoul Innovations",
            "contact@seolinno.kr",
            "Asia Pacific",
            "South Korea",
            "SMB",
            "2023-10-05",
        ),
        (
            19,
            "Sydney Solutions",
            "g'day@sydsol.au",
            "Asia Pacific",
            "Australia",
            "Regular",
            "2024-01-15",
        ),
        (
            20,
            "Shanghai Enterprise Co",
            "info@shent.cn",
            "Asia Pacific",
            "China",
            "Enterprise",
            "2023-04-08",
        ),
        (
            21,
            "Bangalore Tech Hub",
            "info@blrtech.in",
            "Asia Pacific",
            "India",
            "SMB",
            "2023-12-01",
        ),
        (
            22,
            "KL Digital Sdn Bhd",
            "hello@kldigital.my",
            "Asia Pacific",
            "Malaysia",
            "Regular",
            "2024-03-10",
        ),
        # Latin America
        (
            23,
            "São Paulo Systems",
            "contato@spsystems.br",
            "Latin America",
            "Brazil",
            "SMB",
            "2023-05-12",
        ),
        (
            24,
            "Buenos Aires Tech",
            "hola@batech.ar",
            "Latin America",
            "Argentina",
            "Regular",
            "2023-07-20",
        ),
        (
            25,
            "Mexico Digital SA",
            "info@mexdigital.mx",
            "Latin America",
            "Mexico",
            "SMB",
            "2023-09-15",
        ),
        (
            26,
            "Lima Innovations",
            "info@limainno.pe",
            "Latin America",
            "Peru",
            "Regular",
            "2024-01-25",
        ),
        (
            27,
            "Santiago Software",
            "contacto@santiagosw.cl",
            "Latin America",
            "Chile",
            "SMB",
            "2023-11-08",
        ),
        (
            28,
            "Bogota Cloud Services",
            "info@bogotacloud.co",
            "Latin America",
            "Colombia",
            "Regular",
            "2024-02-14",
        ),
        (
            29,
            "Caribbean Digital",
            "hello@caribdigital.jm",
            "Latin America",
            "Jamaica",
            "Regular",
            "2024-04-01",
        ),
        (
            30,
            "Montevideo Systems",
            "info@mvdsys.uy",
            "Latin America",
            "Uruguay",
            "Regular",
            "2024-05-01",
        ),
    ]
    cursor.executemany("INSERT INTO customers VALUES (?, ?, ?, ?, ?, ?, ?)", customers)


def seed_sales_reps(cursor):
    """Insert sales representatives covering different regions."""
    reps = [
        (1, "Alice Johnson", "North America", "2022-06-01"),
        (2, "Bob Smith", "Europe", "2022-09-15"),
        (3, "Carol Williams", "Asia Pacific", "2023-01-10"),
        (4, "David Brown", "Latin America", "2023-03-20"),
        (5, "Eva Martinez", "North America", "2023-07-01"),
    ]
    cursor.executemany("INSERT INTO sales_reps VALUES (?, ?, ?, ?)", reps)


def seed_orders_and_items(cursor):
    """Generate realistic order data spanning the last 12 months."""
    random.seed(42)  # Reproducible data

    # Region-to-rep mapping for order assignments
    region_to_reps = {
        "North America": [1, 5],
        "Europe": [2],
        "Asia Pacific": [3],
        "Latin America": [4],
    }

    # Customer IDs grouped by region
    customer_regions = {}
    cursor.execute("SELECT customer_id, region FROM customers")
    for cid, region in cursor.fetchall():
        customer_regions.setdefault(region, []).append(cid)

    # Product info for pricing
    cursor.execute("SELECT product_id, unit_price FROM products")
    product_prices = {pid: price for pid, price in cursor.fetchall()}
    product_ids = list(product_prices.keys())

    # Generate orders for last 12 months
    order_id = 1
    item_id = 1
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)

    statuses = (
        ["completed"] * 85 + ["pending"] * 8 + ["cancelled"] * 5 + ["refunded"] * 2
    )

    for _ in range(250):
        # Random date in the last 12 months
        days_offset = random.randint(0, 365)
        order_date = (start_date + timedelta(days=days_offset)).strftime("%Y-%m-%d")

        # Random customer
        region = random.choice(list(customer_regions.keys()))
        customer_id = random.choice(customer_regions[region])

        status = random.choice(statuses)

        # Generate 1-5 line items per order
        num_items = random.randint(1, 5)
        order_total = 0

        items = []
        for _ in range(num_items):
            product_id = random.choice(product_ids)
            quantity = random.randint(1, 10)
            price = product_prices[product_id]
            discount = random.choice(
                [0, 0, 0, 5, 10, 15, 20]
            )  # Most orders have no discount
            line_total = round(quantity * price * (1 - discount / 100), 2)
            order_total += line_total

            items.append(
                (item_id, order_id, product_id, quantity, price, discount, line_total)
            )
            item_id += 1

        order_total = round(order_total, 2)

        # Insert order
        cursor.execute(
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?)",
            (order_id, customer_id, order_date, status, order_total),
        )

        # Insert line items
        cursor.executemany(
            "INSERT INTO order_items VALUES (?, ?, ?, ?, ?, ?, ?)", items
        )

        # Assign to sales rep based on customer region
        rep_id = random.choice(region_to_reps[region])
        cursor.execute(
            "INSERT INTO order_assignments VALUES (?, ?)", (order_id, rep_id)
        )

        order_id += 1


def seed_database():
    """Create and populate the sales database."""
    conn = sqlite3.connect(DATABASE_FILE)
    cursor = conn.cursor()

    # Drop existing tables for clean seed
    tables = [
        "order_assignments",
        "order_items",
        "orders",
        "sales_reps",
        "customers",
        "products",
    ]
    for table in tables:
        cursor.execute(f"DROP TABLE IF EXISTS {table}")

    create_tables(cursor)
    seed_products(cursor)
    seed_customers(cursor)
    seed_sales_reps(cursor)
    seed_orders_and_items(cursor)

    conn.commit()

    # Print summary
    for table in [
        "products",
        "customers",
        "orders",
        "order_items",
        "sales_reps",
        "order_assignments",
    ]:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  {table}: {count} rows")

    conn.close()
    print(f"\n✅ Database '{DATABASE_FILE}' created and seeded successfully!")


if __name__ == "__main__":
    seed_database()
