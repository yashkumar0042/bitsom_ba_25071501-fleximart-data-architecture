-- ------------------------------------------------------------
-- Query 1: Customer Purchase History
-- Business Question: "Generate a detailed report showing each customer's name, email,
-- total number of orders placed, and total amount spent. Include only customers who have
-- placed at least 2 orders and spent more than ₹5,000. Order by total amount spent in
-- descending order."
-- Expected to return customers with 2+ orders and >5000 spent
-- ------------------------------------------------------------

SELECT
  CONCAT(c.first_name, ' ', c.last_name) AS customer_name,
  c.email,
  COUNT(DISTINCT o.order_sk) AS total_orders,
  ROUND(SUM(oi.quantity * oi.unit_price), 2) AS total_spent
FROM customers c
JOIN orders o
  ON o.customer_sk = c.customer_sk
JOIN order_items oi
  ON oi.order_sk = o.order_sk
GROUP BY
  c.customer_sk, c.first_name, c.last_name, c.email
HAVING
  COUNT(DISTINCT o.order_sk) >= 2
  AND SUM(oi.quantity * oi.unit_price) > 5000
ORDER BY
  total_spent DESC;


-- ------------------------------------------------------------
-- Query 2: Product Sales Analysis
-- Business Question: "For each product category, show the category name, number of different
-- products sold, total quantity sold, and total revenue generated. Only include categories
-- that have generated more than ₹10,000 in revenue. Order by total revenue descending."
-- Expected to return categories with >10000 revenue
-- ------------------------------------------------------------

SELECT
  p.category AS category,
  COUNT(DISTINCT p.product_sk) AS num_products,
  SUM(oi.quantity) AS total_quantity_sold,
  ROUND(SUM(oi.quantity * oi.unit_price), 2) AS total_revenue
FROM products p
JOIN order_items oi
  ON oi.product_sk = p.product_sk
GROUP BY
  p.category
HAVING
  SUM(oi.quantity * oi.unit_price) > 10000
ORDER BY
  total_revenue DESC;


-- ------------------------------------------------------------
-- Query 3: Monthly Sales Trend (Year 2024)
-- Business Question: "Show monthly sales trends for the year 2024. For each month,
-- display the month name, total number of orders, total revenue, and the running total
-- of revenue (cumulative revenue from January to that month)."
-- Expected to show monthly and cumulative revenue
-- Output: month_name | total_orders | monthly_revenue | cumulative_revenue
-- ------------------------------------------------------------

WITH monthly_sales AS (
  SELECT
    MONTH(o.order_date) AS month_num,
    MONTHNAME(o.order_date) AS month_name,
    COUNT(DISTINCT o.order_sk) AS total_orders,
    SUM(oi.quantity * oi.unit_price) AS monthly_revenue
  FROM orders o
  JOIN order_items oi
    ON oi.order_sk = o.order_sk
  WHERE o.order_date >= '2024-01-01'
    AND o.order_date <  '2025-01-01'
  GROUP BY
    MONTH(o.order_date),
    MONTHNAME(o.order_date)
)
SELECT
  month_name,
  total_orders,
  ROUND(monthly_revenue, 2) AS monthly_revenue,
  ROUND(
    SUM(monthly_revenue) OVER (ORDER BY month_num
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW),
    2
  ) AS cumulative_revenue
FROM monthly_sales
ORDER BY
  month_num;
