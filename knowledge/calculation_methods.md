# Calculation Methods — SQL Patterns

## Year-over-Year Growth
To calculate YoY growth, compare revenue between the same month in consecutive years:
```sql
SELECT
    strftime('%Y-%m', order_date) AS month,
    SUM(total_amount) AS revenue
FROM orders
WHERE status = 'completed'
GROUP BY month
ORDER BY month;
```

## Running Total / Cumulative Revenue
Use a window function to compute cumulative revenue over time:
```sql
SELECT
    order_date,
    total_amount,
    SUM(total_amount) OVER (ORDER BY order_date) AS cumulative_revenue
FROM orders
WHERE status = 'completed';
```

## Regional Revenue Breakdown
Join orders with customers to get revenue by region:
```sql
SELECT
    c.region,
    COUNT(DISTINCT o.order_id) AS order_count,
    SUM(o.total_amount) AS total_revenue
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
WHERE o.status = 'completed'
GROUP BY c.region
ORDER BY total_revenue DESC;
```

## Product Performance Analysis
Join order_items with products for product-level metrics:
```sql
SELECT
    p.product_name,
    p.category,
    SUM(oi.quantity) AS total_units_sold,
    SUM(oi.line_total) AS total_revenue,
    ROUND(SUM(oi.line_total - oi.quantity * p.cost_price), 2) AS gross_profit
FROM order_items oi
JOIN products p ON oi.product_id = p.product_id
JOIN orders o ON oi.order_id = o.order_id
WHERE o.status = 'completed'
GROUP BY p.product_id
ORDER BY total_revenue DESC;
```

## Time-Based Filtering
For "last month", "last quarter", or "last year" queries, use date arithmetic:
- Last 30 days: `WHERE order_date >= date('now', '-30 days')`
- Last month: `WHERE strftime('%Y-%m', order_date) = strftime('%Y-%m', 'now', '-1 month')`
- Last quarter: `WHERE order_date >= date('now', '-3 months')`
- Last year: `WHERE order_date >= date('now', '-1 year')`

## Sales Rep Performance
Join through order_assignments to get rep-level metrics:
```sql
SELECT
    sr.rep_name,
    sr.region,
    COUNT(DISTINCT oa.order_id) AS orders_handled,
    SUM(o.total_amount) AS total_revenue
FROM sales_reps sr
JOIN order_assignments oa ON sr.rep_id = oa.rep_id
JOIN orders o ON oa.order_id = o.order_id
WHERE o.status = 'completed'
GROUP BY sr.rep_id
ORDER BY total_revenue DESC;
```
