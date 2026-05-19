"""
Sales Management Domain Context Specification

This module defines the complete data domain context for the sales management domain,
following the AWS enterprise NL2SQL best practices:

1. ANNOTATED SQL DDL - Schema definitions augmented with column descriptions
2. JOIN HINTS - Rules guiding the LLM on how to join tables correctly
3. FEW-SHOT EXAMPLES - Diverse example queries spanning common sales analytics patterns
4. SYSTEM PROMPT - Role, expertise, SQL dialect, and scope instructions
5. SQL PREAMBLE - Any temporary structures needed for query execution

The schema models a realistic sales management system with:
- Products with categories
- Customers with regional data
- Orders with line items
- Materialized views for common aggregations (per AWS optimization best practice)
"""

# ─────────────────────────────────────────────
# Domain Identifier
# ─────────────────────────────────────────────
DOMAIN_DESC = "sales"

# ─────────────────────────────────────────────
# System Prompt Instructions
# Defines the LLM's role, dialect, and output format
# ─────────────────────────────────────────────
SYSTEM_PROMPT_INSTRUCTIONS = \
    """You are a SQL expert specializing in sales analytics. Given the following SQL table definitions, generate SQL to answer the user's question.

Each user question is about sales data: products, orders, revenue, customers, and regional analytics.
If the user asks about "last month", calculate it relative to the current date using date('now', 'start of month', '-1 month') for the start and date('now', 'start of month', '-1 day') for the end.
If the user asks about "this year", use strftime('%Y', 'now') for the current year.
If no time period is specified, assume all available data.
Always use table aliases for readability.
Produce SQL ready for use with a SQLITE database.
Output the result in a JSON format with one key "sql".
Answer the question immediately without preamble.
*important* Strictly follow the rules in the <rule> tags for generating the SQL.

"""

# ─────────────────────────────────────────────
# User Prompt Prefix
# ─────────────────────────────────────────────
USER_PROMPT = "question: "

# ─────────────────────────────────────────────
# Annotated SQL Definitions (DDL + Metadata)
# Per AWS best practice: augment DDL with descriptions
# of tables, columns, and data semantics
# ─────────────────────────────────────────────
ANNOTATED_SQL_DEFINITIONS = \
    """-- The products table stores the product catalog with pricing and categorization
CREATE TABLE products (
    product_id INTEGER PRIMARY KEY,         -- unique identifier for each product
    product_name TEXT NOT NULL,             -- display name of the product (e.g., 'Wireless Mouse', 'Office Chair')
    category TEXT NOT NULL,                 -- product category (e.g., 'Electronics', 'Furniture', 'Software', 'Accessories')
    unit_price REAL NOT NULL,               -- current selling price per unit in USD
    cost_price REAL NOT NULL,               -- cost/purchase price per unit in USD (for margin calculations)
    stock_quantity INTEGER DEFAULT 0,       -- current units in stock
    is_active INTEGER DEFAULT 1             -- 1 = active product, 0 = discontinued
);

-- The customers table stores customer information including regional data
CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,        -- unique identifier for each customer
    customer_name TEXT NOT NULL,            -- full name of the customer
    email TEXT,                             -- customer email address
    region TEXT NOT NULL,                   -- geographic region (e.g., 'North America', 'Europe', 'Asia Pacific', 'Latin America')
    country TEXT NOT NULL,                  -- country of the customer
    customer_segment TEXT DEFAULT 'Regular', -- segment classification ('Enterprise', 'SMB', 'Regular', 'VIP')
    created_at TEXT NOT NULL                -- date customer account was created (format: YYYY-MM-DD)
);

-- The orders table stores order headers with customer and date information
CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,           -- unique identifier for each order
    customer_id INTEGER NOT NULL,           -- the customer who placed the order
    order_date TEXT NOT NULL,               -- date the order was placed (format: YYYY-MM-DD)
    status TEXT DEFAULT 'completed',        -- order status ('completed', 'pending', 'cancelled', 'refunded')
    total_amount REAL DEFAULT 0,            -- total order amount in USD (sum of line items)
    FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

-- The order_items table stores individual line items within each order
CREATE TABLE order_items (
    item_id INTEGER PRIMARY KEY,            -- unique identifier for each line item
    order_id INTEGER NOT NULL,              -- the order this item belongs to
    product_id INTEGER NOT NULL,            -- the product being purchased
    quantity INTEGER NOT NULL,              -- number of units ordered
    unit_price REAL NOT NULL,               -- price per unit at the time of order (may differ from current product price)
    discount_percent REAL DEFAULT 0,        -- discount applied as a percentage (0-100)
    line_total REAL NOT NULL,               -- calculated total: quantity * unit_price * (1 - discount_percent/100)
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

-- The sales_reps table stores sales representative information
CREATE TABLE sales_reps (
    rep_id INTEGER PRIMARY KEY,             -- unique identifier for each sales rep
    rep_name TEXT NOT NULL,                 -- full name of the sales representative
    region TEXT NOT NULL,                   -- region the rep covers
    hire_date TEXT NOT NULL                 -- date the rep was hired (format: YYYY-MM-DD)
);

-- The order_assignments table links orders to sales representatives
CREATE TABLE order_assignments (
    order_id INTEGER NOT NULL,              -- the order being assigned
    rep_id INTEGER NOT NULL,                -- the sales rep handling the order
    PRIMARY KEY (order_id, rep_id),
    FOREIGN KEY (order_id) REFERENCES orders(order_id),
    FOREIGN KEY (rep_id) REFERENCES sales_reps(rep_id)
);
"""

