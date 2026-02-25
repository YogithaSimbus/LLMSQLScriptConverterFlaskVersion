CREATE VIEW sales_db.vw_customer_sales AS
SELECT
    c.customer_id,
    c.customer_name,
    COUNT(o.order_id) AS total_orders,
    SUM(o.order_amount) AS total_sales,
    AVG(o.order_amount) AS avg_order_value
FROM sales_db.customers c
LEFT JOIN sales_db.orders o
    ON c.customer_id = o.customer_id
GROUP BY c.customer_id, c.customer_name;
