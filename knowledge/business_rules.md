# Business Rules — Sales Management System

## Revenue Calculation
Revenue is calculated as the sum of `line_total` from the `order_items` table.
Each `line_total` is computed as: `quantity × unit_price × (1 - discount_percent / 100)`.
Total order revenue is stored in `orders.total_amount` as a pre-computed aggregate.
When calculating revenue, only include orders with `status = 'completed'` unless explicitly asked for all statuses.

## Profit Margin
Profit margin for a product is calculated as: `(unit_price - cost_price) / unit_price × 100`.
This represents the gross margin percentage.
The `cost_price` field in the `products` table represents the cost to the company.
Net profit per order item is: `line_total - (quantity × cost_price)`.

## Discount Policy
Discounts are stored as `discount_percent` in the `order_items` table.
Common discount tiers are: 0% (standard), 5%, 10%, 15%, and 20%.
Most orders (approximately 70%) have no discount applied.
Discount is applied per line item, not per order.

## Order Statuses
Orders can have the following statuses:
- **completed** — Order fulfilled and delivered (~85% of orders)
- **pending** — Order placed but not yet fulfilled (~8%)
- **cancelled** — Order cancelled before fulfillment (~5%)
- **refunded** — Order completed but later refunded (~2%)

When reporting "sales" or "revenue", only `completed` orders should be included unless the user specifies otherwise.

## Customer Segmentation
Customers are categorized into segments:
- **Enterprise** — Large organizations with high-volume purchasing
- **SMB** — Small and medium businesses
- **Regular** — Standard customers with moderate purchasing
- **VIP** — High-value customers with premium service agreements

The segment is stored in `customers.customer_segment`.

## Active vs Inactive Products
Products have an `is_active` flag (0 or 1) in the `products` table.
When querying products for sales analysis, include all products unless the user asks specifically for "active" or "current" products.

## Sales Representative Assignment
Each order is assigned to a sales representative via the `order_assignments` table.
Sales reps are assigned based on the customer's region.
Some regions have multiple reps (e.g., North America has two reps).