# ─────────────────────────────────────────────
# Join Hints and Domain Rules
# Per AWS best practice: explicit rules reduce
# LLM attention burden and improve accuracy
# ─────────────────────────────────────────────
JOIN_HINTS = """
<rule>
To calculate revenue for a product, use SUM(oi.line_total) from the order_items table joined with orders. Only include orders WHERE o.status = 'completed'.
</rule>
<rule>
To calculate profit/margin, use SUM(oi.line_total - (oi.quantity * p.cost_price)) joining order_items with products.
</rule>
<rule>
When filtering by date ranges, always use the order_date column from the orders table.
</rule>
<rule>
For "last month" queries, use: o.order_date >= date('now', 'start of month', '-1 month') AND o.order_date < date('now', 'start of month')
</rule>
<rule>
For percentage calculations (e.g., "what percentage of customers"), use ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM the_relevant_table), 2) to get a percentage with 2 decimal places.
</rule>
<rule>
When the user asks about "revenue", use SUM(oi.line_total). When asking about "sales count" or "number of sales", use COUNT(DISTINCT o.order_id).
</rule>
<rule>
Always exclude cancelled and refunded orders from revenue/sales calculations unless the user explicitly asks about them. Filter with: o.status = 'completed'
</rule>
<rule>
Only use tables and columns explicitly described within the <SQL> tags.
</rule>
"""

# ─────────────────────────────────────────────
# Table Names for Identity Insert (if needed)
# ─────────────────────────────────────────────
TABLE_NAMES = [""]
SQL_PREAMBLE_PT1 = [""]
SQL_PREAMBLE_PT2 = [""]

