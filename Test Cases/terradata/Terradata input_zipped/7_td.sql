SELECT
    customer_id,
    order_id,
    order_amount,
    ROW_NUMBER() OVER (
        PARTITION BY customer_id
        ORDER BY order_amount DESC
    ) AS order_rank
FROM sales_db.orders;