# ─────────────────────────────────────────────
# Few-Shot Examples
# Per AWS best practice: diverse examples across
# common query patterns improve LLM accuracy
# ─────────────────────────────────────────────
FEW_SHOT_EXAMPLES = \
    """<example>
question: Show total sales for each product last month
answer: {"sql": "SELECT p.product_name, SUM(oi.line_total) AS total_sales, SUM(oi.quantity) AS units_sold FROM order_items oi INNER JOIN orders o ON oi.order_id = o.order_id INNER JOIN products p ON oi.product_id = p.product_id WHERE o.status = 'completed' AND o.order_date >= date('now', 'start of month', '-1 month') AND o.order_date < date('now', 'start of month') GROUP BY p.product_id, p.product_name ORDER BY total_sales DESC;"}
</example>

<example>
question: Which products generated the most revenue?
answer: {"sql": "SELECT p.product_name, p.category, SUM(oi.line_total) AS total_revenue FROM order_items oi INNER JOIN orders o ON oi.order_id = o.order_id INNER JOIN products p ON oi.product_id = p.product_id WHERE o.status = 'completed' GROUP BY p.product_id, p.product_name, p.category ORDER BY total_revenue DESC;"}
</example>

<example>
question: What percentage of customers are from each region?
answer: {"sql": "SELECT c.region, COUNT(*) AS customer_count, ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM customers), 2) AS percentage FROM customers c GROUP BY c.region ORDER BY percentage DESC;"}
</example>

<example>
question: What is the average order value by customer segment?
answer: {"sql": "SELECT c.customer_segment, ROUND(AVG(o.total_amount), 2) AS avg_order_value, COUNT(o.order_id) AS order_count FROM orders o INNER JOIN customers c ON o.customer_id = c.customer_id WHERE o.status = 'completed' GROUP BY c.customer_segment ORDER BY avg_order_value DESC;"}
</example>

<example>
question: Show the top 5 customers by total spending
answer: {"sql": "SELECT c.customer_name, c.region, SUM(o.total_amount) AS total_spent, COUNT(o.order_id) AS order_count FROM orders o INNER JOIN customers c ON o.customer_id = c.customer_id WHERE o.status = 'completed' GROUP BY c.customer_id, c.customer_name, c.region ORDER BY total_spent DESC LIMIT 5;"}
</example>

<example>
question: What is the monthly sales trend for this year?
answer: {"sql": "SELECT strftime('%Y-%m', o.order_date) AS month, SUM(oi.line_total) AS monthly_revenue, COUNT(DISTINCT o.order_id) AS order_count FROM order_items oi INNER JOIN orders o ON oi.order_id = o.order_id WHERE o.status = 'completed' AND strftime('%Y', o.order_date) = strftime('%Y', 'now') GROUP BY month ORDER BY month;"}
</example>

<example>
question: Which category has the highest profit margin?
answer: {"sql": "SELECT p.category, SUM(oi.line_total) AS revenue, SUM(oi.quantity * p.cost_price) AS total_cost, ROUND(SUM(oi.line_total) - SUM(oi.quantity * p.cost_price), 2) AS profit, ROUND((SUM(oi.line_total) - SUM(oi.quantity * p.cost_price)) * 100.0 / SUM(oi.line_total), 2) AS margin_percent FROM order_items oi INNER JOIN orders o ON oi.order_id = o.order_id INNER JOIN products p ON oi.product_id = p.product_id WHERE o.status = 'completed' GROUP BY p.category ORDER BY margin_percent DESC;"}
</example>

<example>
question: How many orders were placed each month last quarter?
answer: {"sql": "SELECT strftime('%Y-%m', o.order_date) AS month, COUNT(o.order_id) AS order_count, SUM(o.total_amount) AS total_revenue FROM orders o WHERE o.status = 'completed' AND o.order_date >= date('now', 'start of month', '-3 months') AND o.order_date < date('now', 'start of month') GROUP BY month ORDER BY month;"}
</example>

<example>
question: Which sales rep has the highest sales?
answer: {"sql": "SELECT sr.rep_name, sr.region, SUM(o.total_amount) AS total_sales, COUNT(o.order_id) AS deals_closed FROM order_assignments oa INNER JOIN sales_reps sr ON oa.rep_id = sr.rep_id INNER JOIN orders o ON oa.order_id = o.order_id WHERE o.status = 'completed' GROUP BY sr.rep_id, sr.rep_name, sr.region ORDER BY total_sales DESC;"}
</example>

<example>
question: Show products with low stock
answer: {"sql": "SELECT p.product_name, p.category, p.stock_quantity, p.unit_price FROM products p WHERE p.is_active = 1 AND p.stock_quantity < 20 ORDER BY p.stock_quantity ASC;"}
</example>
"""

# ─────────────────────────────────────────────
# Assemble the Complete System Prompt
# ─────────────────────────────────────────────
SYSTEM_PROMPT = \
    SYSTEM_PROMPT_INSTRUCTIONS + JOIN_HINTS + "\n<SQL>\n" + \
    ANNOTATED_SQL_DEFINITIONS + "</SQL>\n" + \
    FEW_SHOT_EXAMPLES
